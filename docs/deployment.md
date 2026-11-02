# 自托管与工程部署

平台和导出应用分别部署。平台负责编辑、评测和版本管理；导出应用固定一个版本，可以独立运行。

## 平台

```bash
python -m pip install -e '.[server,evolution,mcp]'
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --workspace ./state --project examples/hello/agent.yaml --studio-dir apps/studio/dist --max-concurrent-runs 4
```

默认绑定 `127.0.0.1:18766`，通过 SSH 转发访问。`--profile deployment.yaml` 绑定模型和工具。使用 `--token-env EVOSPRIG_API_TOKEN` 配置单工作区令牌，在 Studio 连接页输入相同值。多人部署使用 `--auth-file principals.yaml`：

```yaml
- user: alice
  tenant: team
  token_env: EVOSPRIG_ALICE_TOKEN
- user: bob
  tenant: team
  token_env: EVOSPRIG_BOB_TOKEN
```

每个令牌由服务进程环境提供，项目/运行/记忆/候选按 principal 隔离。`--project` 导入到默认 local 身份；使用多用户鉴权时，各用户应在 Studio 中导入或创建自己的项目。不要把令牌写进规格、源码或工程导出。

进程由你的服务管理器负责重启。停止时 worker 释放或保存检查点，启动后扫描可恢复任务；失去租约的写入结果按运行协议处理。运行和进化各自使用有界 worker；并发参数控制普通运行数量。Alpha 的数据库调用为同步 SQLite，多进程压力、数据库替换、背压、公平调度与集群部署进入后续性能专项。

工作目录保存项目、运行、记忆、删除账本、study 和版本数据库。数据库与锁需要随机写文件系统；视频与大产物可放对象存储。备份时停止本平台进程或使用 SQLite backup API，保存所有相关数据库，尤其独立删除账本。恢复前保留最新删除账本，不要以旧备份覆盖它。模型/工具凭据从环境重新注入。

## 固定应用

```bash
evosprig export examples/hello/agent.yaml --target python --out ./hello-python
evosprig export examples/hello/agent.yaml --target http --out ./hello-http
evosprig export examples/hello/agent.yaml --target container --out ./hello-container
```

有 HTTP/MCP/外部 job 工具时增加 `--profile deployment.yaml`。导出包内 `export-report.json` 列出外部依赖，`manifest.json` 给出文件哈希，`agent.lock.json` 固定行为版本。Python 源码随包携带；权重、密钥和历史不打包。自定义插件无导出适配时返回不兼容报告。

在新的 Python 3.12 环境安装并运行：

```bash
cd hello-http
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
# Set EVOSPRIG_SERVICE_TOKEN in your shell, then:
python serve.py --mock --workspace ./state
```

HTTP 服务默认 loopback 8080；所有业务请求需要 `Authorization: Bearer <token>`。`POST /runs` 接受 `{"input": {...}}` 并返回 ID；查询 `/runs/{id}`，读取 `/events`，以 `/input` 提交人工输入，或 POST `/cancel`。公共 `/health` 仅返回状态与版本。每个导出版本使用独立工作目录。服务适用于单应用共享信任域；远程公开部署加 TLS 代理并设置访问控制。

容器目标生成 Dockerfile，运行用户为 UID 10001，持久目录为 `/state`。构建与启动命令见工程 README。基础 Python 镜像固定 tag；部署时可进一步固定 digest。容器依赖 Docker/OCI 构建环境，导出不会自动启动容器。

## 重新导入

Studio 的「导入工程 ZIP」先展示校验结果与依赖，再创建新项目；外部服务绑定由部署操作者提供。CLI：

```bash
evosprig import hello.zip
evosprig import hello.zip --out ./imported-project
```

CLI 接受最多 20 MB / 500 个文件，API 限制 2 MB；拒绝越界路径、符号链接、重复文件、清单不符与未知插件。导入只保存规格与资源，忽略可执行源码。若主动修改 Builder，请先在可信环境执行它生成新规格，再验证并导出；修改后的工程需要重新生成版本锁和清单。
