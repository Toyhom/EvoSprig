# EvoSprig Desktop

The EvoSprig canvas and Python runtime, packaged for Windows, macOS and Linux.

[Install and use](../../docs/desktop.md) · [中文指南](../../docs/zh-CN/desktop.md)

```bash
# After installing the Python dependencies and building apps/studio:
npm ci
npm start
```

Use Node.js 22.12 or newer. `EVOSPRIG_PYTHON` selects the development interpreter. Packaged builds include their own Python backend.

```bash
python scripts/build_backend.py
npm run dist
```

Electron owns a loopback backend on an ephemeral port. The renderer uses the same Studio assets as the browser; API authentication remains in the main process. Workspace files persist across upgrades. System key storage encrypts saved credentials. Standalone application exports contain the framework runtime and run without Electron.
