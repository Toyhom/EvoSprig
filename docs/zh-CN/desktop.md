# 桌面版 Studio

在桌面窗口中使用画布、代码视图和应用导出。EvoSprig 自动启动本地后端，项目、知识库和记忆保存在自己的工作区中。

[English](../desktop.md) · [Studio 指南](studio.md) · [教程](tutorials/README.md)

## 安装

打开最近一次成功的 [Desktop clients 构建](https://github.com/Toyhom/EvoSprig/actions/workflows/desktop.yml)，下载对应系统的附件。下载 GitHub 构建附件需要登录账号。

| 系统 | 附件 | 安装方法 |
| --- | --- | --- |
| Windows x64 | `EvoSprig-Studio-win-x64` | 解压后运行 `.exe` 安装程序。 |
| macOS Apple 芯片 | `EvoSprig-Studio-mac-arm64` | 打开 `.dmg`，将 EvoSprig Studio 拖入应用程序。 |
| macOS Intel | `EvoSprig-Studio-mac-x64` | 打开 `.dmg`，将 EvoSprig Studio 拖入应用程序。 |
| Linux x64 | `EvoSprig-Studio-linux-x64` | 安装 `.deb`，或给 AppImage 添加执行权限后运行。 |

安装包包含 Python、本地后端和网页界面。本地模型服务和应用需要的外部工具单独安装。当前开发构建没有签名；macOS 首次打开时，可在“隐私与安全性”中使用针对该应用的“仍要打开”。

## 创建第一个项目

1. 启动 **EvoSprig Studio**，在侧栏输入项目名，点击 **+**。
2. 选择 **文件 → API 密钥**，填写 `MODEL_API_KEY` 这样的变量名及密钥，再从文件菜单重启本地后端。
3. 展开侧栏的 **模型连接**，选择厂商、填写模型 ID，并使用相同的密钥变量名，保存连接。
4. 在 **应用默认模型** 中选中该连接；有需要时，各节点可以单独覆盖。
5. 保存项目，将 **离线演示** 切换为 **真实模型**，点击运行。

密钥通过操作系统密钥存储加密保存。Linux 未提供密钥存储时，密钥只保留在当前应用进程的内存中。也可以在启动应用时传入环境变量。

## 工作区与文件

**文件 → 打开工作区** 可以选择项目目录，保存部署配置、运行记录、文档索引和记忆。**打开工作区文件夹** 可在系统文件管理器中查看文件。客户端会记住上次的工作区与窗口大小。

默认工作区位于应用数据目录：

- Windows：`%APPDATA%/EvoSprig Studio/workspace`
- macOS：`~/Library/Application Support/EvoSprig Studio/workspace`
- Linux：`${XDG_CONFIG_HOME:-~/.config}/EvoSprig Studio/workspace`

**导入工程** 打开已有的工程 ZIP。顶部工具栏可导出 Python、HTTP 服务或容器工程；ComfyUI 工程还可导出工作流 JSON。导出后的应用可以独立部署和运行。

桌面版与网页版使用相同的工作区文件，可以切换使用；同一个工作区同时只启动一个后端。关闭桌面应用会停止它的后端。模型服务仍按持久化配置保持常驻，可在 Studio 中显式停止。

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
