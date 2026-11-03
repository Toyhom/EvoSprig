import pytest
from test_evolution_methods import Proposer, TaskModel, suite, version

from evosprig.core.journal import Scope
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.gate import ReleaseGate
from evosprig.evolution.registry import register_method
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.sqlite_studies import StudyStore


async def test_custom_optimizer_uses_runtime_and_release_checks(tmp_path, monkeypatch):
    from evosprig.evolution import registry

    monkeypatch.setattr(registry, "METHODS", dict(registry.METHODS))
    monkeypatch.setattr(registry, "_PLUGINS", {})

    async def optimize(context, *, config):
        assert config.options == {"style": "concise"}
        with pytest.raises(ValueError, match="release or test"):
            await context.evaluate(context.seed, "test")
        candidate = await context.json_proposal({"resources": context.seed})
        await context.evaluate(candidate, "search")
        report = await context.evaluate(candidate, "selection")
        return {"selected": candidate, "selected_score": report["score"], "status": "completed"}

    register_method(
        "test_custom", optimize, title="Custom method", family="test", feedback="scores"
    )
    config = StudyConfig(
        method="test_custom",
        allowed_resources=["prompt"],
        options={"style": "concise"},
        budget=ExperimentBudget(max_evaluations=10, max_model_calls=20),
        gate=ReleaseGate(min_samples=1),
    )
    data = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    store = StudyStore(tmp_path / "studies.sqlite")
    scope = Scope("eval-agent")
    result = await execute_study(
        base=version(),
        suite=data,
        config=config,
        models={"main": TaskModel()},
        proposer=Proposer(),
        workspace=tmp_path,
        store=store,
        scope=scope,
        job_id="plugin-test",
    )
    assert result["gate"]["passed"]
    assert result["release_changed"] is False
    assert result["selected_version"] != result["base_version"]
    with pytest.raises(ValueError, match="already registered"):
        register_method(
            "test_custom", optimize, title="Duplicate", family="test", feedback="scores"
        )


def test_unknown_plugin_is_rejected():
    with pytest.raises(ValueError, match="unknown evolution method"):
        StudyConfig(method="unknown_plugin", allowed_resources=["prompt"])


def test_package_discovery_rolls_back_failed_installation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from evosprig.evolution import registry

    monkeypatch.setattr(registry, "METHODS", dict(registry.METHODS))
    monkeypatch.setattr(registry, "_PLUGINS", {})
    monkeypatch.setattr(registry, "_LOADED", False)

    async def optimize(context, *, config):
        return {"selected": context.seed}

    def install():
        register_method("packaged", optimize, title="Packaged", family="test", feedback="scores")

    def fail():
        raise RuntimeError("missing dependency")

    entries = [SimpleNamespace(load=lambda: install), SimpleNamespace(load=lambda: fail)]
    monkeypatch.setattr(registry, "entry_points", lambda **kwargs: entries)
    with pytest.raises(RuntimeError, match="missing dependency"):
        registry.load_methods()
    assert "packaged" not in registry.METHODS
    entries.pop()
    registry.load_methods()
    registry.load_methods()
    assert registry.custom_method("packaged").optimize is optimize
