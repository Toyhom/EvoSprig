[English](../../tutorials/first-agent.md) · **简体中文** · [学习路线](README.md)

<a id="your-first-agent"></a>

# 你的第一个智能体

**目标：** 创建一个工作流，运行它，并在画布上更改其指令。你需要 Python 3.12+、Git；如果使用 Studio，还需要 Node.js 20+。

<a id="1-install-and-create"></a>

## 1. 安装并创建

在终端中运行以下命令：

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[models,server]'
python docs/tutorials/first_agent.py
```

最后一条命令会写入 `.evosprig/tutorial/agent.yaml`。打开 [first_agent.py](../../tutorials/first_agent.py)：`default_model("main")` 定义了共享的模型连接。助手会继承它；输出绑定会选择助手的文本。

<a id="2-run-the-workflow"></a>

## 2. 运行工作流

```bash
evosprig run .evosprig/tutorial/agent.yaml \
  --workspace .evosprig/tutorial-state \
  --input '{"question":"How do I start a reading habit?"}' --mock
```

你应该会看到 `status: succeeded`，以及一个以 `Mock:` 开头的 `answer`。首次运行会检查工作流，无需 API 账户。

如需真实响应，请创建 `.evosprig/tutorial/deployment.yaml`：

```yaml
models:
  main:
    base_url: https://api.deepseek.com
    model: deepseek-flash
    api_key_env: DEEPSEEK_API_KEY
```

在终端中设置 `DEEPSEEK_API_KEY`，如有需要替换提供商设置，然后带 `--profile .evosprig/tutorial/deployment.yaml` 且不带 `--mock` 重新运行。[模型连接字段](../model-connections.md)。

<a id="3-open-the-canvas"></a>

## 3. 打开画布

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project .evosprig/tutorial/agent.yaml \
  --workspace .evosprig/tutorial-studio --profile .evosprig/tutorial/deployment.yaml \
  --studio-dir apps/studio/dist --port 18766
```

打开 `http://127.0.0.1:18766`。选择助手，将 **Instructions** 改为“用一句话回答，然后给出今天可以尝试的一个小行动”，并保存。输入相同的问题，选择 **Live models**，然后再次运行。在 **History** 中比较这两个回答。

<a id="4-try-one-change"></a>

## 4. 尝试一项更改

只更改指令。保持问题和模型不变，这样你就能看到更改产生的作用。打开 **Python** 查看已保存应用程序的代码。

如果模型连接失败，请在启动 Studio 的同一终端中检查基础 URL、模型 ID 和环境变量。如果端口 18766 被占用，请通过 `--port` 选择另一个端口。

**下一步：** [在画布上构建一个漫画应用](comic-studio.md)。
