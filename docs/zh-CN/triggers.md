[English](../triggers.md) · **简体中文** · [文档目录](README.md)

<a id="start-an-agent-from-an-event"></a>

# 从事件启动 agent

使用 `Runtime.create_event_run` 将传入事件转换为一次持久化的应用运行。重复投递会返回相同的运行 ID。首次接受的版本、输入和部署绑定会在重启和应用更新后仍附加到该运行。

```python
from evosprig.core.triggers import Trigger

# Verify the source signature and actor policy in your receiving endpoint.
trigger = Trigger(
    source="github:owner/repository",
    event_id=delivery_id,
    actor=payload["sender"]["login"],
    thread=f"issue-{payload['issue']['number']}",
    payload=payload,
)
run_id = runtime.create_event_run(
    version,
    {"request": payload["issue"]["body"]},
    trigger,
    scope=scope,
)
```

使用 `SQLiteJournal` 进行持久化接入。事件和执行会在该方法返回之前一起存储。worker 可以使用 `journal.due()` 发现已排队的执行，并使用 `runtime.resume(run_id)` 继续执行。接收方可以在创建运行后立即确认源。

源名称标识项目范围内的账户或仓库。保持其稳定，并将源的投递 ID 用作 `event_id`。将稳定的事件内容放入 `payload`；传输重试计数器和接收时间戳应记录在接收方日志中。对同一事件 ID 复用不同内容会抛出 `ValueError`。

触发器可在运行的 `metadata.context.trigger` 中获取。`thread` 字段记录用于应用路由的会话成员关系。后续消息可以使用 [agent 邮箱](shared-workspaces.md)，而 [人工节点](studio.md) 会在执行期间收集决策。
