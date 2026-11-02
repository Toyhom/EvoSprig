# 支持矩阵 · 0.1.0a1

状态以契约测试与真实示例记录为依据。Alpha 面向单机自托管。

| 能力 | 实现与验证范围 |
| --- | --- |
| Builder / YAML / JSON Schema / 画布 | AgentSpec 0.1/0.2；布局与行为哈希独立，代码/画布往返 |
| 状态图 | model、tool、agent、condition、transform、join、loop、parallel、human |
| 持久运行 | SQLite 检查点、租约/fencing、写入 intent、未知结果处理、外部 job ID、取消与人工恢复 |
| 预算 | 步数、模型调用、tokens、时间；并发先预留再结算，缺失 usage 保留预留 |
| 模型 | OpenAI-compatible；真实 DeepSeek Flash 文本/JSON/工具/流式/运行；真实 vLLM 0.10.2 + Qwen3-0.6B 文本/JSON/流式/运行（未验证工具调用） |
| 工具 | Python 契约、HTTP、OpenAPI 3 静态路径 JSON 子集、异步 HTTP job；MCP SDK 1.30.0 / 协议 2025-11-25 Streamable HTTP |
| 记忆与资料 | tenant/user/project/role/namespace 隔离，独立删除账本，词法检索与字符位置引用 |
| 评测 | search/selection/release/test 划分；exact、contains、tool_called 指标，逐样本用量与事件 |
| 进化 | 原生轻量 OPRO；官方 GEPA 0.1.4 adapter；资源白名单、共享预算和独立发布验证 |
| 版本 | 不可变快照、候选 diff、release revision CAS、显式启用与兼容回滚 |
| Studio | 中英界面、图编辑、规格/代码、资源、历史/人工恢复、记忆、改进、版本与 ZIP 导入 |
| 导出 | Python、HTTP 服务、容器 Dockerfile；固定版本、源码、依赖锁、文件清单 |
| 导入 | 限量 ZIP，路径/符号链接/重复/哈希/插件校验；不执行归档源码 |
| 研究助手 | 真实 DeepSeek、人工基线、OPRO、GEPA；9 个原创 smoke cases，测试集未见提升 |
| 视觉示例 | 18 秒 / 3 镜头；真实模型分镜 + Pillow/FFmpeg 程序渲染，真实 job 恢复 |

真实金额未知，按供应商账单结算。同步 Python 工具在线程中运行，超时不保证终止线程；写入需幂等与恢复契约。模型流式接口可独立使用，状态图运行器当前等待完整响应。

当前未实现：原生 TypeScript 执行、MCP Server 导出、神经图像/视频生成适配器、外部记忆平台、更多进化方法、平台 PostgreSQL/多节点部署。容器目标提供构建配方；当前共享服务器无 Docker/Podman，镜像构建留给支持 OCI 的部署环境和 CI。独立 HTTP 服务在本地测试与干净环境运行验证。

开发验证平台：Linux x86_64，Python 3.12（持久环境 3.12.16），Node.js 20.17.0。其他平台依后续 CI 扩展。
