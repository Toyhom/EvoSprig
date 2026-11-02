"""Bound media payloads in textual assessment without changing execution inputs."""

import hashlib


def model_evidence(value):
    if isinstance(value, dict):
        return {
            key: {
                "omitted": "base64 media; use tool/environment observations",
                "characters": len(item),
                "sha256": hashlib.sha256(item.encode()).hexdigest(),
            }
            if key.endswith("_base64") and isinstance(item, str)
            else model_evidence(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [model_evidence(item) for item in value]
    return value
