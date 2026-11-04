[English](../evaluation.md) · **简体中文** · [文档目录](README.md)

<a id="evaluate-the-application-you-want-to-build"></a>

# 评估要构建的应用

从用户实际交给智能体的任务开始。EvoSprig 接受仅输入任务、参考答案、工具要求、节点检查以及来自你自有环境的结果。评估器保持固定，而优化器更改选定的提示词或技能。

<a id="start-with-inputs-only"></a>

## 仅从输入开始

创建 `tasks.jsonl`，其中至少包含四个不同的 JSON 输入对象，且均与你的 AgentSpec 匹配。更大、更具代表性的集合可提供更有用的比较。

```jsonl
{"question":"Which customers account for most of our revenue?"}
{"question":"How did refunds affect October revenue?"}
{"question":"Which region has the strongest repeat purchases?"}
{"question":"Where should we investigate an increase in cancellations?"}
```

```bash
evosprig suite --inputs tasks.jsonl --name sales-tasks --out tasks.yaml \
  --rubric "Check calculations, business relevance and grounding in actual query results."
evosprig improve my-agent/agent.yaml --suite tasks.yaml \
  --method opro --resource instructions --rounds 2 \
  --profile deployment.yaml --max-model-calls 200
```

Studio 的 **Improve → Create from task inputs** 提供相同工作流。评分标准是可选的：默认标准涵盖任务完成、显式约束、事实依据和可用性。不需要参考答案。除非你配置单独模型，否则任务模型充当评判模型：

```yaml
evaluation:
  judges:
    critic:
      base_url: https://api.example.com/v1
      model: your-judge-model
      api_key_env: JUDGE_API_KEY
```

配置多个评判模型时，设置 `metric.judge_binding: critic`。评判调用共享实验的 token、时间和调用预算；报告会显示其单独用量。评判模型会看到任务、可选的参考/上下文、实际输出、人工节点处的问题和已给出的响应，以及工具/环境观测。以 `_base64` 结尾的字段在纯文本评判/反思中以大小和内容哈希表示；媒体必须通过工具观测或自定义多模态评分器进行评估。执行仍会收到原始负载。它不会看到候选名称、优化方法或不断演变的指令文本。`repeats: 2` 或 `3` 记录重复判断及其离散程度。

对于预订、仓库变更、SQL 或代码执行，将评判反馈与环境断言或自定义评分器结合使用。可用时使用独立评判模型。其置信度字段为自报。

<a id="judge-response-limits"></a>

### 评判响应限制

```yaml
metric:
  kind: llm_judge
  output_path: ""
  judge_max_output_tokens: 1400
  judge_max_retries: 1
```

默认允许对截断或格式错误的评估进行一次修复。将输出上限设置为 128 到 8192 个 token，并将重试次数设置为 0 到 3；Studio 在创建仅输入任务时会显示输出上限。身份验证和网络错误会直接传播。修复会保留原始任务和评分标准，消耗同一共享预算，并出现在评判回执中。没有提供商用量记录的调用仍保留其 token 预留。

<a id="bring-your-own-task-suite"></a>

## 使用自己的任务套件

`EvalSuite` 包含互不重叠的 `search`、`selection`、`release` 分区，以及可选的 `test` 分区。`suite` 会确定性地创建这些分区。你也可以在 YAML 中自行分配它们。搜索和选择可供优化器使用；发布和测试输入仍不在其上下文中。

一个样本支持：

```yaml
id: invoice-017
input: {invoice: "..."}
expected: {total: 125.50, balanced: true}
context: {currency: USD, expense_policy: "Meals need a receipt."}
rubric: "Flag missing dates instead of inventing them."
tags: [expense-policy]
required_tools: [calculate]
responses:
  graph/review:
    text: {from_input: draft}
```

`responses` 为无人值守评估提供显式的人工节点答案。`{from_input: draft}` 从该等待节点的输入中复制一个字段。未获答复的审批以及超过恢复限制的作业会被取消，并使任务失败；评估器绝不会假定审批已通过。

<a id="combine-checks-at-different-levels"></a>

## 组合不同层级的检查

| 指标 | 衡量内容 |
| --- | --- |
| `exact`、`contains` | 参考值或必需文本 |
| `tool_called` | 成功的工具回执 |
| `json_schema` | 选定结果的结构 |
| `llm_judge` | 固定评分标准下的任务质量，并附书面反馈 |
| `external` | 返回分数和反馈的具名部署评分器 |
| `composite` | 加权检查，可选带强制阈值 |

使用 `target: output`、`node`、`trajectory`、`tools` 或 `environment`。`output_path` 选择嵌套观测；将其设置为 `""` 可表示整个值。节点目标使用检查点路径，例如 `graph/analyze`。`reference_path` 选择样本的 `expected` 对象中的嵌套值。

```yaml
metric:
  kind: composite
  components:
    - kind: exact
      target: environment
      output_path: tests_passed
      reference_path: balanced
      required: true
      threshold: 1
    - kind: llm_judge
      output_path: ""
      weight: 2
      rubric: "Assess completeness and usefulness against the task."
```

必需项失败会将综合分数强制为零。执行失败或缺少必需的工具回执也会计为零分。在配置的修复尝试后评判 JSON 仍无效，或评分器绑定不可用，会引发评估错误。

<a id="connect-a-scorer-or-environment"></a>

## 连接评分器或环境

HTTP 评分器接收 `{sample, run, observations}` 并返回：

```json
{"score":0.8,"feedback":"Four of five business checks passed","confidence":1.0}
```

```yaml
evaluation:
  scorers:
    business:
      endpoint: https://evaluation.example.com/score
      auth_env: SCORER_TOKEN
  environment:
    documents:
      - {title: Policy, text: "...", source: "policy:v3"}
    facts: ["The customer prefers email."]
    memory_writes: true
```

使用 `kind: external, scorer: business`。评分器是部署绑定；数据集不能导入任意 Python。`memory_writes` 仅在每个样本的全新身份内启用原生内存写入工具。生产用户内存绝不会被复用于搜索。

对于交互式或带副作用的环境，将受信任的 SDK 对象传给实现 `EvaluationEnvironment` 的 `execute_study(environment=...)` 或 `Evaluator(environment=...)`：

```python
class Sandbox:
    allow_writes = True

    def __init__(self, session_factory):
        self.session_factory, self.sessions = session_factory, {}

    async def prepare(self, scope, sample, tools):
        session = await self.session_factory(scope)
        self.sessions[scope.user] = session
        await session.seed(sample.input)
        return session.tools

    async def observe(self, scope, sample, result):
        return await self.sessions[scope.user].check_result(result.output)

    async def cleanup(self, scope):
        session = self.sessions.pop(scope.user, None)
        if session:
            await session.close()

```

会话工厂属于你的环境适配器；其工具和检查必须提供真实的隔离和观测。仅靠作用域 ID 无法隔离远程支付服务或主机 shell。声明式 CLI/Studio 支持预置文档、事实、隔离内存写入和审批响应；任意外部写入沙箱使用 SDK 接口。

<a id="compare-the-outputs"></a>

## 比较输出

```bash
evosprig compare my-agent --study STUDY_ID --workspace .evosprig --out comparison.md
```

比较内容包含配对的任务输入、最终输出、分数、模型和版本标识符。它省略优化器对话和完整执行轨迹。共享导出文件前请先检查：应用输入和最终答案仍可能包含你自己的私有数据。Studio 也可以直接显示配对输出。

原始论文和实现映射：[研究参考](references.md)。
