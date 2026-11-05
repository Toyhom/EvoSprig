"""Evaluation, candidate comparison and manual release routes."""

from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import HTTPException
from pydantic import Field

from evosprig.config import make_models
from evosprig.core.runtime import Runtime
from evosprig.core.spec import Contract
from evosprig.evaluation.suite import EvalSuite
from evosprig.evolution.study import StudyConfig
from evosprig.plugins.mock import MockProvider

from .auth import current_principal


class StudyBody(Contract):
    suite_id: str
    revision: int = Field(ge=1)
    config: StudyConfig
    mock: bool = True
    proposer_binding: str | None = None


class InputsBody(Contract):
    inputs: list[dict] = Field(min_length=4, max_length=10000)
    name: str = "my-tasks"
    rubric: str = Field(default="", max_length=12000)
    seed: int = Field(default=0, ge=0)
    judge_max_output_tokens: int = Field(default=1400, ge=128, le=8192)
    judge_max_retries: int = Field(default=1, ge=0, le=3)


class PublishBody(Contract):
    study_id: str
    release_revision: int = Field(ge=0)


class ReleaseInitialBody(Contract):
    revision: int = Field(ge=1)
    release_revision: int = Field(ge=0)


class RollbackBody(Contract):
    version_id: str
    release_revision: int = Field(ge=1)


def install_evolution_routes(app, store, worker, projects, compile_document, tools_for, profile):
    def document(project_id):
        return projects.get(project_id, identity=current_principal.get().key)

    def scope(project_id):
        document(project_id)
        return current_principal.get().scope(project_id)

    @app.get("/api/evolution/methods")
    async def methods():
        from evosprig.evolution.methods import METHODS
        from evosprig.evolution.registry import load_methods

        load_methods()
        return METHODS

    @app.get("/api/projects/{project_id}/suites")
    async def suites(project_id: str):
        return store.suites(scope(project_id))

    @app.post("/api/projects/{project_id}/suites", status_code=201)
    async def add_suite(project_id: str, body: EvalSuite):
        return {"suite_id": store.put_suite(scope(project_id), body)}

    @app.post("/api/projects/{project_id}/suites/from-inputs", status_code=201)
    async def add_inputs(project_id: str, body: InputsBody):
        from evosprig.evaluation.authoring import suite_from_inputs

        selected_scope = scope(project_id)
        try:
            suite = suite_from_inputs(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return {"suite_id": store.put_suite(selected_scope, suite)}

    @app.get("/api/projects/{project_id}/studies")
    async def studies(project_id: str):
        return store.studies(scope(project_id))

    @app.post("/api/projects/{project_id}/studies", status_code=202)
    async def start_study(project_id: str, body: StudyBody):
        selected_scope, project = scope(project_id), document(project_id)
        if project["revision"] != body.revision:
            raise HTTPException(409, "save or reload the project before improving")
        suite = store.get_suite(selected_scope, body.suite_id)
        base = compile_document(project)
        try:
            body.config.prepare(base)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(422, "evolution target or search space does not match the application") from exc
        if body.config.budget.max_evaluations <= 2 * (len(suite.release) + len(suite.test)):
            raise HTTPException(422, "budget must cover search plus paired validation")
        evaluation_config = (
            yaml.safe_load(Path(profile).read_text()).get("evaluation", {}) if profile else {}
        )
        try:
            from evosprig.evaluation.deployment import EvaluationConfig

            evaluation = EvaluationConfig.model_validate(evaluation_config)
            models = make_models(base.spec, profile, body.mock)
            if body.mock:
                proposer = MockProvider()
            else:
                name = body.proposer_binding or ("main" if "main" in models else next(iter(models), None))
                if name not in models:
                    raise ValueError("proposer binding is missing")
                proposer = models[name]
            model_metadata = Runtime(models)._engine.model_metadata()
            proposer_metadata = Runtime({"proposer": proposer})._engine.model_metadata()["proposer"]
            tools = tools_for(selected_scope)
            for binding in base.spec.tools.values():
                if evaluation.industry and binding.plugin in {
                    "industry.materials",
                    "industry.search",
                    "industry.invoke",
                }:
                    if binding.version != "1":
                        raise ValueError("unsupported industry tool version")
                    continue
                tool = tools.resolve(binding.plugin, binding.version)
                if tool.side_effect != "read_only" and not (
                    (evaluation.environment.memory_writes
                    and tool.name in {"memory.write", "memory.remember", "memory.summarize"})
                    or (evaluation.environment.workspace_writes
                    and tool.name in {"workspace.write", "workspace.wait", "messages.send", "messages.ack", "messages.wait"})
                ):
                    raise ValueError("write tools need an SDK evaluation environment")
        except (ValueError, OSError):
            raise HTTPException(422, "model or evaluation tool configuration is invalid") from None
        store.put(selected_scope, base)
        record = store.create_study(
            selected_scope,
            base.version_id,
            body.suite_id,
            body.config.model_dump(),
            {
                "models": model_metadata,
                "proposer": proposer_metadata,
                "tools": tools.bindings,
                "evaluation": evaluation_config,
                "mock": body.mock,
            },
        )
        worker.dispatch(record)
        return {"id": record["id"], "status": "queued", "base_version": base.version_id}

    @app.get("/api/projects/{project_id}/studies/{study_id}")
    async def study(project_id: str, study_id: str):
        return store.study(scope(project_id), study_id)

    @app.get("/api/projects/{project_id}/studies/{study_id}/comparison")
    async def comparison(project_id: str, study_id: str, split: str = "release"):
        from evosprig.evaluation.comparison import comparison_record

        selected_scope = scope(project_id)
        study = store.study(selected_scope, study_id)
        group = (study.get("result") or {}).get("reports", {}).get(split, {})
        if split not in {"release", "test"} or not {"baseline", "selected"} <= group.keys():
            raise HTTPException(409, "paired validation is not available")
        models = study["bindings"]["models"]
        judges = study["bindings"].get("evaluation", {}).get("judges", {})
        task_model = next(iter(models.values()), {}).get("model", "configured model")
        result = comparison_record(
            store.get_report(selected_scope, group["baseline"]["report_id"]),
            store.get_report(selected_scope, group["selected"]["report_id"]),
            method=study["config"]["method"],
            task_model=task_model,
            judge_model=next(iter(judges.values()), {}).get("model"),
        )
        before = store.get(selected_scope, result["baseline_version"])
        after = store.get(selected_scope, result["evolved_version"])
        prepared, _, _, _ = StudyConfig.model_validate(study["config"]).prepare(before)
        result["resource_changes"] = {
            name: {"role": after.spec.resources[name].role,
                   "before": prepared.resources.get(name, ""), "after": content}
            for name, content in after.resources.items()
            if prepared.resources.get(name) != content
        }
        result["spec_diff"] = store.diff(before, after).get("agent.json")
        return result

    @app.post("/api/projects/{project_id}/studies/{study_id}/cancel", status_code=202)
    async def cancel_study(project_id: str, study_id: str):
        record = store.cancel_study(scope(project_id), study_id)
        if study_id in worker.cancellations:
            worker.cancellations[study_id].set()
        return record

    @app.get("/api/projects/{project_id}/candidates")
    async def candidates(project_id: str):
        return store.candidates(scope(project_id))

    @app.get("/api/projects/{project_id}/versions/{version_id}")
    async def version(project_id: str, version_id: str):
        value = store.get(scope(project_id), version_id)
        return {**asdict(value), "spec": value.spec.model_dump(), "resources": value.resources}

    @app.get("/api/projects/{project_id}/reports/{report_id}")
    async def report(project_id: str, report_id: str):
        return store.get_report(scope(project_id), report_id)

    @app.get("/api/projects/{project_id}/release")
    async def release(project_id: str):
        return store.release(scope(project_id))

    @app.get("/api/projects/{project_id}/release/history")
    async def history(project_id: str):
        return store.history(scope(project_id))

    @app.post("/api/projects/{project_id}/release/initial")
    async def initial_release(project_id: str, body: ReleaseInitialBody):
        selected_scope, project = scope(project_id), document(project_id)
        if project["revision"] != body.revision:
            raise HTTPException(409, "project revision changed")
        if body.release_revision != 0:
            raise HTTPException(409, "initial release is only valid before the first release")
        version = compile_document(project)
        store.put(selected_scope, version)
        return store.publish(
            selected_scope, version.version_id, expected_revision=0, reason="manual baseline"
        )

    @app.post("/api/projects/{project_id}/release")
    async def publish(project_id: str, body: PublishBody):
        selected_scope = scope(project_id)
        study = store.study(selected_scope, body.study_id)
        result = study["result"]
        if study["status"] != "completed" or not result or not result["gate"]["passed"]:
            raise HTTPException(409, "study has no candidate that passed release validation")
        return store.publish(
            selected_scope,
            result["selected_version"],
            expected_revision=body.release_revision,
            expected_base=result["base_version"],
            reason="manual validated candidate",
            evidence={"study_id": body.study_id, "gate": result["gate"]},
        )

    @app.post("/api/projects/{project_id}/release/rollback")
    async def rollback(project_id: str, body: RollbackBody):
        try:
            return store.publish(
                scope(project_id),
                body.version_id,
                expected_revision=body.release_revision,
                reason="manual rollback",
                rollback=True,
            )
        except ValueError:
            raise HTTPException(
                409, "rollback requires a compatible previously released version"
            ) from None
