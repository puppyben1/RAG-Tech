# 当前系统运行机制与数据清洗说明

本文档说明当前“金融监管可信 RAG 问答系统”如何运作、数据如何清洗入库、当前已经生成哪些数据产物，以及前后端如何协同。

## 1. 系统定位

本项目面向银行业监管制度、政策文件和监管统计报表，目标不是普通聊天，而是构建一个可检索、可溯源、可评测的可信 RAG 问答系统。

系统当前支持：

- 多格式监管资料入库：`.xls`、`.xlsx`、`.pdf`、`.doc`、`.docx`。
- Excel 表格题：取数、比较、计算。
- Word/PDF 文本题：单事实检索、多事实检索。
- 开放式 RAG 问答：基于检索证据生成受控答案。
- 可选 LLM 受控生成：配置 API Key 后可用 LLM 对证据进行归纳，但答案仍需通过一致性检查。
- 无证据拒答：资料库中证据不足时返回“无法根据当前资料确定”。
- 证据检索：基于 BM25 的文本 chunk 和表格行级证据检索。
- 自动评测：支持 300 条 QA 验证题复现。
- FastAPI 后端：提供 REST API。
- Vite + React 前端：提供工作台、问答、检索、文档库、知识库状态和评测中心。

## 2. 当前系统架构

系统采用“离线清洗入库 + 在线检索问答 + 前端展示”的架构。

```text
wendang/data 原始文件
  -> manifest 扫描与去重
  -> source_catalog 来源补采合并
  -> 文档解析与表格结构化
  -> RAG 检索底座
     - text_chunks.jsonl
     - text_units.jsonl
     - document_metadata.jsonl
     - table_cells.jsonl
     - table_rows.jsonl
  -> BM25 检索
  -> 可选 hybrid 检索（BM25 + local_hashing_v1 embedding）
  -> 问答服务 / 证据检索服务 / 评测服务
  -> FastAPI API
  -> React 前端工作台
```

核心思想是：

- 文本资料先按片段入库，再解析为带 `page_no/section_path/article_no` 的结构化文本单元。
- 文档元数据在 manifest 基础上做规则增强，补充发文机关、发布日期、文号、业务领域和监管主题。
- Excel 资料按“单元格事实”和“行级证据”两种粒度入库。
- 文本单元和表格行可以构建本地哈希 embedding 索引，用于 BM25 + vector 的第一版混合检索。
- 所有答案和检索结果都尽量返回来源文件、工作表、单元格、行列语义、单位或原文片段。

## 3. 原始数据情况

原始数据目录：

```text
wendang/data
```

当前共 500 份文件。

按扩展名统计：

| 文件类型 | 数量 | 当前处理方式 |
| --- | ---: | --- |
| `.xls` | 232 | 使用 `xlrd` 解析；如本机有 LibreOffice，也可转换为 `.xlsx` 后解析。 |
| `.xlsx` | 157 | 使用 `openpyxl` 解析。 |
| `.pdf` | 45 | 使用 `pdfplumber` 抽取文本。 |
| `.doc` | 32 | 优先尝试 LibreOffice 转换；没有转换工具时使用二进制文本兜底抽取。 |
| `.docx` | 34 | 使用 `python-docx` 抽取段落和表格文本。 |

按系统归类统计：

| source_type | 数量 | 说明 |
| --- | ---: | --- |
| `excel` | 389 | `.xls` 和 `.xlsx`。 |
| `pdf` | 45 | PDF 制度或附件。 |
| `word` | 66 | `.doc` 和 `.docx`。 |

## 4. 数据清洗流程

### 4.1 Manifest 生成

命令：

```powershell
python -m jinrong.cli build-manifest
```

输入：

```text
wendang/data
```

输出：

```text
data/processed/manifest.jsonl
```

每个文件会生成一条文档元数据，包括：

- `doc_id`
- `title`
- `file_name`
- `local_path`
- `file_ext`
- `file_size`
- `sha256`
- `source_type`
- `period`
- `source_url`
- `attachment_url`
- `column`

当前 `manifest.jsonl` 已覆盖 500 个文件。

其中：

- `doc_id` 用于系统内部唯一标识文档。
- `sha256` 用于去重和版本识别。
- `local_path` 用于答案证据回溯到本地原始文件。
- `period` 从文件名中尽量抽取年份、月份或季度。
- `source_url` 和 `attachment_url` 当前本地数据未提供，先保留为空，后续可补采。

### 4.2 来源 URL 补采与 manifest 增强

导出补采模板：

```powershell
python -m jinrong.cli export-source-template
```

输出：

```text
data/intermediate/source_catalog_template.csv
```

模板字段：

```text
doc_id, sha256, file_name, title, source_url, attachment_url, column,
publisher, publish_date, doc_no, business_domain, regulatory_topic
```

补齐来源信息后执行：

```powershell
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
```

支持输入格式：

- `.csv`
- `.jsonl`
- `.json`

匹配顺序：

1. `doc_id`
2. `sha256`
3. `file_name`
4. `title` 归一化宽松匹配

输出：

```text
data/processed/manifest_enriched.jsonl
reports/source_enrichment_report.json
```

服务层读取规则：

- 如果存在 `manifest_enriched.jsonl`，`/documents`、`/search` 优先使用增强 manifest。
- 如果不存在，则继续使用原始 `manifest.jsonl`。
- 原始 `wendang/data` 文件和基础 `manifest.jsonl` 不会被修改。

### 4.3 文本类文件清洗

文本类文件包括：

- `.docx`
- `.doc`
- `.pdf`

对应代码：

```text
src/jinrong/text_parser.py
src/jinrong/knowledge_base.py
```

处理方式：

- `.docx`：使用 `python-docx` 抽取段落和 Word 表格文本。
- `.pdf`：使用 `pdfplumber` 按页抽取文本，并在文本中保留 `[page N]` 标记。
- `.doc`：老 Word 格式不稳定；当前先尝试转换，若没有 LibreOffice，则用二进制兜底方式抽取可读文本。

清洗后输出：

```text
data/processed/text_chunks.jsonl
```

当前数量：

```text
1094 条文本 chunk
```

每条文本 chunk 包含：

```json
{
  "chunk_id": "nfra_398_chunk_0000",
  "doc_id": "nfra_398",
  "source_type": "pdf",
  "source_title": "银行函证工作操作指引",
  "file_name": "398_...",
  "local_path": "E:/work/code/JINRONG/wendang/data/398_....pdf",
  "chunk_index": 0,
  "text": "原文片段",
  "norm_text": "归一化文本"
}
```

切分逻辑：

- 先抽取全文。
- 再按中文句末符号切分句子。
- 多个句子合并为一个 chunk。
- 单个 chunk 控制在约 900 字以内。
- `norm_text` 去掉空白，便于检索匹配。

### 4.4 Excel 表格清洗

Excel 类文件包括：

- `.xls`
- `.xlsx`

对应代码：

```text
src/jinrong/excel_parser.py
src/jinrong/knowledge_base.py
```

当前解析工具：

- `.xlsx`：`openpyxl`
- `.xls`：`xlrd`

Excel 是本项目最重要的数据类型，不能简单转成纯文本。当前清洗保留了：

- 文件标题
- 工作表名
- 单元格坐标
- 行号、列号
- 行标题
- 列标题
- 单位
- 原始值
- 数值化结果

#### 4.3.1 单元格事实

输出：

```text
data/processed/table_cells.jsonl
```

当前数量：

```text
83555 条表格单元格事实
```

每个数值单元格生成一条 fact：

```json
{
  "cell_id": "nfra_003_人身保险公司（月度）   (2)_C5",
  "doc_id": "nfra_003",
  "source_type": "excel",
  "source_title": "2026年2月人身险公司经营情况表",
  "file_name": "003_...",
  "local_path": "E:/work/code/JINRONG/wendang/data/003_....xls",
  "sheet_name": "人身保险公司（月度）   (2)",
  "cell_ref": "C5",
  "row_index": 5,
  "col_index": 3,
  "row_header": "原保险保费收入",
  "col_header": "2026年2月人身险公司经营情况表-本年累计/截至当期-项目",
  "unit": "单位:亿元",
  "value_raw": 13107.93,
  "value_num": 13107.93,
  "text": "2026年2月人身险公司经营情况表 人身保险公司（月度） 原保险保费收入 ...",
  "norm_text": "归一化文本"
}
```

用途：

- 精确取数。
- 比较题。
- 计算题。
- 返回最小证据，如 sheet、cell、单位和原始值。

#### 4.3.2 行级证据

输出：

```text
data/processed/table_rows.jsonl
```

当前数量：

```text
15775 条表格行级证据
```

行级证据把同一 Excel 行的多个单元格聚合成一条 RAG 检索文本：

```json
{
  "row_id": "nfra_003_人身保险公司（月度）   (2)_5",
  "doc_id": "nfra_003",
  "source_type": "excel",
  "source_title": "2026年2月人身险公司经营情况表",
  "file_name": "003_...",
  "local_path": "E:/work/code/JINRONG/wendang/data/003_....xls",
  "sheet_name": "人身保险公司（月度）   (2)",
  "row_index": 5,
  "row_header": "原保险保费收入",
  "unit": "单位:亿元",
  "cell_refs": ["C5"],
  "values": [13107.93],
  "text": "文件：2026年2月人身险公司经营情况表\n工作表：人身保险公司（月度）\n行：原保险保费收入\n数据：本年累计/截至当期=13107.93(C5)",
  "norm_text": "归一化文本"
}
```

用途：

- 作为 Excel 的 RAG 检索单元。
- 避免搜索时只返回孤立数字。
- 让前端展示更自然的表格证据。

### 4.5 文档增强元数据

命令：

```powershell
python -m jinrong.cli build-metadata
```

对应代码：

```text
src/jinrong/metadata_extractor.py
```

输入：

```text
data/processed/manifest.jsonl
data/processed/text_chunks.jsonl
```

输出：

```text
data/processed/document_metadata.jsonl
reports/metadata_extraction_report.json
```

当前第一版采用规则抽取：

- 从标题和首页/首段文本抽取 `publisher`。
- 从标题和正文抽取 `publish_date`。
- 从标题和正文抽取 `doc_no`。
- 根据关键词标注 `business_domain` 和 `regulatory_topic`。
- 保留 `source_url/attachment_url/column` 字段；由于当前本地数据没有下载来源日志，这些字段仍可能为空。

当前生成结果：

| 指标 | 数量 |
| --- | ---: |
| 文档元数据记录 | 500 |
| 已抽取发文机关 | 117 |
| 已抽取发布日期 | 5 |
| 已抽取文号 | 11 |
| 已补齐来源 URL | 0 |

### 4.6 文本结构单元

命令：

```powershell
python -m jinrong.cli build-text-units
```

对应代码：

```text
src/jinrong/structure_parser.py
```

输入：

```text
data/processed/text_chunks.jsonl
```

输出：

```text
data/processed/text_units.jsonl
reports/text_units_report.json
```

处理逻辑：

- 解析 PDF 文本中的 `[page N]` 标记为 `page_no`。
- 识别章节标题，如“第一章”“一、”“（一）”等。
- 识别条款编号，如“第十二条”。
- 生成比原始 chunk 更细的 `text_unit`，并保留 `chunk_id/chunk_index` 以便回溯。

当前生成结果：

| 指标 | 数量 |
| --- | ---: |
| 文本结构单元 | 7132 |
| 带页码的单元 | 3409 |
| 带章节路径的单元 | 7005 |
| 带条款编号的单元 | 1828 |

### 4.7 构建状态与错误审计

全量清洗命令：

```powershell
python -m jinrong.cli build-kb
```

支持参数：

```powershell
python -m jinrong.cli build-kb --qa-only
python -m jinrong.cli build-kb --limit 10
python -m jinrong.cli build-kb --resume
python -m jinrong.cli build-kb --retry-failed
```

状态文件：

```text
data/processed/kb_build_state.jsonl
```

当前数量：

```text
500 条状态记录
```

每个文件处理完成后写一条状态：

```json
{
  "doc_id": "nfra_003",
  "sha256": "...",
  "file_name": "003_...",
  "file_ext": ".xls",
  "source_type": "excel",
  "status": "success",
  "text_chunks": 0,
  "table_cells": 56,
  "updated_at": "2026-07-28T..."
}
```

错误报告：

```text
reports/kb_build_errors.json
```

当前结果：

```json
[]
```

也就是说，全量 500 个文件当前处理错误数为 0。

### 4.8 本地向量索引

命令：

```powershell
python -m jinrong.cli build-vector-index
```

对应代码：

```text
src/jinrong/vector_index.py
```

当前第一版使用 `local_hashing_v1`：

- 不依赖外部模型和网络。
- 将检索文本切分为 token 后映射到 4096 维稀疏向量。
- 使用余弦相似度做向量召回。
- 在 `retrieval=hybrid` 时与 BM25 结果做 RRF 融合排序。

输出：

```text
data/index/text_vectors.jsonl
data/index/table_row_vectors.jsonl
data/index/vector_index_manifest.json
```

当前生成结果：

| 指标 | 数量 |
| --- | ---: |
| 文本向量 | 7132 |
| 表格行向量 | 15775 |
| 向量维度 | 4096 |

## 5. 当前清洗产物汇总

| 文件 | 作用 | 当前数量 |
| --- | --- | ---: |
| `data/processed/manifest.jsonl` | 文档清单与元数据 | 500 |
| `data/processed/manifest_enriched.jsonl` | 来源补采后的增强文档清单 | 有真实 catalog 后生成 |
| `data/processed/document_metadata.jsonl` | 文档增强元数据 | 500 |
| `data/processed/text_chunks.jsonl` | Word/PDF 文本检索片段 | 1094 |
| `data/processed/text_units.jsonl` | Word/PDF 页码/章节/条款级文本单元 | 7132 |
| `data/processed/table_cells.jsonl` | Excel 单元格事实 | 83555 |
| `data/processed/table_rows.jsonl` | Excel 行级 RAG 证据 | 15775 |
| `data/index/text_vectors.jsonl` | Word/PDF 本地 embedding 索引 | 7132 |
| `data/index/table_row_vectors.jsonl` | Excel 行级本地 embedding 索引 | 15775 |
| `data/index/vector_index_manifest.json` | 向量索引构建说明 | 1 |
| `data/processed/kb_build_state.jsonl` | 每个文件的构建状态 | 500 |
| `data/processed/kb_stats.json` | 知识库统计状态 | 1 |
| `reports/metadata_extraction_report.json` | 元数据抽取报告 | 1 |
| `reports/source_enrichment_report.json` | 来源补采合并报告 | 有真实 catalog 后生成 |
| `reports/text_units_report.json` | 文本结构单元报告 | 1 |
| `reports/kb_build_errors.json` | 构建错误报告 | 0 个错误 |
| `reports/excel_eval.json` | Excel QA 评测报告 | 100 条 |
| `reports/text_eval.json` | Word/PDF QA 评测报告 | 200 条 |

当前 `kb_stats.json` 关键指标：

```json
{
  "documents": 500,
  "processed_documents": 500,
  "text_chunks": 1094,
  "document_metadata": 500,
  "text_units": 7132,
  "text_vectors": 7132,
  "table_row_vectors": 15775,
  "table_cells": 83555,
  "table_rows": 15775,
  "error_count": 0
}
```

## 6. 在线问答如何运作

当前在线问答入口：

```text
POST /ask
```

对应代码：

```text
src/jinrong/ask.py
src/jinrong/table_qa.py
src/jinrong/text_qa.py
```

### 6.1 QA 编号复现

如果请求包含：

```json
{"qa_id": "Q001"}
```

系统会：

1. 从 `QA数据.xlsx` 读取对应题目。
2. 判断题目来源是 Excel、Word 还是 PDF。
3. Excel 题走表格确定性求解。
4. Word/PDF 题走文本证据匹配。
5. 返回答案、选项、证据、置信度和 route。

### 6.2 Excel 问答

Excel 题不会直接交给大模型猜答案，而是做结构化事实匹配：

1. 从问题中识别文件名、sheet、行名、列名、指标、计算意图。
2. 在 Excel 单元格事实中查找候选。
3. 取数题返回对应单元格值。
4. 比较题比较候选数值。
5. 计算题执行明确公式。
6. 返回单元格证据。

这保证了表格题可核验。

### 6.3 Word/PDF 选择题问答

Word/PDF 题当前主要是选择题匹配：

1. 抽取文档文本。
2. 按句子或 chunk 检索相关证据。
3. 对选项计算文本覆盖率。
4. 选择证据最强的选项。
5. 返回原文片段作为证据。

### 6.4 开放式 RAG 问答与拒答

没有选项的普通问题会进入可信 RAG 问答流程。

对应代码：

```text
src/jinrong/trusted_qa.py
```

处理流程：

1. 调用 `search_evidence` 从全量知识库检索 top 5 条证据。
2. 对问题抽取关键短语。
3. 检查关键短语在 top evidence 中的覆盖情况。
4. 如果证据不足，返回拒答：

```json
{
  "answer": null,
  "answer_text": "无法根据当前资料确定。",
  "confidence": "low",
  "route": "rag_refusal"
}
```

5. 如果证据充分，系统会优先尝试 LLM 受控生成；未配置 LLM 或调用失败时，回退到本地模板答案。

```json
{
  "route": "rag_open",
  "confidence": "high",
  "answer_text": "根据《...》中的证据，..."
}
```

6. 对答案中的数字做一致性检查：如果答案中出现的数字不在证据中，会在 `debug` 中记录。

LLM 受控生成配置：

```powershell
$env:JINRONG_LLM_API_KEY = "..."
$env:JINRONG_LLM_BASE_URL = "https://api.openai.com/v1"
$env:JINRONG_LLM_MODEL = "gpt-4o-mini"
$env:JINRONG_LLM_TIMEOUT = "30"
```

LLM 调用约束：

- 只允许依据 top evidence 回答。
- 不允许使用外部知识。
- 不允许编造数字、日期、文号、机构名称。
- 证据不足时要求模型返回 `can_answer=false`。
- 模型必须输出 JSON，系统再读取其中的 `answer`。

当前 `debug` 会记录：

- `sufficient`：证据是否充分。
- `matched_terms`：已命中的问题关键词。
- `missing_terms`：未命中的问题关键词。
- `coverage`：关键词覆盖率。
- `best_score`：最高检索分数。
- `candidate_count`：候选证据数量。
- `consistency`：答案数字与证据的一致性检查。

示例：

```powershell
python -m jinrong.cli ask --question "银行函证工作如何提高质量和效率？"
```

会返回 `route=rag_open`，并给出《银行函证工作操作指引》中的证据。

```powershell
python -m jinrong.cli ask --question "宇宙飞船发动机保修期是多少？"
```

会返回 `route=rag_refusal`，说明无法根据当前资料确定。

## 7. 证据检索如何运作

当前证据检索入口：

```text
POST /search
```

对应代码：

```text
src/jinrong/services.py
src/jinrong/retrieval.py
```

检索流程：

1. 根据 `source_type` 和 `doc_id` 做过滤。
2. 根据 `publisher/publish_date/business_domain/regulatory_topic/doc_no/column/has_source_url/article_no` 做元数据过滤。
3. 文本资料优先检索 `text_units.jsonl`，返回页码、章节路径、条款编号；没有该文件时回退到 `text_chunks.jsonl`。
4. Excel 资料检索 `table_rows.jsonl`。
5. `retrieval=bm25` 时使用本地 BM25 排序。
6. `retrieval=hybrid` 时同时执行 BM25 和本地向量召回，并用 RRF 融合排序。
7. `rerank=true` 时使用 `rule_reranker_v1` 对候选证据二次重排。
8. 如果 BM25 没有结果，回退到归一化文本覆盖率检索。
9. 返回 top_k 条证据。

### 7.1 Reranker 第一版

对应代码：

```text
src/jinrong/reranker.py
```

当前第一版是规则重排器：

- 计算查询 token 在正文、标题、位置和元数据中的覆盖情况。
- 对日期短语、完整短语、实质正文长度做额外加权。
- 保留原始召回分数为 `base_score`。
- 在证据中写入 `rerank.method=rule_reranker_v1` 和特征调试信息。

启用方式：

```powershell
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --retrieval hybrid --rerank --top-k 3
```

### 7.2 检索评测集

评测集：

```text
data/eval/retrieval_eval.jsonl
```

评测命令：

```powershell
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank --top-k 5
```

重建评测集：

```powershell
python -m jinrong.cli build-retrieval-eval --target-size 60 --retrieval hybrid --rerank
```

评测报告：

```text
reports/retrieval_eval.json
```

当前第一版评测 60 条 evidence-level 查询，其中 30 条文本证据、30 条表格行证据，覆盖 PDF/Word 文本证据、Excel 表格行证据和元数据过滤。指标包括 `top1_accuracy/top3_accuracy/topk_accuracy`。

搜索结果包含：

- `doc_id`
- `source_type`
- `source_title`
- `source`
- `position`
- `score`
- `text`
- `evidence_type`
- `index`

示例：

```powershell
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --top-k 3
```

会命中《银行函证工作操作指引》相关文本块。

```powershell
python -m jinrong.cli search "2026年2月 人身险 原保险保费收入" --source-type excel --top-k 3
```

会命中“2026年2月人身险公司经营情况表 / 原保险保费收入”的表格行证据。

## 8. 后端如何运作

当前后端是 FastAPI：

```text
src/jinrong/api/app.py
src/jinrong/api/routes.py
src/jinrong/api/schemas.py
```

启动命令：

```powershell
python -m jinrong.cli serve --port 8000
```

主要接口：

| 接口 | 作用 |
| --- | --- |
| `GET /health` | 健康检查。 |
| `GET /openapi.json` | FastAPI 自动生成的 OpenAPI schema。 |
| `POST /ask` | 问答入口。 |
| `POST /search` | 证据检索入口。 |
| `GET /documents` | 文档列表。 |
| `GET /documents/{doc_id}` | 文档详情。 |
| `GET /kb/status` | 知识库状态。 |
| `POST /eval` | 运行 QA 评测。 |

后端服务层集中在：

```text
src/jinrong/services.py
```

这样做的好处是：

- CLI 和 HTTP API 可以复用同一套逻辑。
- 前端只需要关心稳定的 REST 接口。
- 后续替换检索器或接入向量模型时，不需要改前端。

## 9. 前端如何运作

当前前端是 Vite + React：

```text
frontend/
  package.json
  vite.config.js
  index.html
  src/
    main.jsx
    App.jsx
    api.js
    components.jsx
    styles.css
```

启动命令：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

页面：

| 页面 | 功能 | 调用接口 |
| --- | --- | --- |
| 工作台 | 展示文档数、文本块、表格事实、行级证据、错误数 | `GET /kb/status` |
| 问答 | 按 QA 编号或自定义问题进行问答 | `POST /ask` |
| 证据检索 | 检索文本证据和表格行证据 | `POST /search` |
| 文档库 | 浏览 500 份入库文件 | `GET /documents` |
| 知识库状态 | 查看全量知识库状态 JSON | `GET /kb/status` |
| 评测中心 | 运行 Excel、Word/PDF 或全部 QA 评测 | `POST /eval` |

前端默认调用：

```text
http://127.0.0.1:8000
```

可以在顶部 API Base 输入框中修改。

## 10. 自动评测

评测命令：

```powershell
python -m jinrong.cli eval-all
```

当前结果：

```text
Excel: 100/100
Word/PDF: 200/200
Total: 300/300
Accuracy: 1.0
```

评测报告：

```text
reports/excel_eval.json
reports/text_eval.json
```

说明：

- QA 验证题主要用于证明当前系统对标准题集的可复现能力。
- 300/300 不代表开放式 RAG 已经完全成熟。
- 后续还需要增加开放式问答评测、拒答评测和证据充分性评测。

## 11. 当前边界

当前系统已经完成从数据清洗、知识库构建、检索、问答、API 到前端的 MVP 闭环，但仍有一些边界：

- PDF 复杂版式、双栏、扫描件、复杂表格仍可能需要 MinerU、OCR 或专业 PDF parser 增强。
- `.doc` 当前在没有 LibreOffice 时使用兜底抽取，质量低于 `.docx`。
- 当前检索已支持 BM25、`local_hashing_v1` hybrid 检索和 `rule_reranker_v1`；后续仍需接入真实语义 embedding 与模型级 reranker。
- 开放式 RAG 已支持可选 LLM 受控生成；未配置 LLM 时仍使用本地模板答案。
- 拒答机制已经具备第一版，但仍需要更系统的拒答评测集。
- 当前 300 条 QA 是选择题评测，后续应增加开放问答集和人工证据审计。

## 12. 一句话总结

当前系统已经把 500 份本地监管数据清洗为可检索知识库：文本资料变成 1094 个 chunk，Excel 资料变成 83555 条单元格事实和 15775 条行级证据；在线服务通过 FastAPI 提供问答、检索、文档和评测接口，前端通过 React 工作台展示答案与证据。
