"""Fixed authored smoke tasks; no external dataset or measured benchmark claim."""

from pathlib import Path

import yaml

from evosprig.evaluation.suite import EvalSuite


def qa(identifier, question, evidence, expected):
    return {
        "id": identifier,
        "input": {"question": question, "evidence": evidence},
        "expected": expected,
        "tags": ["qa"],
    }


def addition(identifier, a, b):
    return {
        "id": identifier,
        "input": {
            "question": f"Use the addition tool to total the two measured counts: {a} and {b}. Give the result as a number without units.",
            "evidence": "These are authored demonstration counts.",
        },
        "expected": str(a + b),
        "tags": ["tools"],
        "required_tools": ["add"],
    }


suite = EvalSuite.model_validate(
    {
        "id": "evidence-and-tools-smoke",
        "description": "Nine authored smoke cases with disjoint inputs: 3 search, 2 selection, 2 release, 2 sealed test. Exact answer strings plus required tool receipts. For integration evidence, not a general effectiveness estimate.",
        "metric": {"kind": "exact", "output_path": "answer", "normalize_text": True},
        "search": [
            qa(
                "search-qa-1",
                "Which color marks successful checks?",
                "The guide uses green for success and amber for a pending check.",
                "green",
            ),
            addition("search-tool-1", 14, 9),
            qa(
                "search-qa-2",
                "What identifier prevents an old worker from committing?",
                "The runtime records a counter named generation to reject writes from a superseded worker.",
                "generation",
            ),
        ],
        "selection": [
            qa(
                "selection-qa",
                "Which transport is selected in this protocol recipe?",
                "The recipe selects Streamable HTTP for the tool connection.",
                "streamable http",
            ),
            addition("selection-tool", 17, 8),
        ],
        "release": [
            qa(
                "release-qa",
                "What database stores local development checkpoints?",
                "Local checkpoints and operation receipts are stored in SQLite.",
                "sqlite",
            ),
            addition("release-tool", 23, 19),
        ],
        "test": [
            qa(
                "test-qa",
                "What is the one-word label before ledger in the recovery evidence?",
                "Recovery applies the deletion ledger before exposing restored memory records.",
                "deletion",
            ),
            addition("test-tool", 31, 16),
        ],
    }
)

if __name__ == "__main__":
    Path(__file__).with_name("suite.yaml").write_text(
        yaml.safe_dump(suite.model_dump(), sort_keys=False, allow_unicode=True)
    )
