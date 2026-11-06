# 桌面版 Studio

在桌面窗口中使用画布、代码视图和应用导出。EvoSprig 自动启动本地后端，项目、知识库和记忆保存在自己的工作区中。

[English](../desktop.md) · [Studio 指南](studio.md) · [教程](tutorials/README.md)

## 安装

从 [GitHub Releases](https://github.com/Toyhom/EvoSprig/releases/tag/v0.1.8) 下载安装包，无需登录 GitHub。

| 系统 | 下载 | 安装方法 |
| --- | --- | --- |
| Windows x64 | [安装程序](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-win-x64.exe) | 运行 `.exe`。 |
| macOS Apple 芯片 | [DMG](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-mac-arm64.dmg) | 拖入应用程序。 |
| macOS Intel | [DMG](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-mac-x64.dmg) | 拖入应用程序。 |
| Linux x64 | [AppImage](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-linux-x86_64.AppImage) · [DEB](https://github.com/Toyhom/EvoSprig/releases/download/v0.1.8/EvoSprig-Studio-0.1.8-linux-amd64.deb) | 为 AppImage 添加执行权限，或安装 DEB。 |

安装包包含 Python、本地后端和网页界面。本地模型服务和应用需要的外部工具单独安装。安装程序尚未签名；macOS 首次打开时，可在“隐私与安全性”中使用针对该应用的“仍要打开”。

## 创建第一个项目

1. 启动 **EvoSprig Studio**，在侧栏输入项目名，点击 **+**。
2. 选择 **文件 → API 密钥**，填写 `MODEL_API_KEY` 这样的变量名及密钥，再从文件菜单重启本地后端。
3. 展开侧栏的 **模型连接**，选择厂商、填写模型 ID，并使用相同的密钥变量名，保存连接。
4. 在 **应用默认模型** 中选中该连接；有需要时，各节点可以单独覆盖。
5. 保存项目，将 **离线演示** 切换为 **真实模型**，点击运行。

密钥通过操作系统密钥存储加密保存。Linux 未提供密钥存储时，密钥只保留在当前应用进程的内存中。也可以在启动应用时传入环境变量。

## 模型与应用独立部署

开发时只需给节点选择模型角色及能力，通常共用一个默认模型，特殊节点可以单独设置。部署者在工作区的 `deployment.yaml` 中统一绑定具体模型：本机推理服务、自己服务器上的 API 或云端 API 都使用相同的 OpenAI 兼容聊天协议。

导出包提供 `model-contract.json`，列出应用需要的角色、能力和接口。可以先部署应用，再启动模型并填写连接。更换模型服务只改部署配置，无需修改或重新导出智能体。最终用户通过应用界面或业务 API 提交任务，不需要配置每个节点的模型或密钥。

无密钥本地服务取消勾选 **服务需要 API 密钥**；自建 HTTP 服务勾选 **允许自建服务器使用 HTTP**。本机服务可关联预加载配置、指定 GPU，并跨任务保持常驻。推理引擎和模型权重由部署者准备，桌面安装包包含开发工作台和运行时。

完整配置见[模型连接](model-connections.md#应用与模型解耦)与[本地模型](local-models.md)。

## 工作区与文件

**文件 → 打开工作区** 可以选择项目目录，保存部署配置、运行记录、文档索引和记忆。**打开工作区文件夹** 可在系统文件管理器中查看文件。客户端会记住上次的工作区与窗口大小。

默认工作区位于应用数据目录：

- Windows：`%APPDATA%/EvoSprig Studio/workspace`
- macOS：`~/Library/Application Support/EvoSprig Studio/workspace`
- Linux：`${XDG_CONFIG_HOME:-~/.config}/EvoSprig Studio/workspace`

**导入工程** 打开已有的工程 ZIP。顶部工具栏可导出 Python、HTTP 服务或容器工程；ComfyUI 工程还可导出工作流 JSON。导出后的应用可以独立部署和运行。

桌面版与网页版使用相同的工作区文件，可以切换使用；同一个工作区同时只启动一个后端。退出桌面应用会停止它的后端；macOS 关闭窗口后会保留会话，可从 Dock 再次打开。模型服务仍按持久化配置保持常驻，可在 Studio 中显式停止。

## 从源码构建

准备 **Python 3.12+** 和 **Node.js 22.12+**，在需要分发的系统和 CPU 架构上构建。

```bash
python -m venv .venv
# Linux/macOS：source .venv/bin/activate
# Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install '.[server,models,mcp,documents,artifacts,evolution]' pyinstaller==6.16.0
npm ci --prefix apps/studio
npm run build --prefix apps/studio
npm ci --prefix apps/desktop
npm start --prefix apps/desktop
```

Python 不在当前环境时，可通过 `EVOSPRIG_PYTHON` 指定解释器。生成安装包：

```bash
python apps/desktop/scripts/build_backend.py
npm run dist --prefix apps/desktop
```

安装包写入 `apps/desktop/dist`。桌面构建流程在各系统的原生运行器上构建，并检查创建项目、离线运行、导出和密钥设置。准备签名版本时，可配置 electron-builder 的 `CSC_LINK` / `CSC_KEY_PASSWORD` 及 Apple 公证变量。
