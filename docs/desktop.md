# Desktop Studio

Use the same canvas, code views and application exports in a desktop window. EvoSprig starts its local backend automatically and keeps projects, knowledge libraries and memory in your workspace.

[中文](zh-CN/desktop.md) · [Studio guide](studio.md) · [Tutorials](tutorials/README.md)

## Install

Download an installer from [GitHub Releases](https://github.com/Toyhom/EvoSprig/releases/tag/v0.1.8). No GitHub account is needed.

| Platform | Download | Install |
| --- | --- | --- |
| Windows x64 | [Installer](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-win-x64.exe) | Run the `.exe`. |
| macOS Apple silicon | [DMG](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-mac-arm64.dmg) | Drag EvoSprig Studio to Applications. |
| macOS Intel | [DMG](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-mac-x64.dmg) | Drag EvoSprig Studio to Applications. |
| Linux x64 | [AppImage](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-linux-x86_64.AppImage) · [DEB](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-linux-amd64.deb) | Make the AppImage executable, or install the DEB. |

Python, the local backend and the web interface are included. Local model servers and application-specific tools are installed separately. Installers are unsigned; on macOS, use the per-app **Open Anyway** option in Privacy & Security when opening a downloaded build.

## First project

1. Start **EvoSprig Studio**. Enter a project name in the sidebar and click **+**.
2. Choose **File → API keys**. Add a variable such as `MODEL_API_KEY` and its value, then restart the local backend from the File menu.
3. Expand **Model connections** in the sidebar. Choose a provider, enter the model ID and use the same key variable name. Save the connection.
4. Select that connection as the **Application default model**. Individual nodes can override it.
5. Save the project, change **Offline demo** to **Live model**, and run.

API keys are encrypted using the OS key store. On Linux without a key store, keys remain in memory for the current session. You can also provide environment variables when launching the application.

## Deploy models independently

Design nodes around model roles and capabilities. Most nodes share an application default; individual roles can override it. The operator binds those roles in the workspace's `deployment.yaml` to a local inference server, a self-hosted API or a cloud API using the OpenAI-compatible chat protocol.

Exports include `model-contract.json`, listing required roles, capabilities and the interface. Deploy the application first, then start a model server and supply its connection. Switching model services changes deployment settings without editing or exporting the agent again. End users submit tasks through the application UI or business API; its operator manages model connections and credentials once.

For a local service without authentication, uncheck **Service requires an API key**. For a self-hosted HTTP endpoint, enable **Allow HTTP for my self-hosted server**. Local services can preload on selected GPUs and stay resident across runs. The operator supplies inference engines and weights; the desktop installer includes Studio and its runtime.

See [model connections](model-connections.md#separate-applications-from-model-deployments) and [local model services](local-models.md).

## Workspaces and files

**File → Open workspace** selects a directory for projects, deployment settings, run history, document indexes and memory. **Show workspace folder** opens it in your file manager. The last workspace and window size are remembered.

The default workspace is inside the app's user-data directory:

- Windows: `%APPDATA%/EvoSprig Studio/workspace`
- macOS: `~/Library/Application Support/EvoSprig Studio/workspace`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/EvoSprig Studio/workspace`

**Import project** opens an exported ZIP. The toolbar exports Python, HTTP services or container projects; ComfyUI projects also support workflow JSON. Exported applications run independently of Desktop Studio.

A desktop workspace uses the same files as the web Studio. Open it with either interface; run only one backend against a workspace at a time. Quitting the desktop stops its backend; closing a macOS window keeps the session available from the Dock. Managed model services keep their configured persistent lifetime and can be stopped explicitly from Studio.

## Build from source

Use **Python 3.12+** and **Node.js 22.12+**. Build on the operating system and CPU architecture you want to distribute.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install '.[server,models,mcp,documents,artifacts,evolution]' pyinstaller==6.16.0
npm ci --prefix apps/studio
npm run build --prefix apps/studio
npm ci --prefix apps/desktop
npm start --prefix apps/desktop
```

Set `EVOSPRIG_PYTHON` if your Python executable is outside the active environment. To produce installers:

```bash
python apps/desktop/scripts/build_backend.py
npm run dist --prefix apps/desktop
```

The installers are written to `apps/desktop/dist`. The desktop workflow builds each target on its native runner and checks project creation, offline execution, export and credential settings. Signing can be supplied through electron-builder's `CSC_LINK` / `CSC_KEY_PASSWORD` and Apple notarization variables when preparing a signed distribution.
