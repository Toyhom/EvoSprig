# 知识库与 RAG

[English](../rag.md) · **简体中文**

知识库属于应用及其用户、租户作用域。开发者可以从画布、Python、CLI 或独立部署后的 HTTP 服务添加资料。同一来源更新后，下一次检索立即使用新版本，无需修改智能体结构。

## 安装解析能力

```bash
python -m pip install 'evosprig[documents,server,models]'
# Debian / Ubuntu：OCR 与中英文语言包
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim
```

源码安装用 `python -m pip install -e '.[documents,server,models]'`。独立导出包提供 `requirements-documents.lock`，和 `requirements.lock` 一起安装；需要 OCR 的部署环境也要安装 Tesseract。

| 文件 | 解析方式 | 引用定位 |
| --- | --- | --- |
| Markdown / TXT | UTF-8，兼容 BOM | 提取文本中的字符范围 |
| PDF | PDFium 提取文字；扫描页使用 OCR | 页码与字符范围 |
| Word `.docx` | 正文段落与表格 | 字符范围 |
| PNG、JPEG、TIFF、WebP | Tesseract OCR，支持多页 TIFF | 图片页码与字符范围 |

`ocr: auto` 识别没有可选文字的扫描页；`always` 对全部 PDF 页面做 OCR；`disabled` 只提取现有文字。`ocr_languages: chi_sim+eng` 使用已安装的中英文语言包。数字、姓名等精确信息可根据检索返回的页码核对原文。

## 开发者配置

在 `deployment.yaml` 的 `models`、`tools` 同级加入：

```yaml
documents:
  customer_uploads: true
  max_file_bytes: 52428800       # 默认 50 MiB；null 表示取消此配额
  max_batch_files: 1000         # CLI 文件夹 / Studio 单次文件选择
  max_extracted_chars: 20000000 # 单文档提取字符数；可设 null
  max_pages: 2000               # 单 PDF / 多页图片页数；可设 null
  max_ocr_pixels: 20000000      # 单页渲染像素数；可设 null
  allowed_extensions: [.md, .txt, .pdf, .docx, .png, .jpg, .jpeg, .tif, .tiff, .webp]
  chunk_size: 1200              # 200..100000 个字符
  chunk_overlap: 150            # 小于分块大小
  ocr: auto
  ocr_languages: chi_sim+eng
  ocr_dpi: 180
  ocr_timeout_seconds: 180
  max_pending_jobs: 128         # 每个作用域的待处理任务；满时返回 429
  ingestion_workers: 2         # 服务启动时的总解析工作线程数
  retrieval: lexical
```

这些是部署默认值。Studio 的**记忆与资料 → 导入与部署设置**可保存项目配置，并随导出包带走。分块设置对后续导入生效；重新上传即可重建已有来源。

上传内容流式写入临时文件，在后台线程中解析。无论请求是否提供 `Content-Length`，服务都会在读取过程中检查实际字节数。PDFium 不是线程安全的，因此它的原生解析操作串行执行。

默认检索使用持久化 SQLite FTS5 索引，中文按字、拉丁文字按词索引。提问时查询索引，无需重新扫描并分词全部文档。删除记录和恢复备份时，独立删除账本继续约束检索结果。

如需语义检索，配置兼容的 embedding 服务：

```yaml
documents:
  retrieval: hybrid
  embeddings:
    base_url: http://127.0.0.1:8000/v1
    model: your-embedding-model
    api_key_env: EMBEDDING_API_KEY
    timeout_seconds: 60
  embedding_cache_entries: 100000
```

既可使用厂商 API，也可使用本地 embedding 服务；该模型必须提供 `/embeddings`，普通聊天模型不自动具备这一能力。混合检索融合 BM25 和余弦相似度排序，文档向量按内容缓存，跨请求和服务重启复用，权限始终由当前文档存储决定。此适配器执行精确向量扫描；已有大型向量数据库可以通过 [HTTP 或 MCP 工具](tools.md)接入，返回文本、来源、页码，再绑定到检索节点或 Agent。

## 导入、更新与删除

```bash
evosprig data add-documents ./knowledge --project document-chat \
  --workspace .evosprig/docs --profile deployment.yaml
```

CLI 一次处理一份文件，以 `documents/<相对路径>` 作为来源 ID。同来源再次导入时，解析成功后整份替换；失败则保留原版本。并发上传同一来源时，较早提交的慢任务不会覆盖已经成功索引的新版本。

删除来源后，先前已排队的上传也不能将它重新写回；之后主动重新上传可以再次添加。

Python 使用同一知识库实现：

```python
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.document_library import DocumentConfig, DocumentLibrary
from evosprig.plugins.sqlite_memory import SQLiteMemory

scope = MemoryScope(Scope("document-chat"), namespace="documents")
library = DocumentLibrary(SQLiteMemory(".evosprig/docs/memory.sqlite"),
                          DocumentConfig(ocr_languages="chi_sim+eng"))
result = library.ingest_file(scope, "manual.pdf", source="manuals/product")
print(library.retriever(scope).search(scope, "保修期是多久？"))
print(library.list(scope, offset=0, limit=50))
library.delete(scope, result["document_id"])
```

导入和运行使用相同的工作区与应用 ID。带用户认证的 Studio 中，通过已登录项目的 API 上传，服务器负责绑定用户和租户；模型不能指定其他用户的作用域。

## 三种流程设计

| 方式 | 画布 / SDK 操作 | 适用场景 |
| --- | --- | --- |
| 每次必须检索 | 工具节点绑定 `documents.search`，回答节点输入接入 `nodes.retrieve.output.citations` | 每次回答都要先查业务资料 |
| Agent 自主决定 | 将 `documents.search` 加入 Agent 的工具；也可配置 harness 自动记忆检索 | 部分问题需要查文档，部分不需要 |
| 多查询与多样性 | 模型生成最多八种查询表达，交给 `documents.retrieve` 融合排序和筛选 | 用户术语不同，或问题跨多个章节 |

`documents.search` 接收 `query` 和可选 `limit`；`documents.retrieve` 接收 `queries`、`limit`、`diversity`（0..1）。输出的 `citations` 含原文片段、来源、标题、字符范围、分数及可用页码。将片段放在模型的**输入**里，用指令要求根据资料回答并给出引用。自动 harness 检索见[智能体资源](agent-resources.md)。

先在 Studio **检索测试**里看命中原文，再分别调试检索节点、带检索结果的回答节点和完整流程。用实际业务问题评测答案、引用和资料不足时的行为。[指定节点自进化](tutorials/scoped-evolution.md)可以选择某个回答 prompt、查询改写 skill 或声明的 harness 参数，在同一任务集上搜索。

## 让客户管理已部署应用的资料

开发者启用 `customer_uploads`，导出 HTTP 服务，配置模型后启动：

```bash
python -m pip install -r requirements.lock -r requirements-documents.lock
python -m pip install --no-deps .
export EVOSPRIG_SERVICE_TOKEN='replace-with-a-secret'
python serve.py --profile deployment.yaml --workspace ./customer-state --port 8080
```

服务 token 保存在业务后端，由后端验证客户身份并代理允许的操作。导出内容是后端服务，不会自动附带客户网站。不同客户的知识库使用不同部署工作区。

```bash
curl -H "Authorization: Bearer $EVOSPRIG_SERVICE_TOKEN" \
  -H 'Content-Type: application/octet-stream' --data-binary @manual.pdf \
  'http://127.0.0.1:8080/documents/upload?filename=manual.pdf'
```

| 方法 | 路由 | 功能 |
| --- | --- | --- |
| POST | `/documents/upload?filename=manual.pdf&source=manuals/product` | 提交原始文件，返回 202 和任务 ID；`source` 可选 |
| GET | `/documents/jobs/{id}` | 查询 queued / processing / succeeded / failed 及结果或错误 |
| GET | `/documents/jobs` | 最近 50 次导入 |
| POST | `/documents` | JSON `{title, text, source}`，用于短文本 |
| GET | `/documents?offset=0&limit=100` | 分页列出文档 |
| GET | `/documents/search?query=warranty&limit=5` | 检索原文 |
| DELETE | `/documents/{id}` | 删除该版本及其分块 |
| GET | `/documents/settings` | 查看部署配置 |

客户不能通过这些路由修改开发者配置。`customer_uploads: false` 时管理接口返回 403，智能体仍能检索预先导入的资料。任务队列持久化；进程崩溃后，处理中任务在十分钟租约过期后恢复。正常关闭会等待正在解析的文件完成。解析结束后删除临时上传文件，保留工作区和导入状态。备份恢复需保留当前删除账本。

Studio 对应路径为 `/api/projects/{project_id}/documents`，另提供开发者使用的 `PUT /settings`。

容器导出可用 `docker build --build-arg DOCUMENT_PARSERS=1 -t my-agent .` 安装 PDF、图片解析与 OCR；构建参数 `OCR_LANGUAGES="eng chi-sim"` 控制语言包。
