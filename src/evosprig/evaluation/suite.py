"""Immutable-by-content evaluation datasets and protected deterministic scoring."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from evosprig.core.spec import Contract, canonical_json, digest

Split = Literal["search", "selection", "release", "test"]


class Sample(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    input: dict[str, Any]
    expected: Any = None
    context: dict[str, Any] = Field(default_factory=dict)
    rubric: str = Field(default="", max_length=12000)
    responses: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=16)
    required_tools: list[str] = Field(default_factory=list, max_length=32)


class Metric(Contract):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, populate_by_name=True)
    kind: Literal[
        "exact", "contains", "tool_called", "json_schema", "llm_judge", "external", "composite"
    ] = "exact"
    target: Literal["output", "node", "trajectory", "environment", "tools"] = "output"
    node: str | None = None
    rubric: str = Field(default="", max_length=12000)
    judge_binding: str | None = None
    repeats: int = Field(default=1, ge=1, le=3)
    judge_max_output_tokens: int = Field(default=1400, ge=128, le=8192)
    judge_max_retries: int = Field(default=1, ge=0, le=3)
    scorer: str | None = None
    schema_: dict | None = Field(default=None, alias="schema")
    components: list[Metric] = Field(default_factory=list, max_length=16)
    weight: float = Field(default=1, gt=0, le=100)
    required: bool = False
    threshold: float = Field(default=0.5, ge=0, le=1)
    reference_path: str = ""

    @model_validator(mode="after")
    def validate_metric(self):
        if self.kind == "composite" and not self.components:
            raise ValueError("composite metric needs components")
        if self.kind != "composite" and self.components:
            raise ValueError("components belong to composite metrics")
        if self.kind == "external" and not self.scorer:
            raise ValueError("external metric needs a deployment scorer name")
        if self.target == "node" and not self.node:
            raise ValueError("node assessment needs a checkpoint path")
        if self.kind == "json_schema":
            from evosprig.core.spec import check_schema

            if self.schema_ is None:
                raise ValueError("json_schema metric needs a schema")
            check_schema(self.schema_)

        def depth(metric):
            return 1 + max((depth(item) for item in metric.components), default=0)

        if depth(self) > 4:
            raise ValueError("metric nesting exceeds four levels")
        return self

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
        try:
            for part in self.reference_path.split(".") if self.reference_path else []:
                expected = expected[int(part)] if isinstance(expected, list) else expected[part]
        except (KeyError, ValueError, TypeError, IndexError):
            return 0.0, "reference path was absent"
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

    @model_validator(mode="before")
    @classmethod
    def choose_metric(cls, data):
        if isinstance(data, dict) and "metric" not in data:
            samples = [
                s
                for split in ("search", "selection", "release", "test")
                for s in data.get(split, [])
            ]
            if any("expected" not in sample for sample in samples if isinstance(sample, dict)):
                data = {**data, "metric": {"kind": "llm_judge", "output_path": ""}}
        return data

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
        data = self.model_dump(by_alias=True)

        def clean(metric):
            defaults = Metric().model_dump(by_alias=True)
            for key in set(defaults) - {"kind", "output_path", "normalize_text"}:
                if metric[key] == defaults[key]:
                    metric.pop(key)
            for child in metric.get("components", []):
                clean(child)

        clean(data["metric"])
        for split in ("search", "selection", "release", "test"):
            for sample in data[split]:
                for key in ("context", "rubric", "responses"):
                    if not sample[key]:
                        sample.pop(key)
        return digest(data)

    def split_id(self, split: Split):
        samples = []
        for sample in getattr(self, split):
            data = sample.model_dump()
            for key in ("context", "rubric", "responses"):
                if not data[key]:
                    data.pop(key)
            samples.append(data)
        return digest(
            {
                "suite": self.suite_id,
                "split": split,
                "samples": samples,
            }
        )

    def optimization_view(self):
        """Only this view, not the full suite, is given to optimization methods."""
        return {
            "suite_id": self.suite_id,
            "search": [sample.model_dump() for sample in self.search],
            "selection": [sample.model_dump() for sample in self.selection],
        }
