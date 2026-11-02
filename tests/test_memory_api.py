import asyncio

import httpx
from test_durable_api import approval_spec, wait_for

from evosprig.server.app import create_app
from evosprig.server.auth import Principal


async def test_scoped_projects_runs_memory_and_documents(tmp_path):
    app = create_app(
        tmp_path,
        principals={"alice-token": Principal("alice", "lab"), "bob-token": Principal("bob", "lab")},
    )
    async with app.router.lifespan_context(app):
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost"
            ) as alice,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost"
            ) as bob,
        ):
            alice.headers["authorization"] = "Bearer alice-token"
            bob.headers["authorization"] = "Bearer bob-token"
            spec = approval_spec().model_dump()
            assert (await alice.post("/api/projects", json={"spec": spec})).status_code == 201
            assert (await bob.get("/api/projects/approval")).status_code == 404
            assert (await bob.post("/api/projects", json={"spec": spec})).status_code == 201
            record = (
                await alice.post(
                    "/api/projects/approval/memory",
                    json={"content": "Project secret: blue", "source": "user"},
                )
            ).json()
            base = "/api/projects/approval/memory"
            assert (await bob.get(base, params={"query": "secret"})).json() == []
            assert (await bob.get(base + "/export")).json() == []
            assert (await bob.get(base + "/" + record["id"])).status_code == 404
            assert (await bob.delete(base + "/" + record["id"])).status_code == 404
            assert (
                await bob.put(base + "/" + record["id"], json={"content": "stolen", "revision": 1})
            ).status_code == 404
            assert (
                await alice.post(base, json={"content": "x", "source": "user", "user": "bob"})
            ).status_code == 422
            run = (
                await alice.post(
                    "/api/projects/approval/runs",
                    json={"revision": 1, "input": {"text": "alice draft"}},
                )
            ).json()
            await wait_for(alice, run["run_id"], "waiting_input")
            for suffix in ["", "/events"]:
                assert (await bob.get("/api/runs/" + run["run_id"] + suffix)).status_code == 404
            for suffix in ["/cancel", "/resume"]:
                assert (await bob.post("/api/runs/" + run["run_id"] + suffix)).status_code == 404
            assert (await bob.get("/api/projects/approval/runs")).json() == []
            document = (
                await alice.post(
                    "/api/projects/approval/documents",
                    json={
                        "title": "Guide",
                        "source": "docs:guide",
                        "text": "Checkpoints preserve completed node results.",
                    },
                )
            ).json()
            assert (
                await alice.get(
                    "/api/projects/approval/documents/search", params={"query": "checkpoints"}
                )
            ).json()[0]["source"] == "docs:guide"
            assert (
                await bob.get(
                    "/api/projects/approval/documents/search", params={"query": "checkpoints"}
                )
            ).json() == []
            assert (
                await bob.delete("/api/projects/approval/documents/" + document["document_id"])
            ).status_code == 404
            # Concurrent middleware contexts must not cross-contaminate identity.
            results = await asyncio.gather(
                *[client.get(base + "/export") for client in [alice, bob] * 6]
            )
            assert all(
                len(response.json()) == (1 if i % 2 == 0 else 0)
                for i, response in enumerate(results)
            )
