# 可信 RAG 问答系统实现规格

## 1. 目标

系统面向银行业监管制度、政策文件和监管统计报表，提供可溯源问答能力。核心要求是：

- 能处理 `doc/docx/pdf/xls/xlsx` 多格式原始文件。
- 能回答表格取数、表格比较、表格计算、单事实检索、多事实检索问题。
- 所有答案必须返回证据，证据至少包含来源文件；表格证据应包含工作表、行列语义、单元格和单位。
- 对评测集支持自动化复现和指标输出。

## 2. 当前实现状态

当前 MVP 已完成：

- 扫描 `wendang/data` 生成 `data/processed/manifest.jsonl`。
- 构建 `data/processed/text_chunks.jsonl`、`data/processed/text_units.jsonl`、`data/processed/table_cells.jsonl` 和 `data/processed/table_rows.jsonl` 作为 RAG 检索底座。
- 生成 `data/processed/document_metadata.jsonl`，补充发文机关、发布日期、文号、业务领域、监管主题等结构化字段。
- `.xlsx` 表格解析与单元格事实查询。
- `.docx/.pdf` 文本抽取，`.doc` 二进制兜底抽取。
- 300 条 QA 自动评测，当前本地结果为 `300/300`。
- CLI 和 HTTP API。

## 3. 数据规格

### 3.1 Manifest

路径：`data/processed/manifest.jsonl`

如果已执行来源补采合并，在线服务优先读取：

```text
data/processed/manifest_enriched.jsonl
```

每行一个文档对象：

```json
{
  "doc_id": "nfra_001",
  "title": "2026年银行业总资产、总负债（月度）",
  "file_name": "001_...",
  "local_path": "E:/work/code/JINRONG/wendang/data/001_...",
  "file_ext": ".xls",
  "file_size": 12345,
  "sha256": "...",
  "source_type": "excel",
  "period": "2026年",
  "source_url": null,
  "attachment_url": null,
  "column": null
}
```

### 3.2 Document Metadata

路径：`data/processed/document_metadata.jsonl`

每行一个增强后的文档元数据对象。当前第一版以规则抽取为主，用文件名和首页/首段文本补充可检索字段：

```json
{
  "doc_id": "nfra_398",
  "title": "银行函证工作操作指引",
  "source_type": "pdf",
  "publisher": "金融监管总局办公厅、财政部办公厅",
  "publish_date": null,
  "doc_no": "财会〔2022〕39号",
  "business_domain": "银行函证",
  "regulatory_topic": "函证",
  "source_url": null,
  "attachment_url": null,
  "column": null,
  "metadata_evidence": "原文或标题中的抽取依据"
}
```

说明：
- `source_url/attachment_url/column` 字段保留，但当前本地数据没有原始下载日志，因此仍可能为 `null`。
- `/documents` 和 `/documents/{doc_id}` 会将该文件合并到 manifest 结果中返回。

### 3.3 问答响应

统一返回：

```json
{
  "question": "问题文本",
  "answer": "A 或直接答案",
  "answer_text": "答案文本或数值",
  "evidence": [
    {
      "source": "本地文件路径",
      "sheet_name": "工作表名",
      "cell_ref": "C5",
      "row_header": "原保险保费收入",
      "col_header": "本年累计/截至当期",
      "unit": "单位:亿元",
      "text": "证据文本"
    }
  ],
  "confidence": "high|medium|low",
  "route": "excel_mcq|text_mcq|excel_lookup|excel_compare|excel_calc|text_open|rag_open|rag_refusal",
  "debug": null
}
```

### 3.4 RAG 检索底座

文本 chunk：

```text
data/processed/text_chunks.jsonl
```

每行包含：

```json
{
  "chunk_id": "nfra_397_chunk_0000",
  "doc_id": "nfra_397",
  "source_type": "word",
  "source_title": "银行函证工作操作指引",
  "local_path": "E:/...",
  "chunk_index": 0,
  "text": "原文片段",
  "norm_text": "归一化文本"
}
```

文本结构单元：

```text
data/processed/text_units.jsonl
```

每行包含从 Word/PDF 文本 chunk 中进一步解析出的页码、章节路径和条款编号，用于更精确的证据定位：

```json
{
  "unit_id": "nfra_398_unit_0001",
  "doc_id": "nfra_398",
  "source_type": "pdf",
  "source_title": "银行函证工作操作指引",
  "chunk_id": "nfra_398_chunk_0000",
  "chunk_index": 0,
  "unit_index": 1,
  "page_no": 1,
  "section_path": "一、总体要求",
  "article_no": null,
  "text": "原文结构单元",
  "norm_text": "归一化文本"
}
```

表格单元格事实：

```text
data/processed/table_cells.jsonl
```

每行包含：

```json
{
  "cell_id": "nfra_145_人身保险公司（月度）__C5",
  "doc_id": "nfra_145",
  "sheet_name": "人身保险公司（月度）",
  "cell_ref": "C5",
  "row_header": "原保险保费收入",
  "col_header": "本年累计/截至当期",
  "unit": "单位:亿元、万件",
  "value_raw": 31739.18
}
```

表格行级证据：

```text
data/processed/table_rows.jsonl
```

每行包含同一 Excel 逻辑行的聚合文本，用于 RAG 证据检索：

```json
{
  "row_id": "nfra_003_人身保险公司（月度）_5",
  "doc_id": "nfra_003",
  "source_type": "excel",
  "source_title": "2026年2月人身险公司经营情况表",
  "sheet_name": "人身保险公司（月度）",
  "row_index": 5,
  "row_header": "原保险保费收入",
  "unit": "单位:亿元",
  "cell_refs": ["C5"],
  "values": [13107.93],
  "text": "文件：... 工作表：... 行：... 数据：...",
  "norm_text": "归一化文本"
}
```

构建命令：

```powershell
python -m jinrong.cli build-kb
python -m jinrong.cli build-kb --qa-only
python -m jinrong.cli export-source-template
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
python -m jinrong.cli build-metadata
python -m jinrong.cli build-text-units
python -m jinrong.cli build-vector-index
```

当前开发阶段推荐先使用 `--qa-only` 快速构建评测覆盖文件；完整 500 文件构建可作为离线任务运行。

## 4. HTTP API 规格

### `GET /health`

健康检查。

响应：

```json
{"status": "ok"}
```

### `POST /ask`

问答入口。支持按 QA 编号复现，也支持问题文本。

当前可信问答策略：

- 有选项题优先走确定性 QA 求解，不让模型直接猜选项。
- 明确 Excel 文件和指标的开放式问题优先走结构化表格查询。
- 普通开放式问题走 RAG 检索：先调用本地 BM25 证据检索，再基于 top evidence 生成受控答案。
- 若配置了 LLM，则将 top evidence 输入 OpenAI-compatible Chat Completions 接口，要求模型只能依据证据输出 JSON。
- 若未配置 LLM 或 LLM 调用失败，则自动回退到本地模板答案。
- LLM 输出后的答案仍要经过数字一致性检查；若检查失败，回退本地模板答案。
- 若证据不足，返回 `route=rag_refusal`，`answer_text=无法根据当前资料确定。`。
- `debug` 中记录证据充分性判断、匹配关键词、缺失关键词、检索候选数量和数字一致性检查。

LLM 配置通过环境变量完成：

```powershell
$env:JINRONG_LLM_API_KEY = "..."
$env:JINRONG_LLM_BASE_URL = "https://api.openai.com/v1"
$env:JINRONG_LLM_MODEL = "gpt-4o-mini"
$env:JINRONG_LLM_TIMEOUT = "30"
```

请求：

```json
{
  "qa_id": "Q001"
}
```

或：

```json
{
  "question": "根据 Excel 附件《2023年10月人身险公司经营情况表》...",
  "options": {
    "A": "31739.18",
    "B": "6428.56",
    "C": "24912.73",
    "D": "397.89"
  }
}
```

响应：见 3.3。

### `POST /search`

证据检索入口。

当前实现使用本地 BM25 检索：

- 文本资料优先检索 `text_units.jsonl`；如果该文件不存在，则回退到 `text_chunks.jsonl`。
- Excel 资料优先检索 `table_rows.jsonl`，返回行级表格证据。
- 支持按 `publisher/publish_date_from/publish_date_to/business_domain/regulatory_topic/doc_no/column/has_source_url/article_no` 过滤。
- `retrieval=bm25` 时只使用 BM25；`retrieval=hybrid` 时使用 BM25 + 本地哈希 embedding 向量召回，并用 RRF 融合排序。
- `rerank=true` 时使用 `rule_reranker_v1` 对候选证据二次重排，并在每条证据中返回 `base_score/rerank` 调试信息。
- 当 BM25 无结果时，回退到归一化文本覆盖率检索。

请求：

```json
{
  "query": "银行函证 工作质量 效率",
  "source_type": "pdf",
  "doc_id": null,
  "business_domain": "银行函证",
  "doc_no": "财会〔2022〕39号",
  "retrieval": "hybrid",
  "rerank": true,
  "top_k": 5
}
```

响应：

```json
{
  "query": "银行函证 工作质量 效率",
  "total": 3,
  "top_k": 5,
  "index": "hybrid_bm25_hash_embedding",
  "results": [
    {
      "doc_id": "nfra_398",
      "source_type": "pdf",
      "source_title": "银行函证工作操作指引",
      "source": "E:/...",
      "position": {
        "unit_id": "nfra_398_unit_0001",
        "unit_index": 1,
        "chunk_id": "nfra_398_chunk_0000",
        "chunk_index": 0,
        "page_no": 1,
        "section_path": "一、总体要求",
        "article_no": null
      },
      "score": 1.23,
      "text": "证据片段",
      "publisher": "金融监管总局办公厅、财政部办公厅",
      "doc_no": "财会〔2022〕39号",
      "business_domain": "银行函证",
      "regulatory_topic": "函证",
      "source_url": null,
      "attachment_url": null,
      "column": null,
      "evidence_type": "text_unit",
      "index": "hybrid",
      "base_score": 0.0328,
      "rerank": {
        "method": "rule_reranker_v1",
        "base_rank": 1,
        "token_coverage": 0.8
      }
    }
  ]
}
```

### `GET /documents`

列出文档。

查询参数：

- `source_type`: `excel|word|pdf`
- `file_ext`: 如 `.xlsx`
- `query`: 文件名/标题关键词
- `publisher`: 发文机关关键词
- `publish_date_from`: 发布日期下界，格式 `YYYY-MM-DD`
- `publish_date_to`: 发布日期上界，格式 `YYYY-MM-DD`
- `business_domain`: 业务领域
- `regulatory_topic`: 监管主题
- `doc_no`: 文号
- `column`: 栏目
- `has_source_url`: 是否只返回已补齐来源 URL 的文档
- `article_no`: 条款编号，如 `第十二条`
- `limit`: 默认 50
- `offset`: 默认 0

返回结果会合并 `document_metadata.jsonl` 中的增强字段，如 `publisher/publish_date/doc_no/business_domain/regulatory_topic/source_url/attachment_url/column`。

### `GET /documents/{doc_id}`

返回单个文档元数据。

### `GET /kb/status`

返回离线 RAG 检索底座状态，包括已构建文档数、文本 chunk 数、文本结构单元数、文档增强元数据数、表格单元格数、表格行级证据数和错误数。
如果已构建向量索引，还会返回 `vector_index/text_vectors/table_row_vectors`。

### `POST /eval`

运行评测。

请求：

```json
{"scope": "all"}
```

`scope` 可取：`all/excel/text`。

### Retrieval Eval

检索评测命令：

```powershell
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank --top-k 5
```

生成或重建检索评测集：

```powershell
python -m jinrong.cli build-retrieval-eval --target-size 60 --retrieval hybrid --rerank
```

评测集：

```text
data/eval/retrieval_eval.jsonl
```

报告：

```text
reports/retrieval_eval.json
```

当前第一版评测集规模为 60 条，其中 `text_unit` 30 条、`table_row` 30 条。

## 5. FastAPI 后端

当前已提供 FastAPI 后端，同时保留旧标准库 HTTP 服务作为 fallback。接口路径和 JSON 字段保持稳定，前端无需修改即可接入。

目录：

```text
src/jinrong/api/
  __init__.py
  app.py
  schemas.py
  routes.py
```

启动命令：

```powershell
python -m jinrong.cli serve --port 8000
```

`serve` 默认优先启动 FastAPI/uvicorn；如果环境缺少相关依赖，则回退到 `api_server.py` 中的轻量 HTTP 服务。

## 6. React 前端对接规格

当前前端页面：

- 工作台：调用 `GET /kb/status`。
- 问答页：调用 `POST /ask`。
- 证据检索页：调用 `POST /search`。
- 文档库页：调用 `GET /documents` 和 `GET /documents/{doc_id}`。
- 知识库状态页：调用 `GET /kb/status`。
- 评测页：调用 `POST /eval`。

前端展示重点：

- 答案正文。
- 置信度和 route。
- 证据卡片。
- 表格证据中的 `sheet_name/cell_ref/unit/value_raw`。
- 文本证据中的来源文件和片段。

当前已实现的前端文件：

```text
frontend/
  package.json
  vite.config.js
  index.html
  src/
    App.jsx
    api.js
    components.jsx
    main.jsx
    styles.css
```

启动命令：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

生产构建：

```powershell
cd frontend
npm run build
```

## 7. 已验证能力

当前本地验证命令：

```powershell
$env:PYTHONPATH = ".\src"
python -m jinrong.cli eval-all
python -m compileall -q src
```

当前本地评测结果：

```text
Excel: 100/100
Word/PDF: 200/200
Total: 300/300
```

前端 smoke test 覆盖：

- 桌面端问答、证据检索、文档库切换。
- 移动端问答结果展示。
- API 地址切换与健康检查。
- 浏览器控制台无 JavaScript 错误。
