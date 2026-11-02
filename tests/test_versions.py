from concurrent.futures import ThreadPoolExecutor

import pytest
from test_evaluation import version

from evosprig.core.journal import Scope
from evosprig.evolution.gate import ReleaseGate
from evosprig.plugins.sqlite_projects import RevisionConflict
from evosprig.plugins.sqlite_versions import VersionStore


def test_candidate_protection_and_immutable_snapshot(tmp_path):
    store, scope, base = VersionStore(tmp_path / "versions.sqlite"), Scope("eval-agent"), version()
    identifier = store.put(scope, base)
    candidate = store.candidate(
        scope,
        base,
        {"prompt": "Answer concisely."},
        allowed=["prompt"],
        method="opro",
        job_id="job-1",
    )
    assert candidate["version_id"] != identifier
    assert "Answer concisely" in candidate["diff"]["prompt"]
    assert store.get(scope, identifier).resources["prompt"] == "Answer accurately."
    with pytest.raises(ValueError, match="protected"):
        store.candidate(
            scope, base, {"scorer": "return 1"}, allowed=["prompt"], method="opro", job_id="job-1"
        )
    with pytest.raises(ValueError, match="credential"):
        store.candidate(
            scope,
            base,
            {"prompt": "sk-" + "x" * 25},
            allowed=["prompt"],
            method="opro",
            job_id="job-1",
        )
    with pytest.raises(KeyError):
        store.get(Scope("eval-agent", "other"), identifier)
    assert store.candidates(Scope("eval-agent", "other")) == []
    assert store.release(scope)["revision"] == 0


def test_concurrent_release_cas_and_compatible_rollback(tmp_path):
    store, scope, base = VersionStore(tmp_path / "versions.sqlite"), Scope("eval-agent"), version()
    store.put(scope, base)
    first = store.publish(scope, base.version_id, expected_revision=0)
    candidates = [
        store.candidate(
            scope, base, {"prompt": text}, allowed=["prompt"], method="test", job_id="job"
        )
        for text in ["revision A", "revision B"]
    ]

    def publish(candidate):
        try:
            return store.publish(
                scope,
                candidate["version_id"],
                expected_revision=first["revision"],
                expected_base=base.version_id,
            )["revision"]
        except RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(map(str, pool.map(publish, candidates))) == ["2", "conflict"]
    active = store.release(scope)
    rejected = next(item for item in candidates if item["version_id"] != active["version_id"])
    with pytest.raises(ValueError, match="previously released"):
        store.publish(scope, rejected["version_id"], expected_revision=2, rollback=True)
    rollback = store.publish(scope, base.version_id, expected_revision=2, rollback=True)
    assert rollback["revision"] == 3
    assert len(store.history(scope)) == 3


def test_release_gate_checks_regression_sample_count_and_failed_runs():
    base = {
        "suite_id": "suite",
        "report_id": "base",
        "split": "release",
        "count": 2,
        "score": 0.5,
        "tags": {"qa": 1.0, "tools": 0.0},
        "input_tokens": 20,
        "output_tokens": 10,
        "samples": [
            {"sample_id": "a", "run": {"status": "succeeded"}},
            {"sample_id": "b", "run": {"status": "succeeded"}},
        ],
    }
    improved = {**base, "report_id": "candidate", "score": 1.0, "tags": {"qa": 1.0, "tools": 1.0}}
    assert ReleaseGate(min_gain=0.1).assess(base, improved)["passed"]
    regressed = {**improved, "tags": {"qa": 0.0, "tools": 1.0}}
    assert not ReleaseGate().assess(base, regressed)["passed"]
    assert not ReleaseGate(min_samples=3).assess(base, improved)["passed"]
    with pytest.raises(ValueError):
        ReleaseGate().assess(base, {**improved, "split": "test"})
