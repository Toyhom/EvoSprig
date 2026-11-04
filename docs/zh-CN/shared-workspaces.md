[English](../shared-workspaces.md) · **简体中文** · [文档目录](README.md)

<a id="shared-documents-peer-messages-and-wake-ups"></a>

# 共享文档、点对点消息与唤醒

智能体和人员可以编辑同一项目文档。EvoSprig 将内容、修订历史和写入回执存储在 `documents.sqlite` 中，并按租户、用户和项目划分范围。

```python
from evosprig.core.journal import Scope
from evosprig.plugins.workspace_tools import WorkspaceStore

store = WorkspaceStore(".evosprig/documents.sqlite")
scope = Scope("office")
draft = store.read(scope, "deliverables/plan.md")
saved = store.write(scope, "deliverables/plan.md", "# Launch plan\n...",
                    draft["revision"], idempotency_key="plan-edit-1")
```

新文档从修订版本 0 开始。每次成功编辑都会创建一个修订版本。过期的编辑会引发 `ToolRejectedError("revision_conflict", ...)`；重试前请重新读取并合并。重复相同的操作 ID 和内容会返回原始结果。

<a id="agent-tools"></a>

## 智能体工具

| 插件 | 参数 | 结果 |
| --- | --- | --- |
| `workspace.list` | `prefix` | 文档名称和修订版本 |
| `workspace.read` | `name` | 最新内容和修订版本 |
| `workspace.write` | `name`、`content`、`expected_revision` | 名称、修订版本和时间戳 |
| `workspace.history` | `name` | 修订元数据 |
| `workspace.wait` | `seconds`、`message` | 持久化的外部作业；到期时恢复 |

这些工具可通过 `make_tools` 使用。使用 `Builder.tool` 声明智能体所需的工具。设置 `tool_errors="feedback"`，使智能体能够响应修订版本冲突。为文档编辑和计划唤醒启用写入。

`workspace.wait` 在返回作业 ID 之前持久化截止时间。当作业就绪时，Studio 的 worker 会恢复该运行；CLI 用户需显式恢复同一运行。重启 worker 会保留原始截止时间。取消运行会取消其未完成的唤醒。最大延迟：七天。

<a id="browser-and-service-clients"></a>

## 浏览器与服务客户端

所有路由都使用当前已认证的项目范围：

| `/api/projects/{id}/workspace` 下的路由 | 操作 |
| --- | --- |
| `GET /documents?prefix=` | 列出文档 |
| `GET /document?name=&revision=` | 读取最新或历史内容 |
| `PUT /document` | 使用 `name`、`content`、`expected_revision`、`operation_id` 保存；可选 `media_type` |
| `GET /history?name=` | 修订版本列表 |
| `GET /download?name=` | 下载文档 |

浏览器保存发生冲突时返回 HTTP 409，并保留其草稿。[Cowork workbench](../../apps/cowork) 使用这些路由显示、编辑和下载团队交付物。

<a id="peer-to-peer-messages"></a>

## 点对点消息

同一运行中，任何拥有邮箱的智能体都可以向另一个智能体发送消息。为固定角色命名，例如 `analyst` 和 `writer`，或在 map body 中使用 `mailbox={"ref":"input.item.role"}`。运行时提供发送者身份；模型参数仅包含接收者和内容。

```python
builder.tool("send", "messages.send")
builder.tool("inbox", "messages.receive")
builder.tool("wait_for_reply", "messages.wait")
builder.node("analyst", "agent", model="main", mailbox="analyst",
             tools=["send", "inbox", "wait_for_reply"],
             instructions="Share findings with writer; answer peer questions.",
             inputs={"request": {"ref": "input.request"}},
             output_schema={"type": "object"})
```

| 插件 | 参数 | 行为 |
| --- | --- | --- |
| `messages.send` | `recipient`、`content`，可选 `reply_to` | 幂等投递；返回 ID 和序列 |
| `messages.receive` | 可选 `after`、`limit` | 读取此智能体未确认的消息 |
| `messages.ack` | `ids` | 将消息标记为已处理；仅接受此邮箱的 ID |
| `messages.wait` | 可选 `after`、`timeout_seconds` | 持久化等待，在到达或超时时恢复 |

具有 `messages.receive` 的智能体会在模型/工具轮次之间收到新到达的消息。显式读取和等待可在任务期间获取回复。已完成的专家智能体在工作流安排下一波次时读取排队的消息；跨波次保持其邮箱名称稳定。发送和等待需要与共享文档相同的持久化存储和写入权限。消息按租户、用户、项目和运行划分范围。消息 ID、游标、原始等待截止时间和确认在 worker 重启后仍然保留。回复链接到回复智能体实际收到的消息。

使用 `tool_errors="feedback"` 时，无效的回复或确认会向智能体返回更正。确认 ID 来自已接收的消息；发送消息产生的回执属于接收者的邮箱。

[CoworkOS (EvoSprig)](../../examples/cowork) 将直接点对点消息与共享文档、主智能体审核和有针对性后续波次相结合。
