"""Immutable-by-content evaluation datasets and protected deterministic scoring."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from evosprig.core.spec import Contract, canonical_json, digest

Split = Literal["search", "selection", "release", "test"]


class Sample(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    input: dict[str, Any]
    expected: Any
    tags: list[str] = Field(default_factory=list, max_length=16)
    required_tools: list[str] = Field(default_factory=list, max_length=32)


class Metric(Contract):
    kind: Literal["exact", "contains", "tool_called"] = "exact"
    output_path: str = "answer"
    normalize_text: bool = False

    def score(self, sample: Sample, result: dict):
        if result["status"] != "succeeded":
            return 0.0, "runtime did not succeed"
        observed_tools = {
            event["data"].get("tool")
            for event in result["events"]
            if event["type"] == "tool.result"
        }
        if set(sample.required_tools) - observed_tools:
            return 0.0, "required tool receipt was absent"
        if self.kind == "tool_called":
            names = [
                event["data"].get("tool")
                for event in result["events"]
                if event["type"] == "tool.result"
            ]
            passed = sample.expected in names
            return float(passed), "required tool used" if passed else "required tool was not used"
        actual = result["output"]
        try:
            for part in self.output_path.split(".") if self.output_path else []:
                actual = actual[int(part)] if isinstance(actual, list) else actual[part]
        except (KeyError, ValueError, TypeError, IndexError):
            return 0.0, "output path was absent"
        expected = sample.expected
        if self.normalize_text and isinstance(actual, str) and isinstance(expected, str):
            actual, expected = actual.strip().casefold(), expected.strip().casefold()
        if self.kind == "exact":
            passed = canonical_json(actual) == canonical_json(expected)
        else:
            passed = isinstance(actual, str) and isinstance(expected, str) and expected in actual
        return float(passed), "metric passed" if passed else "output did not match expected value"


class EvalSuite(Contract):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    description: str = ""
    metric: Metric = Field(default_factory=Metric)
    search: list[Sample] = Field(min_length=1, max_length=10000)
    selection: list[Sample] = Field(min_length=1, max_length=10000)
    release: list[Sample] = Field(min_length=1, max_length=10000)
    test: list[Sample] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def disjoint(self):
        identifiers, inputs = set(), set()
        for split in ("search", "selection", "release", "test"):
            for sample in getattr(self, split):
                fingerprint = digest(sample.input)
                if sample.id in identifiers or fingerprint in inputs:
                    raise ValueError("sample IDs and inputs must be disjoint across the suite")
                identifiers.add(sample.id)
                inputs.add(fingerprint)
        canonical_json(self.model_dump())
        return self

    @property
    def suite_id(self):
        return digest(self.model_dump())

    def split_id(self, split: Split):
        return digest(
            {
                "suite": self.suite_id,
                "split": split,
                "samples": [sample.model_dump() for sample in getattr(self, split)],
            }
        )

    def optimization_view(self):
        """Only this view, not the full suite, is given to optimization methods."""
        return {
            "suite_id": self.suite_id,
            "search": [sample.model_dump() for sample in self.search],
            "selection": [sample.model_dump() for sample in self.selection],
        }
