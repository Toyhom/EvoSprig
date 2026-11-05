[English](../memory.md) · **简体中文** · [文档目录](README.md)

<a id="memory-and-documents"></a>

# 记忆与文档

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

`DocumentRetriever.ingest` 接受有界纯文本、标题和来源标识符。它会创建确定性分块以及包含精确偏移量的引文引用。默认文档搜索使用 BM25，包括中文字符。将存储包装在 `HybridMemory` 中以添加语义排序。文档使用 `documents` 命名空间。可通过在 `[start:end]` 处切分原始文本来验证引文。

<a id="deletion-and-restore"></a>

## 构建文档问答应用

单次检索使用 `documents.search`；多查询使用 `documents.retrieve`，最多合并八条查询并做排序融合和结果去重。它们都可以放成必经的工具节点，也可以交给智能体按需调用。返回结果包含来源、标题、片段及引用位置。

```bash
evosprig data add-documents ./knowledge --project document-chat --workspace .evosprig/docs
evosprig serve --project examples/document-chat/agent.yaml \
  --workspace .evosprig/docs --profile deployment.yaml --studio-dir apps/studio/dist
```

导入和运行使用相同的 workspace 与项目 ID。每批支持最多 128 个 Markdown/TXT 文件，每个不超过 1 MB；更多文档分批导入。PDF、Word 和扫描件先抽取为文字。默认使用 BM25，SDK 的 `HybridMemory` 可加入向量语义检索；已有向量数据库也可以封装成自定义检索工具。完整配置见[文档问答样例](../../examples/document-chat/)。


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

共享加载器接受文本文件或由 `.md`/`.txt` 文件组成的文件夹（最多 128 个文件，每个 1 MB）。它会保留来源标签和用于引文的摘录偏移量。添加未更改的文件是幂等的。更改过的文件会创建新的文档版本；替换集合时，在 Studio 中移除过时记录。CLI 使用本地身份。在已身份验证的部署中，通过已登录用户的 Studio/API 添加文档，以保留该用户的作用域。使用相同的工作区和项目 ID 运行 agent。参见[与你的文档聊天](../../examples/document-chat)。

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
