# Third-party dependencies

EvoSprig Alpha uses these separately installed packages. Exact direct and transitive versions are recorded in the Python lock files and Studio package-lock.json. Package license metadata remains with installed dependencies.

| Package | Purpose | License | Source |
| --- | --- | --- | --- |
| Pydantic | Typed contract validation and JSON Schema generation | MIT | https://github.com/pydantic/pydantic |
| jsonschema | Validate tool, input and output JSON | MIT | https://github.com/python-jsonschema/jsonschema |
| PyYAML | Readable project specifications | MIT | https://github.com/yaml/pyyaml |
| HTTPX | Optional async model transport | BSD-3-Clause | https://github.com/encode/httpx |
| FastAPI / Starlette | Optional local service | MIT / BSD-3-Clause | https://github.com/fastapi/fastapi ; https://github.com/encode/starlette |
| uvicorn | ASGI server | BSD-3-Clause | https://github.com/encode/uvicorn |
| React / React DOM | Studio interface | MIT | https://github.com/facebook/react |
| React Flow | Canvas | MIT | https://github.com/xyflow/xyflow |
| Vite | Studio build tooling | MIT | https://github.com/vitejs/vite |
| TypeScript | Studio type checking | Apache-2.0 | https://github.com/microsoft/TypeScript |
| Playwright | Browser verification | Apache-2.0 | https://github.com/microsoft/playwright |
| Hatchling / pytest / Ruff | Build and verification tooling | MIT / MIT / MIT | https://github.com/pypa/hatch ; https://github.com/pytest-dev/pytest ; https://github.com/astral-sh/ruff |

Model HTTP contracts follow the [DeepSeek API documentation](https://api-docs.deepseek.com/) and the compatible chat-completion format. The product contains original workflow/runtime code and uses the dependencies above through their public APIs.

The local release candidate uses Apache-2.0. Public distribution is handled separately by the project owner.

MCP support optionally uses the official `mcp` Python SDK 1.30.0 (MIT) and its
separately installed dependencies. The base runtime does not import the SDK. The
pinned development lock and optional export lock record the tested dependency set.
Protocol scope is documented in `docs/tools.md`.

Evolution optionally uses the official GEPA library 0.1.4 (MIT), installed separately.
Its source attribution and paper/project links are retained in the method documentation.
The OPRO baseline is an independent implementation of the published score-history idea;
no FlashRSI framework source is included.

The optional short-film example uses Pillow 12.0.0 (HPND) and imageio-ffmpeg 0.6.0 (BSD-2-Clause). The separately installed FFmpeg executable may include GPL components such as libx264; consult its bundled license/build metadata. The product does not redistribute that binary or third-party media assets. Qwen3-0.6B (Apache-2.0) was used only for an external vLLM compatibility test; weights are not included.
