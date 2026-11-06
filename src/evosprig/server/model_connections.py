"""Deployment model connections and their optional resident service binding."""

import asyncio
import os
from pathlib import Path

import yaml
from fastapi import HTTPException
from pydantic import Field

from evosprig.config import read_profile
from evosprig.core.spec import Contract
from evosprig.plugins.openai_compatible import Connection


class ModelConnectionUpdate(Contract):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    connection: Connection


class ServicePlacementUpdate(Contract):
    gpu_devices: list[int] | None = None


def install_model_routes(app, profile, *, editable=True):
    lock = asyncio.Lock()

    @app.put("/api/services/{name}/placement")
    async def save_placement(name: str, body: ServicePlacementUpdate):
        if not editable:
            raise HTTPException(403, "Shared services are managed by the server operator")
        if profile is None:
            raise HTTPException(409, "Start Studio with --profile deployment.yaml")
        from evosprig.local_services import ServiceConfig, ServiceManager, service_environment

        async with lock:
            data = read_profile(profile)
            if name not in data.get("services", {}):
                raise HTTPException(404, "Service not found")
            config = {**data["services"][name], "gpu_devices": body.gpu_devices}
            try:
                service_environment(ServiceConfig.model_validate(config))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            status = await asyncio.to_thread(ServiceManager(profile).status, name)
            if status["reachable"] or status["managed"]:
                raise HTTPException(409, "Stop this service before changing its GPU placement")
            data["services"][name] = config
            path = Path(profile)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(yaml.safe_dump(data, sort_keys=False))
            temporary.replace(path)
        return {"saved": name, "gpu_devices": body.gpu_devices}

    @app.get("/api/models")
    async def list_models():
        data = read_profile(profile)
        return {"editable": profile is not None and editable,
                "services": list(data.get("services", {})),
                "models": [{"name": name, **Connection.model_validate(value).model_dump(mode="json"),
                            "key_configured": bool(os.environ.get(value.get("api_key_env") or ""))}
                           for name, value in data.get("models", {}).items()]}

    @app.put("/api/models")
    async def save_model(body: ModelConnectionUpdate):
        if not editable:
            raise HTTPException(403, "Shared deployment connections are managed by the server operator")
        if profile is None:
            raise HTTPException(409, "Start Studio with --profile deployment.yaml to save model connections")
        from evosprig.core.version import check_public_text

        value = body.connection.model_dump(mode="json", exclude_none=True)
        value["api_key_env"] = body.connection.api_key_env
        try:
            check_public_text(yaml.safe_dump(value))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        async with lock:
            data = read_profile(profile)
            if body.connection.local_service and body.connection.local_service not in data.get("services", {}):
                raise HTTPException(422, "Choose a service declared in this deployment profile")
            data.setdefault("models", {})[body.name] = value
            path = Path(profile)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(yaml.safe_dump(data, sort_keys=False))
            temporary.replace(path)
        return {"saved": body.name}
