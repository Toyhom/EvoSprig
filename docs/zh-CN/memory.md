[English](../memory.md) · **简体中文** · [文档目录](README.md)

<a id="memory-and-documents"></a>

# 智能体记忆

SQLite 是基线 `MemoryStore`。每条记录都属于一个精确的 `tenant / user / project / role / namespace` 作用域。选择会在相关性排序之前应用该作用域。该基线支持显式写入、精确去重、带修订检查的更新、有效时间窗口、词法搜索、删除、导出和命名空间重置。冲突事实仍作为单独的记录保留，并附带其来源；自动语义冲突解决是一项扩展能力。

```python
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.sqlite_memory import SQLiteMemory

memory = SQLiteMemory("workspace/memory.sqlite")
scope = MemoryScope(Scope("research", user="alice", tenant="team"))
record = memory.write(scope, "Use concise Chinese replies", source="user:explicit")
assert memory.search(scope, "Chinese")[0]["id"] == record["id"]
memory.delete(scope, record["id"])
```

`memory.search`、`memory.write` 和 `documents.search` 可声明为工具插件。CLI、Studio 和独立导出在工具参数之外绑定其作用域。模型无法提供其他用户或项目。写入遵循与其他有副作用的工具相同的三部分写入选择加入机制。检索结果是不可信数据，并保留来源归属；将系统策略保存在带版本的 prompt/skill 资源中。

## 记忆、上下文与应用资料

| 层次 | 内容 | Studio / 运行方式 |
| --- | --- | --- |
| 长期记忆 | 用户偏好、事实、经验、关系 | **记忆**页；`memory.*` 工具 |
| 工作上下文 | 当前目标、进度、会话摘要、近期消息 | 上下文块、图输入、普通模型或智能体节点 |
| 外部知识库 | 手册、合同和业务文档 | **知识库**页；`documents.search` / `documents.retrieve` |

智能体可以不使用知识库而拥有记忆。二者可以共享存储和检索算法，但作用域和生命周期独立。知识库是应用资料，客户可在部署后更新，详见[知识库与 RAG](rag.md)。

### 长对话如何处理

**节点设置 → 记忆**可配置记忆工具、任务前召回和工具历史预算。预算会缩短发送给模型的旧工具结果，保留近期工具轮次、调用与结果的配对，以及完整运行记录。它按字符计数，不等同于模型 token。系统消息与用户消息会保留，因此受保护的内容可能超出该预算。

语义压缩用普通模型或智能体节点完成。把旧摘要与较早的消息传给它，再把新摘要和未经修改的近期消息接到回答节点。摘要节点可单独选模型和提示词；应用自行决定何时触发，例如超过长度阈值时或下一轮交互前。参见[工作上下文教程](tutorials/working-context.md)，提供可导入的 Python 代码，不依赖文档库。

`memory.summarize` 用于保存模型写出的经验摘要，并关联来源记录 ID；它不会自动压缩会话。上下文块可保存有长度限制的工作笔记；图输出可把新摘要交给部署后的业务应用，在下一次请求时复用。

<a id="deletion-and-restore"></a>

## 配置基于检索的外部记忆

外部记忆将记录保存在模型上下文之外，再按任务检索相关内容。它与业务知识库独立配置。在 **记忆** 页新建记忆库、添加事实或经验，然后打开 **检索与读写设置**：

| 模式 | 召回方式 | 额外服务 |
| --- | --- | --- |
| `lexical` | BM25 关键词匹配 | 不需要 |
| `semantic` | 向量余弦相似度 | 本地或 API 向量模型 |
| `hybrid` | BM25 与向量排名通过 RRF 融合 | 本地或 API 向量模型 |

在 **检索测试** 中查看当前记忆库的命中记录与来源。最低余弦相似度用于过滤向量命中；混合模式仍可返回关键词命中的记录。向量模型与智能体使用的语言模型分别配置。

打开智能体节点的 **记忆 → 检索式外部记忆**，选择库并点击 **接入记忆库**。开启 **每次任务开始前自动检索** 后，由 harness 先召回记忆；不开启时，由智能体按需调用搜索工具。自动召回可调整查询输入、条数和上下文字符预算。勾选 **附加记忆写入工具** 会附加写入工具，工作流和运行时也需要开放写入权限。

同一用户和项目内，选用同一个库的节点共享记录；选择不同库即可分开记忆。记忆库设置中的 **智能体写入** 可关闭写入工具，开发者仍能在记录页维护内容。上下文块和时序关系也归属当前选中的记忆库。

### 部署配置

在 `deployment.yaml` 的 `models` 旁添加：

```yaml
memory:
  banks:
    default:
      retrieval: lexical
    writer:
      retrieval: hybrid
      embeddings:
        base_url: http://127.0.0.1:8011/v1
        model: your-embedding-model
        api_key_env: MEMORY_EMBEDDING_API_KEY
        timeout_seconds: 30
      min_similarity: 0.3
      embedding_batch_size: 64
      embedding_cache_entries: 100000
      retrieval_timeout_seconds: 120
      agent_writes: true
```

使用兼容 OpenAI `/embeddings` 的接口，包括本地部署的向量模型。进程环境中设置 `MEMORY_EMBEDDING_API_KEY`；无需鉴权的本地服务可用占位值。服务地址、模型、批大小、缓存条数、相似度阈值和工具超时均可调整。Studio 将项目级配置保存在工作目录中，并覆盖部署文件里同名库的配置。

### Python 开发

```python
from evosprig.sdk import Builder

builder = Builder("remembering-assistant", {"type": "object"},
                  {"type": "object"}, spec_version="0.3")
builder.default_model("main", requires=["text", "tool_calling"])
builder.memory_tool("recall_preferences", bank="writer", operation="search")
builder.memory_tool("save_preference", bank="writer", operation="write")
builder.node(
    "assistant", "agent", instructions="Use the user's preferences when relevant.",
    inputs={"question": {"ref": "input.question"}},
    output_schema={"type": "object"},
    tools=["recall_preferences", "save_preference"],
    harness={"memory": {"tool": "recall_preferences", "query_input": "question",
                        "limit": 5, "max_chars": 4000}},
)
builder.output(answer={"ref": "nodes.assistant.output.text"})
builder.execution(allow_side_effects=True)
spec = builder.build_spec()
```

在上述部署配置中声明 `writer`。运行时传入 `--profile deployment.yaml --allow-writes`，即可允许已选的写入工具执行。工具插件名为 `memory.writer.search` 和 `memory.writer.write`；默认库仍使用 `memory.search`、`memory.write`。其他操作包括 `recall`、`remember`、`summarize`、`context` 和 `relations`。命名库的 `recall` 先使用该库的检索策略，再结合经验的重要性与时间衰减排序。

Python、HTTP 和容器导出会将所选库的配置写入 `memory-config.json` 和 `deployment.example.yaml`；ZIP 导回画布时恢复配置。记忆记录保存在运行工作目录中，跨会话复用该目录即可。应用导出只携带配置，不携带个人记忆。向量缓存会持久保存，重启后继续使用；每次检索都重新检查原记录的更新和删除状态。

### Studio API

- `GET /api/projects/{id}/memory/banks`：列出记忆库配置。
- `PUT /api/projects/{id}/memory/banks/{name}`：创建或配置记忆库。
- 在记忆记录、检索、导出、上下文和关系路由上添加 `?bank=writer` 选择库；省略时使用 `default`。

服务器先确定用户和项目，再选择库。模型不能通过工具参数切换身份或其他记忆库。若需在 Python 中接入其他存储，实现 `MemoryStore` 协议，再通过 `register_memory_tools` 绑定；内置可配置记忆库使用 SQLite，向量模型可本地部署或通过 API 调用。

## 删除与恢复

`memory.sqlite` 包含记录。`memory.deletions.sqlite` 是一个独立的单调删除账本，包含 ID、作用域和删除时间，但不包含被删除的内容。Delete 会删除活动行，并在一个附加的 SQLite 事务中记录墓碑。命名空间重置还会为较旧的备份记录截止点。每次读取、搜索、导出和恢复都会检查当前账本。

使用 `memory.export(scope)` 和 `memory.restore(scope, records)` 进行作用域内备份和恢复。恢复从不会覆盖较新的活动记录，也不会跨越作用域。恢复记忆数据库的备份时，保留最新账本。从旧备份恢复两个文件会擦除之后的删除历史，因此不受支持。灾难恢复要求单独备份/迁移账本。这些是运维数据库；生成的应用程序导出会排除两者。

<a id="api-identities"></a>

## API 身份

开发服务器默认使用 `local` 主体。对于单独用户，传入带有环境引用的 `--auth-file identities.yaml`：

```yaml
- user: alice
  tenant: team
  token_env: ALICE_API_TOKEN
- user: bob
  tenant: team
  token_env: BOB_API_TOKEN
```

在服务器环境中设置相应令牌，并使用 bearer 身份验证。每个主体拥有其项目、运行、事实和文档。请求体不能选择身份；未知记录和超出作用域的记录都会返回 404。服务器继续绑定到回环地址；通过经过身份验证的 TLS 反向代理将其暴露，并转发允许的回环 Host。通过服务器配置文件管理身份列表。

记忆路由位于 `/api/projects/{id}/memory` 下；文档上传、列出、搜索和删除位于 `/api/projects/{id}/documents` 下。记忆数据导出是与应用程序导出明确分开的操作。

<a id="retrieval-strategies"></a>

## 检索策略

SQLite 搜索使用 BM25 词频和长度归一化，并采用英文单词和 CJK 字符分词。传入 `at=<unix timestamp>` 以指定历史有效性，传入 `content_type` 以过滤记录。

`HybridMemory(memory, embedder)` 通过倒数排名融合结合 BM25 和余弦排名。嵌入器提供 `model_id` 和 `embed(list[str]) -> list[list[float]]`。批处理和向量缓存都是有界的；每次查询都会在排名前重新读取已授权记录和删除账本。在模型控制的参数之外配置你的嵌入提供方。

```python
from evosprig.plugins.semantic_memory import HybridMemory

# embedding_provider implements the Embeddings protocol.
semantic = HybridMemory(memory, embedding_provider)
hits = semantic.search(scope, "preferred communication style", limit=5)
```

<a id="context-blocks-and-temporal-relations"></a>

## 上下文块与时间关系

```python
from evosprig.plugins.structured_memory import StructuredMemory

structured = StructuredMemory(memory)
profile = structured.set_context(scope, "profile", "Alice prefers concise replies.",
                                 source="user:explicit", max_chars=1000)
structured.set_context(scope, "profile", "Alice prefers concise replies in English.",
                       source="user:explicit", revision=profile["revision"])
structured.set_relation(scope, "Alice", "works_on", "Orion", source="user", valid_from=100)
structured.set_relation(scope, "Alice", "works_on", "Atlas", source="user", valid_from=200)
assert structured.relations(scope, "Alice", at=150)[0]["metadata"]["relation"][2] == "Orion"
```

上下文块使用带修订检查的更新和可配置的字符预算。时间关系更新会原子地关闭前一个区间；有界图遍历会遵循在查询时有效的关系。所有记录共享现有作用域和删除账本。

API 公开 `/api/projects/{id}/context`、`/context/{name}` 和 `/relations`。运行时的 `memory.context` 和 `memory.relations` 工具在部署绑定的用户作用域中提供读取访问。这些工具包含在独立导出中。参见[个人助理](../../examples/personal-memory)。

可直接使用兼容的嵌入 API：

```python
from evosprig.plugins.embeddings import EmbeddingConnection, OpenAIEmbeddings

provider = OpenAIEmbeddings(EmbeddingConnection(
    base_url="https://api.openai.com/v1", model="text-embedding-3-small",
    api_key_env="OPENAI_API_KEY",
))
semantic = HybridMemory(memory, provider)
```

安装 `models` extra 以使用 HTTP 客户端。当从异步应用程序调用时，此同步记忆适配器应在 worker/线程中运行。其请求具有显式超时、有界响应大小，且不自动重试。

<a id="load-a-document-collection"></a>

## 加载文档集合

```bash
evosprig data add-documents ./documents --project document-chat --workspace .evosprig/docs
```

共享加载器支持文件和文件夹，保留来源、页码和字符位置。相同来源解析成功后整份替换，失败保留旧版本。CLI 使用本地身份；带认证的 Studio/API 使用服务器绑定的用户作用域。配置与部署后文档管理见[知识库与 RAG](rag.md)。

<a id="experience-recall-and-linked-summaries"></a>

## 经验召回与关联摘要

`EpisodicMemory` 使用查询相关性、重要性和指数式新近度衰减对已授权记录进行排名。权重和半衰期可在 SDK 中配置。链接连接同一作用域内的相关记录，召回可以包含这些邻居。

```python
from evosprig.plugins.episodic_memory import EpisodicMemory

experiences = EpisodicMemory(memory)
record = experiences.remember(scope, "The user avoids peanuts", source="user:explicit",
                              importance=1.0, tags=["food"])
experiences.summarize(scope, "Avoid peanuts when planning meals", [record["id"]])
hits = experiences.recall(scope, "meal preferences", limit=5)
```

原生工具 `memory.remember`、`memory.recall` 和 `memory.summarize` 将这些操作暴露给 agent。摘要由调用模型提供，并保留其来源 ID 和修订版本。删除、使来源过期或更改来源会隐藏过时的派生摘要，包括在恢复之后。agent 选择何时进行摘要以及关联哪些经验。

这在 BM25、混合语义检索、上下文块和时间关系之外，增加了相关性/重要性/新近度召回以及关联经验笔记。它借鉴了 [Generative Agents](https://github.com/joonspk-research/generative_agents) 和 [A-Mem](https://github.com/agiresearch/A-mem) 中使用的思想，并实现为原生记忆策略。

<a id="multi-query-retrieval"></a>

## 多查询检索

`documents.retrieve` 接受 `queries`（最多八个）、`limit` 和 `diversity`。agent 可以构造互补查询，使用倒数排名融合合并其结果，并通过词法多样性惩罚减少近似重复的摘录。每个结果都保留其原始引文和来源偏移量。它使用与单查询搜索相同的文档存储和作用域检查。

对于精确术语使用单查询 BM25，对于包含多个方面的问题使用多查询检索，当改写表述很重要时使用混合检索，对于必须始终可用的短事实使用上下文块。嵌入仍是可选的；这些策略都不需要训练模型权重。

原始论文和实现映射：[研究参考](references.md)。
