[English](../optimizer-plugins.md) · **简体中文** · [文档目录](README.md)

<a id="add-an-evolution-algorithm"></a>

# 添加进化算法

实现一个接收 `EvolutionContext` 和 `StudyConfig` 的异步函数，然后注册它。EvoSprig 提供候选版本、任务执行、评分、预算和发布验证。

<a id="minimal-optimizer"></a>

## 最小优化器

```python
from evosprig.evolution import register_method

async def concise_search(context, *, config):
    selected = context.seed
    best = await context.evaluate(selected, "selection")
    feedback = await context.evaluate(selected, "search")
    for _ in range(config.rounds):
        candidate = await context.json_proposal({
            "resources": selected,
            "tasks": context.view["search"],
            "feedback": feedback,
            "instruction": "Simplify the instructions while preserving task constraints.",
            "style": config.options.get("style", "concise"),
        })
        feedback = await context.evaluate(candidate, "search")
        validation = await context.evaluate(candidate, "selection")
        if validation["score"] > best["score"]:
            selected, best = candidate, validation
        context.emit("method.checkpoint", score=best["score"])
    return {"selected": selected, "selected_score": best["score"],
            "status": "completed"}


def install():
    register_method(
        "concise_search", concise_search,
        title="Concise search", family="instruction search",
        feedback="task inputs and scalar scores",
        source="https://example.org/your-paper",
    )
```

返回的 `selected` 映射包含每个所选资源的完整文本。`context.version()` 验证该集合。`context.evaluate()` 归档候选，并返回应用程序的分数、输出和执行观察结果。

在嵌入式应用程序中，先调用 `install()`，再构造 `StudyConfig`：

```python
from evosprig.evolution.study import StudyConfig

install()
config = StudyConfig(method="concise_search", allowed_resources=["draft", "style"],
                     rounds=2, options={"style": "plain language"})
```

将此配置连同编译后的应用程序、`EvalSuite`、模型绑定和 `StudyStore` 一起传递给 `execute_study(...)`。[test_optimizer_plugins.py](../../tests/test_optimizer_plugins.py) 中的 SDK 集成会实际执行完整路径。

<a id="package-a-plugin-for-cli-and-studio"></a>

## 为 CLI 和 Studio 打包插件

通过 Python 入口点暴露安装器：

```toml
[project.entry-points."evosprig.evolution"]
concise_search = "my_optimizer:install"
```

将包安装到运行 EvoSprig 的环境中，并重启服务器。CLI 和 Studio 会从同一注册表发现其方法元数据。随后，你可以选择 **Concise search** 或运行：

```bash
evosprig improve agent.yaml --suite tasks.yaml \
  --method concise_search --resource draft --resource style --rounds 2
```

包是受信任的服务器扩展。方法注册会拒绝重复名称和同步函数。

<a id="context-contract"></a>

## 上下文契约

| 接口 | 用途 |
| --- | --- |
| `seed`, `allowed` | 初始资源文本和所选资源名称 |
| `view["search"]`, `view["selection"]` | 冻结的优化任务 |
| `evaluate(texts, split, samples=None)` | 在允许的拆分或子集上运行应用程序 |
| `propose(messages, json_output=False)` | 受预算约束的提议模型请求 |
| `json_proposal(payload)` | 请求并验证完整资源映射 |
| `archive(texts)`, `version(texts)` | 存储候选或编译其快照 |
| `emit(type, **data)` | 向研究 UI 发送进度 |
| `meter` | 共享的调用、token、候选、评估和时间限制 |

使用上下文模型和评估方法，使调用计入研究预算。传播 `BudgetExceeded` 和取消。研究运行器会在发布/测试任务上验证所选版本，并计算发布门禁；用户会单独采用该版本。

<a id="validate-a-method"></a>

## 验证方法

覆盖无效候选、预算耗尽、取消、选择行为以及一次完整的 `execute_study` 运行。将原始论文添加到 [references](references.md)，并在 [method table](evolution.md) 中描述所实现的机制。使用一个小型应用程序任务集来演示其变更和产生的输出。

<a id="structured-candidate-plugins"></a>

## 结构化候选插件

注册 `supports_structured=True`，用于接受 `StudyConfig.search_space` 的优化器。
然后 `context.seed` 和每个提议都具有 `{"resources": {...}, "fields": {...}}` 的结构。
使用 `context.version(candidate)` 验证边界、图结构和工具权限；
`context.evaluate(candidate, split)` 会运行该精确快照。仅资源插件保留
其现有的名称到文本映射。模块所有权可通过
`context.search_space.modules` 获取；`resource:name` 目标用于标识资源，JSON 指针用于标识字段。

将方法状态与目标资源分开。`context.emit("method.checkpoint", ...)`
存储进度，而返回的 `selected` 候选控制发布评估。
