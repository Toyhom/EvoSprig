# Alpha validation

本记录对应本地 `0.1.0a1` 发行候选，2026-11-02。源码、wheel/sdist 和独立应用均在 Linux x86_64 / Python 3.12 验证；Studio 使用 Node.js 20。

| 场景 | 证据与范围 |
| --- | --- |
| Python 契约 | 113 项通过（71.62 秒）；规格、运行、租约/崩溃恢复、权限、记忆删除、预算、进化、发布 CAS、导出和导入 |
| Studio | 5 条 Playwright 流程通过；包含条件边哈希往返、人工恢复、资源与记忆、改进/候选、ZIP 导入和容器目标下载、冲突保留、桌面/移动页面 |
| MCP | 官方 SDK 1.30.0 / 2025-11-25，真实本机 Streamable HTTP 服务与独立工程调用 |
| DeepSeek | 官方 deepseek-flash；文本、JSON、工具、流式；两种真实进化方法与人工基线 |
| vLLM | 0.10.2 + Qwen3-0.6B / H100，4 次请求：文本、JSON、流式、运行器，共 83 输入 / 14 输出 tokens；[脱敏记录](vllm-validation.json) |
| 短片 | 1 次 DeepSeek 请求，364 输入 / 96 输出 tokens；18 秒，3 镜头；CLI 退出后恢复同一 job，1 次渲染；无密钥重放产生相同 SHA-256 |
| 干净安装 | 全新环境安装 wheel 与 server/evolution/mcp extras，创建项目、运行 mock、导出 HTTP 工程 |
| 独立服务 | 导出运行源码和依赖安装在独立环境；鉴权、后台运行、事件与持久结果，不依赖 Studio/进化模块 |
| 制品边界 | 源码与 wheel/sdist 扫描，明确文件白名单、凭据特征检测，版本化导出与 SHA-256 清单 |

vLLM 验证沿用既有安装；0.10.2 的 NVML 设备查找不支持调度器提供的 UUID，因此测试进程加载了局部 UUID→NVML index 兼容映射，CUDA 可见设备保持不变。权重从已有对象存储加载，未打包到产品。该验证不包含 vLLM 工具调用或吞吐基准。

真实进化结果在 [研究助手](../examples/research-assistant/README.md)：原始/人工/OPRO/GEPA 共 70 次调用，50,442 输入 / 2,134 输出 tokens。两种方法 release 达到 2/2；sealed test 原始和候选均为 2/2，人工基线也是 2/2。仅用于工程 smoke 验证，未证明泛化收益或优于人工。未自动发布候选。真实模型记录来自开发快照，最终示例导出使用发行候选运行时重新锁定相同提示资源。

视频为模型分镜与 CPU 程序渲染，无声音、外部素材或神经视频生成；自动演示审核明确标注。容器 Dockerfile 已生成并验证内容，当前服务器没有 Docker/Podman，未在此处构建或运行 OCI 镜像。外部开发者试用、公开演示上传和包注册表发布由项目负责人另行安排。

复现：`pytest -q`；`npm --prefix apps/studio test`；`python scripts/release/export_examples.py --out <new-directory>`；`python scripts/release/package.py --out <artifacts-directory>`。真实 API 调用需要自己的凭据，普通测试不产生模型费用。

## Studio redesign follow-up · 2026-11-02

DEV-018 introduces the neutral Studio interface, project search, informative workflow cards and a keyboard-accessible mobile drawer. TypeScript/Vite build passes; JS is about 134.88 kB gzip. Existing dependencies and Python runtime are unchanged.

The six-scenario browser regression passed in 121.43 seconds. Visual inspection then confirmed desktop/mobile canvas, mobile navigation and version comparison. A final node-draft fallback was checked with the two workflow regressions and an additional unsupported-kind recovery scenario. That new test initially expected the invalid value in a deliberately sanitized API error; it now checks the validation category and passed in a focused rerun. Seven distinct browser scenarios have passed across these runs. Width checks cover 1440, 1024, 390 and 320 pixels, with a node-visibility check after canvas resize. This is targeted keyboard/responsive validation, not a full accessibility audit.

The earlier Alpha archives retain their original contents. Build the latest Studio from this source revision; the Python validation above remains the unchanged Alpha baseline. Design rationale and official reference links are in [Studio interface](studio-design.md).
