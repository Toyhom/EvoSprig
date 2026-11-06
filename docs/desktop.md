# Desktop Studio

Use the same canvas, code views and application exports in a desktop window. EvoSprig starts its local backend automatically and keeps projects, knowledge libraries and memory in your workspace.

[中文](zh-CN/desktop.md) · [Studio guide](studio.md) · [Tutorials](tutorials/README.md)

## Install

Open the latest successful [Desktop clients build](https://github.com/Toyhom/EvoSprig/actions/workflows/desktop.yml), then download the artifact for your computer. GitHub requires a signed-in account to download build artifacts.

| Platform | Download | Install |
| --- | --- | --- |
| Windows x64 | `EvoSprig-Studio-win-x64` | Unzip and run the `.exe` installer. |
| macOS Apple silicon | `EvoSprig-Studio-mac-arm64` | Open the `.dmg` and drag EvoSprig Studio to Applications. |
| macOS Intel | `EvoSprig-Studio-mac-x64` | Open the `.dmg` and drag EvoSprig Studio to Applications. |
| Linux x64 | `EvoSprig-Studio-linux-x64` | Install the `.deb`, or make the AppImage executable and run it. |

Python, the local backend and the web interface are included. Local model servers and application-specific tools are installed separately. Current development builds are unsigned; on macOS, use the per-app **Open Anyway** option in Privacy & Security when opening a downloaded build.

## First project

1. Start **EvoSprig Studio**. Enter a project name in the sidebar and click **+**.
2. Choose **File → API keys**. Add a variable such as `MODEL_API_KEY` and its value, then restart the local backend from the File menu.
3. Expand **Model connections** in the sidebar. Choose a provider, enter the model ID and use the same key variable name. Save the connection.
4. Select that connection as the **Application default model**. Individual nodes can override it.
5. Save the project, change **Offline demo** to **Live model**, and run.

API keys are encrypted using the OS key store. On Linux without a key store, keys remain in memory for the current session. You can also provide environment variables when launching the application.

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
