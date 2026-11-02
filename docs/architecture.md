# Architecture

EvoSprig 将 AgentSpec、资源快照和运行协议作为代码、画布、进化与导出的共同边界。Python 发行单元为 `src/evosprig`，Studio 是独立构建的 React 应用。

| 模块 | 职责 |
| --- | --- |
| core | 规格、版本、模型/工具/存储协议、状态图、预算、操作日志 |
| sdk | 显式声明式 Python Builder |
| plugins | 兼容 API、HTTP/MCP/异步 job、SQLite、记忆与词法检索 |
| evaluation | 固定数据划分、样本结果、指标、共享计费 |
| evolution | OPRO、官方 GEPA 适配、资源白名单、验证与发布门槛 |
| exporters | 能力检查、工程收集、固定版本、ZIP 导入校验 |
| server | API、身份作用域、有界 worker、SSE、独立服务入口 |
| apps/studio | 画布、规格、代码、资源、运行、记忆、改进、版本 |

core 不依赖具体 HTTP、数据库、优化器或 UI；依赖边界由自动测试检查。基础包只依赖 Pydantic、jsonschema、PyYAML，额外能力使用 extras。

AgentSpec 0.1 保持可读兼容，0.2 添加条件、转换、循环、并行、汇合和人工节点。图上的显式循环由有界 loop 节点承载；任意拓扑回边仍被拒绝。布局不参与行为哈希。版本锁包括规范化规格、资源哈希、插件版本与运行时版本；编辑草稿不会改变已开始的运行或已发布版本。

运行器先写 intent 再执行外部操作。完成结果、外部 job ID、模型调用预算和人工输入持久保存在 SQLite。租约和 fencing 防止旧 worker 覆盖新结果；不确定写入等待查询或人工处理。模型请求没有 usage 回执时保留预留额度。详细语义见 [durable-runtime.md](durable-runtime.md)。

记忆键包括 tenant/user/project/role/namespace。文档检索采用词法匹配并保留来源与字符区间。独立删除账本在恢复旧备份时继续过滤已删除记录；恢复时必须同时保留它，见 [memory.md](memory.md)。

进化 worker 只能修改已授权的文本资源并使用 search/selection 数据；release/test 在搜索完成后独立运行。任务与提议模型共享预算，保留验证额度。候选和样本结果不可变；发布使用 revision 比较更新，回滚检查数据契约。进化中断保留费用与结果，标记 interrupted，不自动重跑搜索。

主服务采用 SQLite 与有界 asyncio worker，适合单机受信任部署。API 只允许 loopback Host/同源浏览器访问，可绑定 bearer token 或服务端 principal。请求体提供的用户身份不参与授权。Studio 使用保存后的 revision，冲突时保留本地编辑。

导出默认只包含选定规格、资源、最小运行源码和依赖锁，不含业务数据。HTTP/容器目标增加单应用服务和持久 worker。导入器检查压缩包路径、大小、文件清单和哈希，仅读声明式数据，不执行归档中的 Python。完整平台的多 worker、数据库后端与部署性能路线见 [roadmap.md](roadmap.md)。
