"""A synchronous compatible embedding adapter for memory ingestion and retrieval."""

import os

import httpx
from pydantic import Field, model_validator

from evosprig.core.protocols import ProviderError
from evosprig.core.spec import Contract
from evosprig.plugins.http_tools import validate_endpoint
from evosprig.plugins.semantic_memory import vectors


class EmbeddingConnection(Contract):
    base_url: str
    model: str = Field(min_length=1)
    api_key_env: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    timeout_seconds: float = Field(default=30, gt=0, le=600)

    @model_validator(mode="after")
    def endpoint(self):
        validate_endpoint(self.base_url)
        return self


class OpenAIEmbeddings:
    def __init__(self, connection: EmbeddingConnection, *, transport=None):
        self.connection, self.transport = connection, transport
        self.model_id = connection.base_url.rstrip("/") + "/" + connection.model

    def embed(self, texts):
        if (
            not isinstance(texts, list)
            or not 1 <= len(texts) <= 256
            or any(not isinstance(text, str) or not text or len(text) > 100000 for text in texts)
        ):
            raise ValueError("embed needs 1..256 bounded texts")
        key = os.environ.get(self.connection.api_key_env)
        if not key:
            raise ProviderError(
                "configuration", "embedding credential environment variable is missing"
            )
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.connection.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    self.connection.base_url.rstrip("/") + "/embeddings",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "model": self.connection.model,
                        "input": texts,
                        "encoding_format": "float",
                    },
                ) as response:
                    if not 200 <= response.status_code < 300:
                        raise ProviderError(
                            "upstream", f"embedding endpoint returned HTTP {response.status_code}"
                        )
                    body = bytearray()
                    for part in response.iter_bytes():
                        body.extend(part)
                        if len(body) > 16000000:
                            raise ProviderError(
                                "response_limit", "embedding response exceeded its byte limit"
                            )
            import json

            data = json.loads(body)["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError("embedding batch size differs")
            if any(type(item.get("index")) is not int for item in data):
                raise ValueError("embedding indices must be integers")
            ordered = sorted(data, key=lambda item: item["index"])
            if [item["index"] for item in ordered] != list(range(len(texts))):
                raise ValueError("embedding indices differ")
            return vectors([item["embedding"] for item in ordered], len(texts))
        except httpx.HTTPError:
            raise ProviderError("transport", "embedding transport failed") from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError(
                "invalid_response", "embedding response violated the batch contract"
            ) from None
