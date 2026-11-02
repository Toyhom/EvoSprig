import asyncio
import io
import zipfile

import httpx
from test_evaluation import suite, version
from test_evolution_methods import Proposer, TaskModel

from evosprig.evolution.study import StudyConfig
from evosprig.server.app import create_app
from evosprig.server.auth import Principal


async def test_full_api_study_release_running_frozen_version_rollback_export(tmp_path):
    app = create_app(tmp_path, principals={"alice": Principal("alice"), "bob": Principal("bob")})

    # Deterministic fixtures exercise actual job orchestration and scoring without API cost.
    def models(bindings):
        return {name: Proposer() if name == "proposer" else TaskModel() for name in bindings}

    app.state.study_worker.model_factory = models
    base, data = version(), suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost",
            headers={"authorization": "Bearer alice"},
        ) as client:
            project = (
                await client.post(
                    "/api/projects",
                    json={"spec": base.spec.model_dump(), "resources": base.resources},
                )
            ).json()
            assert project["resources"] == base.resources
            assert (
                await client.post(
                    "/api/projects/eval-agent/release/initial",
                    json={"revision": 1, "release_revision": 0},
                )
            ).status_code == 200
            suite_id = (
                await client.post("/api/projects/eval-agent/suites", json=data.model_dump())
            ).json()["suite_id"]
            config = StudyConfig(method="opro", allowed_resources=["prompt"], rounds=1).model_dump()
            config["gate"]["min_samples"] = 1
            start = await client.post(
                "/api/projects/eval-agent/studies",
                json={"suite_id": suite_id, "revision": 1, "config": config},
            )
            assert start.status_code == 202, start.text
            identifier = start.json()["id"]
            for _ in range(300):
                study = (await client.get(f"/api/projects/eval-agent/studies/{identifier}")).json()
                if study["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(0.02)
            assert study["status"] == "completed", study
            assert study["result"]["gate"]["passed"]
            candidates = (await client.get("/api/projects/eval-agent/candidates")).json()
            assert candidates[0]["diff"]
            released = await client.post(
                "/api/projects/eval-agent/release",
                json={"study_id": identifier, "release_revision": 1},
            )
            assert released.status_code == 200, released.text
            candidate_id = released.json()["version_id"]
            assert candidate_id != base.version_id
            assert (
                await client.post(
                    "/api/projects/eval-agent/release",
                    json={"study_id": identifier, "release_revision": 1},
                )
            ).status_code == 409
            selected_run = await client.post(
                "/api/projects/eval-agent/runs",
                json={"revision": 1, "input": {"question": "release"}, "use_release": True},
            )
            assert selected_run.status_code == 202
            assert selected_run.json()["agent_version"] == candidate_id
            # Editing draft resources keeps the active version and running version fixed.
            edited = await client.put(
                "/api/projects/eval-agent",
                json={
                    "spec": base.spec.model_dump(),
                    "resources": {"prompt": "new draft"},
                    "layout": {},
                    "revision": 1,
                },
            )
            assert edited.status_code == 200
            assert (await client.get("/api/projects/eval-agent/release")).json()[
                "version_id"
            ] == candidate_id
            exported = await client.post(
                "/api/projects/eval-agent/export", params={"version_id": candidate_id}
            )
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                assert archive.read("prompts/main.md").decode() == "Return the exact label ok."
                assert not any(name.endswith("sqlite") for name in archive.namelist())
            rollback = await client.post(
                "/api/projects/eval-agent/release/rollback",
                json={"version_id": base.version_id, "release_revision": 2},
            )
            assert rollback.status_code == 200
            assert rollback.json()["version_id"] == base.version_id
            assert len((await client.get("/api/projects/eval-agent/release/history")).json()) == 3
            client.headers["authorization"] = "Bearer bob"
            assert (
                await client.get(f"/api/projects/eval-agent/studies/{identifier}")
            ).status_code == 404
            assert (
                await client.post(
                    "/api/projects/eval-agent/release",
                    json={"study_id": identifier, "release_revision": 3},
                )
            ).status_code == 404
