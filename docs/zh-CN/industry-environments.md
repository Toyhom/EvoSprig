[English](../industry-environments.md) · **简体中文** · [文档目录](README.md)

<a id="build-industry-agents-with-their-own-working-environment"></a>

# 构建拥有自有工作环境的行业智能体

行业智能体需要的不仅是问题和答案。它可能需要读取申请、检查政策、更新记录并请求审批。EvoSprig 将环境构建、业务工具和基于结果的评估连接起来，让你能够开发整个工作流程。

![行业环境构建与智能体开发](../../examples/industry-environment-builder/assets/overview.svg)

选择你的起点：

- **你已有经过验证的 IndustryBench 环境：** [准备智能体和任务套件](#use-an-existing-environment)。
- **你需要新的业务流程：** [起草其环境](#construct-a-new-environment)，实现并验证它，然后准备智能体。
- **你有另一个模拟器：** 实现[评估环境协议](evaluation.md#connect-a-scorer-or-environment)。

<a id="use-an-existing-environment"></a>

## 使用现有环境

安装你的 IndustryBench 发行版，或将 `INDUSTRYBENCH_ROOT` 设置为其包根目录。它提供 `industrybench.session`、`industrybench.registry`、`industrybench.evaluation`、领域引擎和冻结用例。

```bash
export INDUSTRYBENCH_ROOT=/path/to/industry-agent
evosprig industry prepare --industry government --limit 12 --out my-industry-agent
```

选择 `finance`、`government` 或 `manufacturing`。该命令会创建：

| 文件 | 用途 |
| --- | --- |
| `agent.yaml` | 原生工具调用智能体 |
| `prompts/procedure.md` | 可编辑并进化的操作说明 |
| `suite.yaml` | 互不重叠的搜索、选择和发布任务 |
| `deployment.yaml` | 模型、业务工具和环境设置 |

智能体看到用例、公开流程和工具 schema。参考答案保留在评估器处。每个任务都会创建全新沙箱；记录的操作会针对固定业务检查进行回放。

<a id="evaluate-then-improve"></a>

## 评估，然后改进

设置 `deployment.yaml` 中引用的模型凭据：

```bash
evosprig evaluate my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml \
  --profile my-industry-agent/deployment.yaml

evosprig improve my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml \
  --profile my-industry-agent/deployment.yaml \
  --method reflexion --resource procedure --rounds 2 \
  --max-evaluations 100 --timeout 1800
```

优化器提出指令修改，执行智能体，并使用环境的结果来选择候选。在启用某个版本之前，请比较编辑内容和结果。[选择另一种进化方法](evolution.md)。

对于画布，启动同一项目和配置：

```bash
evosprig serve --project my-industry-agent/agent.yaml \
  --profile my-industry-agent/deployment.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/industry
```

使用生成的套件执行 **Improve**。行业沙箱由评估分配；普通 **Run** 在没有评估会话的情况下执行工作流程。

<a id="construct-a-new-environment"></a>

## 构建新环境

[环境构建器](../../examples/industry-environment-builder)将业务简报转化为七项相互关联的输出：

**上下文 → schema → 流程 → 工具图 → 数据 → API → 实现草稿 → 人工审查。**

```bash
evosprig industry synthesis --templates /path/to/industry-agent/synthesis \
  --scene government --out environment-builder

evosprig serve --project environment-builder/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/industry-builder
```

例如，提交：

```json
{"brief":"Build a benefits application process with eligibility checks, exception review and a recorded final decision."}
```

模板场景包括 `loan`、`account`、`credit_cards`、`deposit`、`invest`、`government` 和 `manufacturing`。每个阶段都是一个模型节点，具有可编辑的提示词和有界输出。生成的项目默认使用七次模型调用、每次调用 8,192 个输出 token、总预算 200,000 个 token；请根据你的领域在项目中调整这些设置。

审查后，将实现草稿与环境引擎集成。运行其参考工具和验证工具，然后冻结用例和业务答案。这个经过验证的安装会成为 `industry prepare` 的输入。

<a id="business-tool-interface"></a>

## 业务工具接口

| 工具 | 智能体操作 |
| --- | --- |
| `industry.materials` | 读取用例和操作流程 |
| `industry.search` | 发现相关工具 schema |
| `industry.invoke` | 在活动沙箱中调用已发现的工具 |

调用使用记录到日志的幂等键。每个会话拥有自己的引擎线程，用于创建、调用和清理，包括与线程绑定的数据库。最终检查使用记录的业务结果。

<a id="tune-task-size-and-budgets"></a>

## 调整任务规模和预算

`industry prepare` 将大约一半的用例分配给搜索，并预留两个用于发布；其余用例选择候选。至少需要四个用例。请使用具有代表性的任务套件做出发布决策。

| 设置 | 默认值 | 用途 |
| --- | --- | --- |
| 智能体 `max_tool_rounds` | 192 | 每个用例的工具使用轮次 |
| 智能体 `max_model_calls` | 200 | 共享预算内的模型调用上限 |
| `evaluation.industry.search_limit` | 8 | 一次工具搜索返回的 schema 数 |
| `evaluation.industry.max_calls` | 256 | 业务工具调用上限 |
| `evaluation.industry.timeout_seconds` | 30 | 每次业务工具调用的超时时间 |
| `evaluation.environment.max_concurrent_samples` | 1 | 独立评估会话数 |

`evaluation.industry.allowed_cases` 限制可访问的用例。沙箱写入权限适用于模拟业务操作。生成的配置包含所有选定的用例 ID，套件将三个评估划分保持独立。

[行业助手](../../examples/industry-assistant) · [环境构建器](../../examples/industry-environment-builder) · [评估指南](evaluation.md)
