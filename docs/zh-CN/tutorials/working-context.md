# 在多轮交互中延续工作上下文

[English](../../tutorials/working-context.md) · **简体中文**

用两个普通的**模型节点**搭建 `summarize → answer`：把旧对话提炼成摘要，再结合近期消息回答。整个流程不需要知识库，也不增加新的节点类型。

## 1. 创建流程

在已安装 EvoSprig 的项目目录中运行：

```bash
python docs/tutorials/working_context.py
```

[完整代码](../../tutorials/working_context.py)会生成 `.evosprig/working-context/agent.yaml`。应用输入为 `previous_summary`、`older_messages`、`recent_messages`、`question`。摘要节点输出结构化 JSON；回答节点只接收新摘要、未经修改的近期消息和当前问题。应用同时返回回答与摘要，供下一轮复用。

## 2. 配置模型并打开画布

创建 `.evosprig/working-context/deployment.yaml`：

```yaml
models:
  main:
    base_url: https://api.openai.com/v1
    model: your-answer-model
    api_key_env: MODEL_API_KEY
    capabilities: [text, structured_output]
  summary:
    base_url: https://api.openai.com/v1
    model: your-summary-model
    api_key_env: MODEL_API_KEY
    capabilities: [text, structured_output]
```

将地址和模型 ID 换成自己的 API 厂商或本地服务；两个连接可以使用同一个模型。

```bash
export MODEL_API_KEY='your-key'
evosprig serve --project .evosprig/working-context/agent.yaml \
  --workspace .evosprig/working-context/workspace \
  --profile .evosprig/working-context/deployment.yaml \
  --studio-dir apps/studio/dist --port 8000
```

在画布中点击 `summarize`，通过**设计**编辑提示词，通过**模型绑定**指定模型。输入映射连接旧消息与之前的摘要；`answer` 引用 `nodes.summarize.output.summary` 和原始近期消息。也可以从空白画布添加两个普通模型节点，完成相同连接。

## 3. 运行一轮对话

把下面的内容粘贴到**运行输入**，选择**真实模型**后运行：

```json
{
  "previous_summary": "用户正在准备一个小型团队工作坊。",
  "older_messages": [
    "用户：总费用不要超过800元。",
    "助手：可以预约周五的会议室。",
    "用户：改成周六，有六个人。"
  ],
  "recent_messages": ["用户：有一位参加者需要无台阶通行。"],
  "question": "我应该向场地方说明哪些要求？"
}
```

在运行记录中分别查看两个节点。回答应保留周六、六人、预算和通行要求。修改其中一条约束，再运行一次，检查摘要是否正确保留用户的修正。

## 4. 部署之后继续使用

从 Studio 导出 **HTTP service**。业务应用把 `output.summary` 存到当前会话，另外保留近期消息，在下一次请求时传入；不同用户的会话应分别保存。导出服务执行同一张图，后续对话不需要打开开发平台。[部署文档](../deployment.md)提供启动命令和 API。

这个两节点示例每次都会压缩。在完整应用中，可用普通**条件节点**判断是否达到开发者设置的上下文阈值；达到时调用摘要，未达到时用**数据映射节点**传递原摘要。为近期消息和回答预留空间。超长历史应分窗口逐次摘要，因为执行摘要的模型本身也有上下文上限。

对于智能体内部的多轮工具调用，**节点设置 → 记忆 → 配置上下文策略 → 限制工具历史长度**可以直接缩短旧工具结果，不增加模型调用。它保留近期轮次与完整运行记录；这是截短，不是语义压缩。长期事实、经验和工作上下文块见[智能体记忆](../memory.md)。
