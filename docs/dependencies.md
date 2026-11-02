# Dependencies and references

EvoSprig is licensed under Apache-2.0. Dependencies retain their own licenses and are installed separately; exact versions are recorded in the Python and npm lock files.

| Dependency | License |
| --- | --- |
| Pydantic, jsonschema, PyYAML | MIT |
| HTTPX | BSD-3-Clause |
| FastAPI, Starlette, uvicorn | MIT / BSD-3-Clause |
| React, React Flow, Vite | MIT |
| TypeScript, Playwright | Apache-2.0 |
| MCP Python SDK, GEPA | MIT |
| Pillow, imageio-ffmpeg | HPND / BSD-2-Clause |
| Hatchling, pytest, Ruff | MIT |

The motion-graphics example uses a separately installed FFmpeg executable; consult that build's license when distributing binaries. EvoSprig source distributions do not bundle FFmpeg.

Algorithm references and implementation details are in [Evolution](evolution.md). Application pattern references are included with each [example](../examples/README.md).
