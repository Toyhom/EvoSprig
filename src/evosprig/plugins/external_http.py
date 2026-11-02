"""Durable remote jobs: POST endpoint, GET/DELETE endpoint/{job_id}."""

import re
from typing import Literal

from pydantic import Field

from evosprig.core.protocols import ExecutionError, ExternalStatus, ExternalTool
from evosprig.plugins.http_tools import HTTPToolConfig, http_tool


class ExternalHTTPConfig(HTTPToolConfig):
    kind: Literal["external_http"] = "external_http"
    method: Literal["POST"] = "POST"
    side_effect: Literal["write"] = "write"
    idempotent: Literal[True] = True
    job_timeout_seconds: float = Field(default=3600.0, gt=0, le=86400)


def external_http_tool(config: ExternalHTTPConfig, *, transport=None):
    async def request(method, suffix="", **arguments):
        raw = config.model_dump(exclude={"job_timeout_seconds"})
        raw.update(
            kind="http",
            method=method,
            endpoint=config.endpoint.rstrip("/") + suffix,
            idempotent=method == "POST",
            output_schema={},
        )
        return await http_tool(HTTPToolConfig.model_validate(raw), transport=transport).function(
            **arguments
        )

    def suffix(job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
            raise ExecutionError("external service returned an invalid job ID")
        return "/" + job_id

    async def submit(*, idempotency_key, **arguments):
        body = await request("POST", **arguments, idempotency_key=idempotency_key)
        job_id = body.get("job_id") if isinstance(body, dict) else None
        suffix(job_id)
        return job_id

    async def poll(job_id):
        body = await request("GET", suffix(job_id))
        if not isinstance(body, dict):
            raise ExecutionError("external service returned invalid status")
        return ExternalStatus(
            body.get("status"),
            body.get("output"),
            "remote job failed" if body.get("error") else None,
        )

    async def cancel(job_id):
        await request("DELETE", suffix(job_id))

    return ExternalTool(
        config.name,
        config.description,
        config.input_schema,
        config.output_schema,
        submit,
        poll,
        cancel,
        version=config.version,
        timeout_seconds=config.timeout_seconds,
        job_timeout_seconds=config.job_timeout_seconds,
    )
