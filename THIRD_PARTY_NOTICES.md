# Third-party dependencies

EvoSprig M0 uses these separately installed packages. Exact direct and transitive versions are recorded in the Python lock files and Studio package-lock.json. Package license metadata remains with installed dependencies.

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

Model HTTP contracts follow the [DeepSeek API documentation](https://api-docs.deepseek.com/) and the compatible chat-completion format. M0 contains original workflow/runtime code and uses the dependencies above through their public APIs.

Project license selection and public distribution are pending the first release decision.
