# M0 architecture

`src/evosprig` 作为一个发行单元，按模块保持依赖边界。

| 模块 | 职责 |
| --- | --- |
| core | 规格、资源快照、插件协议、DAG 与工具循环、预算、事件 |
| sdk | 显式 Python Builder |
| plugins | 兼容 API、离线模型、内置工具、SQLite 项目存储 |
| exporters | 目标兼容检查、声明式代码生成、Python 工程收集 |
| server | FastAPI、单工作空间项目、后台运行、SSE、画布投影 |
| apps/studio | React/TypeScript/React Flow 开发入口 |

core 的契约测试检查依赖方向。基础包依赖 Pydantic、jsonschema、PyYAML；HTTPX 与 FastAPI/uvicorn 通过 extras 安装。

## 规格与版本

`spec/agent-spec-0.1.schema.json` 由 Pydantic 模型生成，CI 检查二者一致。JSON Schema 描述结构；图的可达性、引用依赖、能力和资源路径由 Python 编译器补充校验。`spec_version` 与插件版本必须匹配已实现的契约。

规格规范化按键排序，边按 source/target 排序。画布坐标保存为独立 layout。AgentVersion 固定规范化规格、资源 SHA-256、插件版本与运行时版本。运行持有不可变 JSON 快照，后续文件编辑不会修改在途版本。

资源只从项目根目录内解析，拒绝越界路径、越界符号链接、私有目录和凭据特征。输入格式读取使用安全 YAML，不执行构建脚本。用户显式运行 `build_agent.py` 时才执行 Python Builder。

## 执行与事件

DAG 节点按拓扑序依次运行。model 节点执行一次模型请求；tool 节点执行一次已注册只读工具；agent 节点维护消息与工具观察循环，受总运行预算限制。JSON 输出经输出 schema 校验。

事件包含 run_id、固定 agent_version、node_id、单调 sequence、时间与调用关联 ID。记录模型身份、采样温度、输出限额和已知用量；事件不保留私有推理内容、密钥、原始 provider 错误体或完整工具参数。最终任务输出作为私有运行数据由调用者或工作空间存储保管。

服务将项目、运行状态和事件放 SQLite，数据库目录由 `--workspace` 指定。SQLite、锁和运行环境要求适合随机写入的文件系统；大型文件应放独立对象存储，后续 Artifact 协议记录引用。

## API

`/api/projects` 创建/列出项目；`PUT /api/projects/{id}` 携带 revision。`/canvas` 和 `/code` 获取同一已保存版本的视图。`POST /api/projects/{id}/runs` 返回 run_id，`GET /api/runs/{id}` 查询状态，`/events` 通过 SSE 和 Last-Event-ID 补读，`/cancel` 请求取消。`POST /api/projects/{id}/export` 下载源码 ZIP。

当前服务只接受 loopback Host 和同源浏览器请求，可额外启用 bearer token。已有项目资源由 CLI 导入到工作空间；M0 Web 编辑器编辑规格与资源引用，资源文件通过本地工程管理。

## Export and release

Python 导出使用明确的模块清单，包含可独立安装的运行源码。导出前检查目标与插件，输出 manifest 固定文件内容；重复导出具有相同清单。客户端默认配置仅保存凭据环境变量名。

产品源码扫描脚本和 Python 构建白名单分别控制源码范围与分发范围。Python wheel/sdist 包含运行包及所需公共文档；Studio 从产品源码单独构建。当前项目尚未向公共注册表发布。
