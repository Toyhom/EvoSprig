import asyncio

import pytest
from test_evaluation import suite, version
from test_evolution_methods import Proposer, TaskModel

from evosprig.core.journal import LeaseConflict, LeaseLost, Scope
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.gate import ReleaseGate
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.sqlite_studies import StudyStore


async def test_full_study_reserves_validation_and_does_not_publish(tmp_path):
    data = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    config = StudyConfig(
        method="opro",
        allowed_resources=["prompt"],
        rounds=1,
        budget=ExperimentBudget(max_evaluations=10, max_model_calls=20),
        gate=ReleaseGate(min_samples=1),
    )
    store, scope = StudyStore(tmp_path / "studies.sqlite"), Scope("eval-agent")
    base = version()
    store.put(scope, base)
    suite_id = store.put_suite(scope, data)
    record = store.create_study(scope, base.version_id, suite_id, config.model_dump(), {})
    result = await execute_study(
        base=base,
        suite=data,
        config=config,
        models={"main": TaskModel()},
        proposer=Proposer(),
        workspace=tmp_path,
        store=store,
        scope=scope,
        job_id=record["id"],
    )
    assert result["status"] == "completed"
    assert result["gate"]["passed"]
    assert result["reports"]["test"]["baseline"]["score"] == 0
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert result["usage"]["evaluations"] == 8
    assert result["usage"]["model_calls"] == 9
    assert store.release(scope)["version_id"] is None
    assert result["release_changed"] is False
    assert result["selected_version"] != base.version_id
    private = store.get_report(scope, result["reports"]["test"]["selected"]["report_id"])
    assert private["samples"][0]["input"]["question"] == "sealed-secret"


def test_study_fencing_and_expired_jobs_do_not_restart_search(tmp_path, monkeypatch):
    import time

    now = [time.time()]
    monkeypatch.setattr(time, "time", lambda: now[0])
    store, scope, base, data = (
        StudyStore(tmp_path / "db.sqlite"),
        Scope("eval-agent"),
        version(),
        suite(),
    )
    store.put(scope, base)
    store.put_suite(scope, data)
    job = store.create_study(scope, base.version_id, data.suite_id, {}, {})
    generation = store.claim_study(scope, job["id"], "worker-a")
    with pytest.raises(LeaseConflict):
        store.claim_study(scope, job["id"], "worker-b")
    store.update_study(scope, job["id"], "worker-a", generation, usage={"reserved_tokens": 100})
    now[0] += 31
    assert store.pending_studies() == []
    assert store.study(scope, job["id"])["status"] == "interrupted"
    assert store.study(scope, job["id"])["usage"]["reserved_tokens"] == 100
    with pytest.raises(LeaseLost):
        store.update_study(scope, job["id"], "worker-a", generation, status="completed")
    with pytest.raises(KeyError):
        store.get_suite(Scope("eval-agent", "another"), data.suite_id)


async def test_canceled_study_keeps_release_unchanged(tmp_path):
    data, base = suite(), version()
    config = StudyConfig(method="opro", allowed_resources=["prompt"], rounds=1)
    store, scope = StudyStore(tmp_path / "db.sqlite"), Scope("eval-agent")
    store.put(scope, base)
    store.publish(scope, base.version_id, expected_revision=0)
    cancel = asyncio.Event()
    cancel.set()
    result = await execute_study(
        base=base,
        suite=data,
        config=config,
        models={"main": TaskModel()},
        proposer=Proposer(),
        workspace=tmp_path,
        store=store,
        scope=scope,
        job_id="canceled",
        cancel=cancel,
    )
    assert result["status"] == "canceled"
    assert store.release(scope)["revision"] == 1
