# Quickstart · 快速开始

Python 3.12+；Studio 源码构建需要 Node.js 20+。

## 安装与离线运行

在产品仓库中执行：

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
evosprig validate examples/hello/agent.yaml
evosprig run examples/hello/agent.yaml --mock --input '{"question":"Hello EvoSprig"}'
```

示例先用 Python 工具统计输入，再把问题和统计结果交给模型。`--mock` 返回确定性离线输出，事件中模型身份为 `mock/offline`。生成同一规格：

```bash
python examples/hello/build_agent.py
```

应用用户安装基础包即可使用规格、Builder 和离线运行器；`.[models]` 增加兼容 API，`.[server]` 增加本地 API，`.[evolution]` 安装 GEPA，`.[mcp]` 安装 MCP SDK，`.[media]` 安装短片渲染依赖。开发锁文件包含测试工具。

## 真实模型

默认连接为官方 `https://api.deepseek.com`，模型为 `deepseek-flash`。在当前终端提供密钥：

```bash
read -rsp 'DeepSeek API key: ' DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
printf '\n'
evosprig run examples/hello/agent.yaml --profile examples/deployment.example.yaml --input '{"question":"What is 2 + 3?"}'
unset DEEPSEEK_API_KEY
```

规格保存逻辑模型引用；部署 profile 保存端点、模型名、能力和凭据环境变量名。其他兼容服务使用独立 profile。DeepSeek 示例关闭 thinking；供应商专用参数位于 `options`。适配器验证 HTTPS，允许 loopback HTTP 推理服务，不跟随重定向，不自动重试。

`scripts/live_smoke.py --report <path>` 是单独的付费验证入口，需要 `DEEPSEEK_API_KEY`。最多调用 6 次、生成 704 tokens，验证文本、JSON、工具调用、工具结果、流式输出与完整运行。基础 CI 使用 mock。

## Studio

```bash
cd apps/studio
npm ci
npm run build
cd ../..
evosprig serve --workspace ../local-data/studio --project examples/hello/agent.yaml --studio-dir apps/studio/dist
```

打开 `http://127.0.0.1:8765`。远程开发可在本机建立 SSH 端口转发，再通过本机 loopback 地址打开。CLI 固定绑定 loopback。

1. 选择示例或新建项目。拖动节点、连接端口，点击节点编辑参数。
2. 在「规格」编辑输入输出、工具、资源引用、入口和执行预算。新增图节点后建立显式连线；校验会拒绝循环、断开的图和未知引用。
3. 保存后运行离线演示。真实模型模式使用启动服务的进程环境和 `--profile`，界面无需保存模型密钥。
4. 在资源页编辑提示，在改进页选择数据划分、可修改资源、方法和预算。
5. 对比候选，在版本页手动启用或回滚；选择 Python、HTTP 或 Container 导出。
6. 运行历史支持人工输入、恢复与取消，记忆页管理当前用户项目的事实和资料。

revision 冲突返回 HTTP 409，页面保留本地修改。复制本地规格后重新加载比较。布局变化不改变规格哈希。「Python」页显示已保存版本的 Builder 代码。

可用 `--token-env EVOSPRIG_API_TOKEN` 为 API 添加 bearer token；在 Studio「连接」中输入相同令牌。它仅保存在页面内存。多用户身份配置、持久目录和备份说明见 [部署文档](deployment.md)。

前端热更新：另启 `npm run dev`，代理到默认 API 端口 8765。

## 独立导出

```bash
evosprig export examples/hello/agent.yaml --out ../local-data/hello-export
cd ../local-data/hello-export
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
```

请在独立 Python 环境执行最后三步。导出包包含可读 Builder、AgentSpec、资源、版本锁、依赖锁、最小运行源码和 SHA-256 文件清单。运行时检查固定版本；修改资源后重新导出生成新版本。实际服务凭据在目标机器配置。

当前导出支持 Python、HTTP 服务和容器构建工程；内置工具、记忆、HTTP、MCP 和异步 HTTP job 可移植。自定义工具可通过 SDK 注册（见 `examples/custom_tool.py`）；包含未提供导出支持的插件或请求 TypeScript 等未实现目标时，导出器给出不兼容项。

## 本地验证

```bash
ruff check src tests examples scripts
pytest -q
python -m build
python scripts/release/audit.py --artifacts dist
```

浏览器测试在 `apps/studio` 执行 `npx playwright install chromium --only-shell` 和 `npm test`。测试自动启动 18765 端口的临时服务并在结束时关闭，使用 mock。通过 `EVOSPRIG_PYTHON` 和 `EVOSPRIG_TEST_WORKSPACE` 指定解释器与测试数据库目录。
