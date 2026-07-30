# 项目后续设计与开发计划

本文档基于 `docs/SPEC.md` 制定，用于说明当前数据清洗状态、后续 RAG 系统设计计划和阶段验收标准。

## 1. 当前结论

当前项目已经完成 MVP 级别的数据处理、问答、检索、评测和前端演示，但还没有完成全量 500 份文件的生产级 RAG 入库。

数据状态分为两层：

| 层级 | 当前状态 | 说明 |
| --- | --- | --- |
| 原始数据 | 已具备 | `wendang/data` 是本项目本地原始下载数据目录，共 500 份文件。 |
| Manifest 清单 | 已完成 | `data/processed/manifest.jsonl` 已覆盖 500 个文件，包含 `doc_id`、标题、本地路径、文件大小、SHA-256、文件类型等字段。 |
| QA 覆盖知识库 | 已完成 | `data/processed/text_chunks.jsonl` 与 `data/processed/table_cells.jsonl` 当前由 `build-kb --qa-only` 构建，覆盖 49 个评测相关文档。 |
| 全量 RAG 知识库 | 待完成 | 还需要对 500 个文件做完整解析、切分、表格结构化、索引构建和错误审计。 |
| QA 评测 | 已完成 | 300 条验证题当前本地结果为 300/300。 |
| 前端演示 | 已完成 MVP | `frontend/index.html` 已可调用问答、检索、文档、评测等接口。 |

因此，“本地数据都清洗好了吗”的准确回答是：清单级清洗已经完成，评测集覆盖数据已经清洗并入库；全量 500 份数据还没有完成生产级 RAG 清洗入库。

## 2. SPEC 对齐原则

后续开发必须保持 `docs/SPEC.md` 中的接口、字段和行为稳定。

核心约束：

- 问答统一走 `POST /ask`。
- 证据检索统一走 `POST /search`。
- 文档库统一走 `GET /documents` 和 `GET /documents/{doc_id}`。
- 知识库状态统一走 `GET /kb/status`。
- 评测统一走 `POST /eval`。
- 回答必须包含 `answer`、`answer_text`、`evidence`、`confidence`、`route`。
- 表格证据必须尽量包含 `sheet_name`、`cell_ref`、`row_header`、`col_header`、`unit`、`value_raw`。
- 文本证据必须包含来源文档和原文片段。
- 无证据时不能强答，应返回低置信度或无法确定。

## 3. 目标架构

项目后续按“离线入库 + 在线问答 + 可视化评测”推进。

```text
wendang/data 原始文件
  -> manifest 扫描与去重
  -> Word/PDF/Excel 解析
  -> 文本 chunk 与表格 cell fact
  -> BM25/向量/结构化索引
  -> FastAPI 服务
  -> React 工作台
  -> QA 自动评测与证据审计
```

## 4. 阶段计划

### 阶段一：全量数据清洗入库

目标：把 500 份原始文件全部转成可检索、可溯源的知识库。

解析工具采用分层策略，不一次性引入重型工具：

| 文档格式 | 当前采用 | 后续增强 | 设计理由 |
| --- | --- | --- | --- |
| `.docx` | `python-docx` | MinerU / LlamaIndex parser | 当前足够抽取段落和 Word 表格；复杂版式后续再增强。 |
| `.doc` | 二进制兜底抽取 | LibreOffice 转 `.docx` | 老 Word 格式不稳定，应优先转换后解析。 |
| `.pdf` | `pdfplumber` | MinerU / LlamaParse / OCR | PDF 是最大难点，基础库先覆盖可抽文本 PDF；双栏、扫描件、复杂表格进入增强分支。 |
| `.xlsx` | `openpyxl` | 表头识别、合并单元格展开、row text | Excel 必须保留 sheet、cell、行列语义和单位，不能只转纯文本。 |
| `.xls` | 暂不深度解析 | LibreOffice 转 `.xlsx` | 老 Excel 格式需要转换后进入统一结构化解析流程。 |

任务：

- 扩展 `build-kb` 的全量运行能力，避免超时和超大中间文件。
- 对 `.xls` 建立稳定转换流程，优先转成 `.xlsx` 后解析。
- 对 `.doc` 建立 LibreOffice 转换流程，优先转成 `.docx` 或 `.pdf` 后解析。
- 为每个解析失败文件记录错误类型、错误信息和可重试状态。
- 输出全量版：
  - `data/processed/text_chunks.jsonl`
  - `data/processed/table_cells.jsonl`
  - `data/processed/kb_stats.json`
  - `reports/kb_build_errors.json`

验收标准：

- `manifest.jsonl` 文件数等于原始数据文件数。
- 全量构建结束后 `kb_stats.json` 能报告文档数、文本块数、表格单元格数和失败文件列表。
- 失败文件不导致整个构建中断。
- 原始文件不被修改。

### 阶段二：RAG 检索增强

目标：从当前规则检索升级为更完整的 RAG 检索底座。

任务：

- 为文本 chunk 建立 BM25 检索。
- 为表格行生成 row text，用于语义召回。
- 增加可选向量索引，支持 `bge-m3` 或其他中文 embedding 模型。
- 增加重排序模块，先保留可配置接口，后续接入 reranker。
- `/search` 返回更稳定的 `score`、`position` 和证据类型。

验收标准：

- `POST /search` 能同时检索文本证据和表格证据。
- 支持 `source_type`、`doc_id`、`top_k` 过滤。
- 检索结果可直接用于 `/ask` 的证据引用。

### 阶段三：FastAPI 后端工程化

目标：将当前标准库 HTTP 服务迁移为正式 FastAPI 服务，同时保持 SPEC 不变。

建议目录：

```text
src/jinrong/api/
  app.py
  schemas.py
  routes.py
  dependencies.py
```

任务：

- 用 Pydantic 定义请求和响应模型。
- 将 `services.py` 中的服务函数挂接到 FastAPI router。
- 保持已有路径与 JSON 字段不变。
- 增加统一错误响应格式。
- 增加 API 文档页面和 CORS 配置。

验收标准：

- 旧前端无需修改即可调用新 FastAPI 后端。
- `GET /openapi.json` 可自动生成。
- API smoke test 覆盖 `/health`、`/ask`、`/search`、`/documents`、`/kb/status`、`/eval`。

### 阶段四：React 前端工程化

目标：从无构建 React 演示页升级为 Vite + React 工作台。

建议目录：

```text
frontend/
  package.json
  src/
    App.jsx
    api.js
    pages/
      DashboardPage.jsx
      AskPage.jsx
      SearchPage.jsx
      DocumentsPage.jsx
      KbStatusPage.jsx
      EvalPage.jsx
    components/
      EvidenceCard.jsx
      DocumentTable.jsx
      StatusBadge.jsx
```

页面：

- 工作台：展示文档数、chunk 数、表格单元格数、评测准确率。
- 问答页：输入问题或 QA 编号，展示答案、置信度、route 和证据。
- 证据检索页：检索文本片段和表格证据。
- 文档库页：按文件类型、关键词、doc_id 浏览。
- 知识库状态页：展示构建状态和失败文件。
- 评测中心：运行 Excel/Text/All 评测并展示结果。

验收标准：

- 桌面端和移动端均无布局错位。
- 问答结果中的证据可读、可追踪。
- 表格证据能明确展示 sheet、cell、单位和原始值。

### 阶段五：可信问答与拒答机制

目标：让系统从“能答题”升级为“可信问答”。

任务：

- 增加证据充分性判断。
- 增加无证据拒答。
- 增加多证据合并回答。
- 增加答案中的数字、日期、机构名和证据一致性校验。
- 为开放式问题输出引用证据列表。

验收标准：

- 没有证据时不编造答案。
- 每个答案至少有一个可追踪证据。
- 表格计算题能展示计算公式。
- 多事实问题能返回多个证据来源。

## 5. 下一步优先级

建议按下面顺序继续开发：

1. 补齐运行环境依赖，确保 CLI、API、评测命令在新环境可直接运行。
2. 做全量 `build-kb` 的批处理和错误审计，解决 500 文件完整入库。
3. 将当前 HTTP 服务迁移到 FastAPI，但保持 `docs/SPEC.md` 的接口不变。
4. 将 `frontend/index.html` 迁移为 Vite + React 工程。
5. 增加 BM25/向量混合检索和证据重排序。
6. 增加拒答、证据充分性和开放式 RAG 生成。

## 6. 当前可运行命令

安装依赖后建议使用：

```powershell
pip install -e .
$env:PYTHONPATH = ".\src"
python -m jinrong.cli build-manifest
python -m jinrong.cli build-kb --qa-only
python -m jinrong.cli eval-all
python -m jinrong.cli serve --port 8000
```

全量入库命令：

```powershell
$env:PYTHONPATH = ".\src"
python -m jinrong.cli build-kb
```

全量入库可能耗时较长，后续应改造成可断点续跑、分批构建和失败重试。

## 7. 执行记录

### 2026-07-28：第一步，补齐运行环境依赖

已执行：

```powershell
pip install -e .
python -m jinrong.cli kb-status
python -m compileall -q src
python -m jinrong.cli eval-all
```

验证结果：

- 项目已作为 editable package 安装成功。
- `pdfplumber` 等缺失依赖已安装。
- `python -m jinrong.cli kb-status` 可正常读取当前知识库状态。
- `python -m compileall -q src` 通过。
- `python -m jinrong.cli eval-all` 通过，当前 QA 评测为 `300/300`，准确率 `1.0`。

当前知识库状态：

| 指标 | 数量 |
| --- | ---: |
| 已入库文档 | 49 |
| 文本块 | 307 |
| 表格单元格事实 | 2412 |
| 构建错误 | 0 |

下一步进入“全量数据清洗入库”：将当前 QA 覆盖版知识库扩展为覆盖 500 份文件的完整 RAG 知识库，并补充错误审计与分批构建机制。

### 2026-07-28：第二步，全量数据清洗入库

已完成代码改造：

- `build-kb` 改为逐文件处理、流式写入 JSONL，避免全量 Excel 清洗时占用过高内存。
- 新增 `data/processed/kb_build_state.jsonl`，记录每个文件的处理状态、chunk 数、cell fact 数和更新时间。
- 新增 `reports/kb_build_errors.json`，记录失败文件、失败阶段、错误类型和是否可重试。
- `build-kb` 新增 `--resume`、`--retry-failed`、`--limit` 参数，支持断点续跑、失败重试和小批量 smoke test。
- 新增 `xlrd` 作为 `.xls` 纯 Python 解析兜底；`.xlsx` 继续使用 `openpyxl`。
- `.doc` 优先尝试 LibreOffice 转换，若本机没有 LibreOffice，则使用二进制兜底抽取。

已执行：

```powershell
pip install -e .
python -m compileall -q src
python -m jinrong.cli build-kb --limit 10
python -m jinrong.cli build-kb
python -m jinrong.cli kb-status
python -m jinrong.cli eval-all
```

全量入库结果：

| 指标 | 数量 |
| --- | ---: |
| Manifest 文件数 | 500 |
| 已处理文档 | 500 |
| 文本块 | 1094 |
| 表格单元格事实 | 83555 |
| 构建状态记录 | 500 |
| 构建错误 | 0 |

验证结果：

- `data/processed/text_chunks.jsonl` 已生成全量文本块。
- `data/processed/table_cells.jsonl` 已生成全量表格单元格事实。
- `data/processed/kb_stats.json` 已更新为全量状态。
- `reports/kb_build_errors.json` 为空数组。
- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

下一步进入“RAG 检索增强”：在现有全量文本块和表格事实之上增加 BM25 检索、表格 row text 和可选向量索引。

### 2026-07-28：第三步，RAG 检索增强第一版

已完成代码改造：

- 新增 `src/jinrong/retrieval.py`，实现本地 BM25 检索，不依赖外部向量模型或服务。
- 新增 `data/processed/table_rows.jsonl`，将 Excel 单元格事实聚合为行级证据。
- `build-kb` 现在同时输出文本块、单元格事实和表格行证据。
- `/search` 和 CLI `search` 已接入 BM25：
  - 文本资料检索 `text_chunks.jsonl`。
  - Excel 资料优先检索 `table_rows.jsonl`。
  - BM25 无结果时回退到归一化文本覆盖率检索。
- 搜索结果新增 `evidence_type` 和 `index` 字段，便于前端区分证据来源和检索方式。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli build-kb
python -m jinrong.cli kb-status
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --top-k 3
python -m jinrong.cli search "2026年2月 人身险 原保险保费收入" --source-type excel --top-k 3
python -m jinrong.cli eval-all
```

当前知识库状态：

| 指标 | 数量 |
| --- | ---: |
| 文档 | 500 |
| 文本块 | 1094 |
| 表格单元格事实 | 83555 |
| 表格行级证据 | 15775 |
| 构建错误 | 0 |

验证结果：

- PDF 搜索可命中《银行函证工作操作指引》相关文本块。
- Excel 搜索可命中“2026年2月人身险公司经营情况表 / 原保险保费收入”的表格行证据。
- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

下一步可以继续做两件事之一：

1. 接入可选向量索引和 reranker，形成 BM25 + dense retrieval + rerank 的混合检索。
2. 先迁移 FastAPI 后端，把当前稳定的服务接口工程化。

### 2026-07-28：第四步，FastAPI 后端工程化

已完成代码改造：

- 新增 `src/jinrong/api/app.py`，提供 FastAPI 应用入口。
- 新增 `src/jinrong/api/routes.py`，将 `services.py` 中的服务能力挂接到 router。
- 新增 `src/jinrong/api/schemas.py`，用 Pydantic 定义 `AskRequest`、`SearchRequest` 和 `EvalRequest`。
- `python -m jinrong.cli serve` 默认优先启动 FastAPI/uvicorn。
- 保留 `src/jinrong/api_server.py` 作为旧标准库 HTTP fallback。
- `pyproject.toml` 已加入 `fastapi` 和 `uvicorn` 依赖。

保持兼容的接口：

- `GET /health`
- `GET /openapi.json`
- `POST /ask`
- `POST /search`
- `GET /documents`
- `GET /documents/{doc_id}`
- `GET /kb/status`
- `POST /eval`

已执行：

```powershell
pip install -e .
python -m compileall -q src
python -m jinrong.cli eval-all
```

FastAPI TestClient 已验证：

- `GET /health` 返回 200。
- `GET /kb/status` 返回 500 文档全量知识库状态。
- `GET /documents` 和 `GET /documents/{doc_id}` 正常。
- `GET /openapi.json` 正常。
- `POST /search` 正常返回 `bm25_processed_jsonl` 检索结果。
- `POST /ask` 正常。
- `POST /eval` 正常。

真实 HTTP 启动验证：

- `python -m jinrong.cli serve --host 127.0.0.1 --port 8011` 可启动。
- `GET /health` 返回 `ok`。
- `POST /search` 查询“银行函证 工作质量 效率”可命中 `nfra_398`。

回归结果：

- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

下一步建议进入“React 前端工程化”：将当前 `frontend/index.html` 迁移为 Vite + React 项目，并继续保持上述 API contract 不变。

### 2026-07-28：第五步，React 前端工程化

已完成代码改造：

- 将 `frontend/index.html` 从 CDN React 单页应用迁移为 Vite + React 入口。
- 新增 `frontend/package.json` 和 `frontend/vite.config.js`。
- 新增 `frontend/src/main.jsx`、`frontend/src/App.jsx`、`frontend/src/api.js`、`frontend/src/components.jsx`、`frontend/src/styles.css`。
- 页面扩展为：
  - 工作台
  - 问答
  - 证据检索
  - 文档库
  - 知识库状态
  - 评测中心
- 前端继续默认调用 `http://127.0.0.1:8000`，保持后端 API contract 不变。
- 使用 `lucide-react` 提供导航与状态图标。

已执行：

```powershell
cd frontend
npm install
npm run build
```

联调验证：

- 启动 FastAPI 后端：`python -m jinrong.cli serve --host 127.0.0.1 --port 8000`。
- 启动 Vite 前端：`npm run dev -- --port 5173`。
- Playwright + Edge smoke test 已通过。
- 已生成桌面截图：`reports/vite_frontend_smoke.png`。
- 已生成移动端截图：`reports/vite_frontend_mobile_smoke.png`。

下一步建议进入“可信问答增强”：增加开放式 RAG 回答、证据充分性判断、无证据拒答和答案一致性校验。

### 2026-07-28：第六步，可信问答增强第一版

已完成代码改造：

- 新增 `src/jinrong/trusted_qa.py`，实现开放式 RAG 问答。
- 普通开放式问题现在会先调用全量知识库检索，再基于 top evidence 生成受控答案。
- 增加证据充分性判断：
  - 抽取问题关键短语。
  - 检查 top evidence 的关键词覆盖。
  - 结合检索分数判断证据是否足够。
- 增加无证据拒答：
  - 证据不足时返回 `route=rag_refusal`。
  - `answer_text` 固定为“无法根据当前资料确定。”。
- 增加答案一致性检查：
  - 检查答案中出现的数字是否能在证据文本中找到。
  - 检查结果写入 `debug.consistency`。
- `ask.py` 已接入可信 RAG 开放式问答。
- Excel 问答已从只支持 `.xlsx` 扩展为同时支持 `.xls/.xlsx`。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli ask --question "银行函证工作如何提高质量和效率？"
python -m jinrong.cli ask --question "宇宙飞船发动机保修期是多少？"
python -m jinrong.cli eval-all
```

验证结果：

- “银行函证工作如何提高质量和效率？”返回 `route=rag_open`，置信度 `high`，证据数 3。
- “宇宙飞船发动机保修期是多少？”返回 `route=rag_refusal`。
- FastAPI `/ask` 对上述两个问题均验证通过。
- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

当前边界：

- 开放式答案在第六步时仍是基于证据抽取和模板生成；第七步已接入可选 LLM 受控生成。
- 拒答策略是关键词覆盖 + 检索分数的第一版规则，后续需要构造拒答评测集。
- 多证据综合回答当前较保守，后续可增加证据压缩和分点归纳。

### 2026-07-28：第七步，LLM 受控生成

已完成代码改造：

- 新增 `src/jinrong/llm.py`，支持 OpenAI-compatible Chat Completions 调用。
- LLM 通过环境变量启用，不写入任何密钥：
  - `JINRONG_LLM_API_KEY`
  - `JINRONG_LLM_BASE_URL`
  - `JINRONG_LLM_MODEL`
  - `JINRONG_LLM_TIMEOUT`
- `trusted_qa.py` 已接入 LLM 受控生成：
  - 证据充分后才调用 LLM。
  - LLM 必须只依据证据回答。
  - LLM 必须输出 JSON。
  - LLM 调用失败或未配置 Key 时回退本地模板答案。
  - LLM 答案数字一致性检查失败时回退本地模板答案。
- `.gitignore` 已忽略 `.env` 和 `.env.*`，避免误提交密钥。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli ask --question "银行函证工作如何提高质量和效率？"
python -m jinrong.cli ask --question "宇宙飞船发动机保修期是多少？"
python -m jinrong.cli eval-all
```

降级验证：

```powershell
$env:JINRONG_LLM_API_KEY = "test-key"
$env:JINRONG_LLM_BASE_URL = "http://127.0.0.1:9/v1"
$env:JINRONG_LLM_TIMEOUT = "1"
python -m jinrong.cli ask --question "银行函证工作如何提高质量和效率？"
```

验证结果：

- 未配置 API Key 时，系统使用 `generation_mode=template`，开放式问答可正常返回。
- 配置不可用 LLM 地址时，系统记录 `llm_used=true` 和错误原因，并回退模板答案。
- 资料库外问题仍返回 `route=rag_refusal`。
- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

当前边界：

- 本地未配置真实 LLM API Key，因此未做真实模型生成质量评测。
- 当前只支持 OpenAI-compatible Chat Completions 协议。
- 后续需要增加开放式问答人工评测集，评估 LLM 答案是否更完整、更忠实。

### 2026-07-28：第八步，文档元数据增强与条款级 text_units

已完成代码改造：

- 新增 `src/jinrong/metadata_extractor.py`，从 manifest、标题和首段文本中抽取增强元数据。
- 新增 `src/jinrong/structure_parser.py`，把 Word/PDF 文本 chunk 进一步解析为页码、章节、条款级文本单元。
- `src/jinrong/cli.py` 新增 `build-metadata` 和 `build-text-units`。
- `src/jinrong/services.py` 已将 `/documents` 和 `/documents/{doc_id}` 合并 `document_metadata.jsonl`。
- `/search` 对 Word/PDF 优先检索 `text_units.jsonl`，返回 `evidence_type=text_unit`，并在 `position` 中给出 `unit_id/chunk_id/page_no/section_path/article_no`。
- `/kb/status` 已增加 `document_metadata` 和 `text_units` 统计。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli build-metadata
python -m jinrong.cli build-text-units
python -m jinrong.cli kb-status
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --top-k 2
python -m jinrong.cli documents --source-type pdf --query 银行函证 --limit 2
python -m jinrong.cli eval-all
```

生成结果：

| 产物 | 数量 |
| --- | ---: |
| `data/processed/document_metadata.jsonl` | 500 |
| `data/processed/text_units.jsonl` | 7132 |
| `reports/metadata_extraction_report.json` | 1 |
| `reports/text_units_report.json` | 1 |

元数据抽取覆盖：

| 字段 | 已填充数量 |
| --- | ---: |
| `publisher` | 117 |
| `publish_date` | 5 |
| `doc_no` | 11 |
| `source_url` | 0 |
| `attachment_url` | 0 |

文本结构单元覆盖：

| 指标 | 数量 |
| --- | ---: |
| 文本结构单元 | 7132 |
| 带页码 | 3409 |
| 带章节路径 | 7005 |
| 带条款编号 | 1828 |

验证结果：

- `POST /search` 查询“银行函证 工作质量 效率”可命中 `nfra_398`，证据类型为 `text_unit`，并返回 `page_no=1`。
- `GET /documents` 查询“银行函证”可返回合并后的 `publisher/doc_no/business_domain/regulatory_topic`。
- FastAPI TestClient smoke 覆盖 `/kb/status`、`/search`、`/documents`。
- `python -m jinrong.cli eval-all` 仍为 `300/300`，准确率 `1.0`。

当前边界：

- `source_url/attachment_url/column` 仍然缺失，因为当前本地数据只有下载后的文件，没有原始下载 manifest 或抓取日志。
- 发文机关、发布日期、文号是规则抽取第一版，覆盖率还不够竞赛级，需要继续补采来源和增强规则。
- `text_units` 已可用于证据定位，但复杂 PDF 版式、扫描件、双栏和表格内条款仍需要 MinerU/OCR 或专业 parser 增强。

下一步建议进入“来源 URL 补采 + 元数据过滤接口增强”：建立 `source_catalog.jsonl` 对齐流程，把来源页面 URL、附件 URL、栏目补回知识库，并让 `/documents`、`/search` 支持 `publisher/business_domain/publish_date/article_no` 等过滤。

### 2026-07-28：第九步，来源 URL 补采入口与元数据过滤接口增强

已完成代码改造：

- 新增 `src/jinrong/source_catalog.py`，支持从 `.csv/.jsonl/.json` 来源 catalog 合并 `source_url/attachment_url/column` 等字段。
- `src/jinrong/config.py` 新增：
  - `MANIFEST_ENRICHED_PATH`
  - `SOURCE_CATALOG_TEMPLATE_PATH`
  - `SOURCE_ENRICHMENT_REPORT`
- `src/jinrong/cli.py` 新增：
  - `export-source-template`
  - `enrich-manifest --source-catalog ...`
- 服务层优先读取 `data/processed/manifest_enriched.jsonl`；如果不存在，则回退 `manifest.jsonl`。
- `build-metadata` 在存在增强 manifest 时优先使用增强 manifest，保证来源 URL 能继续进入 `document_metadata.jsonl`。
- `/documents` 和 CLI `documents` 新增过滤：
  - `publisher`
  - `publish_date_from`
  - `publish_date_to`
  - `business_domain`
  - `regulatory_topic`
  - `doc_no`
  - `column`
  - `has_source_url`
  - `article_no`
- `/search` 和 CLI `search` 新增同样的元数据过滤，并在证据结果中返回文档增强元数据字段。
- FastAPI schema、FastAPI routes、标准库 HTTP fallback 均已同步参数。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli export-source-template
python -m jinrong.cli enrich-manifest --source-catalog <临时smoke_catalog.csv> --output <临时manifest_enriched_smoke.jsonl>
python -m jinrong.cli documents --business-domain 银行函证 --limit 2
python -m jinrong.cli documents --has-source-url --limit 2
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --business-domain 银行函证 --top-k 2
python -m jinrong.cli search "银行函证" --source-type pdf --doc-no 财会〔2022〕39号 --top-k 1
```

验证结果：

- `export-source-template` 已生成 `data/intermediate/source_catalog_template.csv`，覆盖 500 份文档。
- smoke catalog 可按 `doc_id` 匹配并合并来源 URL、附件 URL、栏目等字段；测试输出写入临时文件，验证后已清理，没有污染正式 `manifest_enriched.jsonl`。
- `documents --business-domain 银行函证` 返回 `nfra_397/nfra_398`。
- `documents --has-source-url` 当前返回 0，符合现状：还没有真实来源 catalog。
- `search --business-domain 银行函证` 能命中 `nfra_398`，证据类型为 `text_unit`，证据中带 `publisher/doc_no/business_domain/regulatory_topic`。
- FastAPI TestClient smoke 覆盖 `/kb/status`、`/documents?business_domain=...`、`POST /search`。

当前边界：

- 工程入口已经完成，但真实 `source_url/attachment_url/column` 仍需来自下载日志、人工补表或爬虫补采。
- 当前没有把 smoke 的假 URL 写入正式增强 manifest。
- 版本关系 `supersedes/superseded_by/effective_status` 还未实现。

下一步建议进入“真实来源 catalog 补齐 + 语义检索第一版”：一边补真实 URL，一边接入 BM25 + embedding 的 hybrid retrieval，以提升同义改写和复杂问题召回。

### 2026-07-28：第十步，BM25 + embedding 混合检索第一版

已完成代码改造：

- 新增 `src/jinrong/vector_index.py`。
- `src/jinrong/config.py` 新增：
  - `INDEX_DIR`
  - `TEXT_VECTOR_INDEX_PATH`
  - `TABLE_VECTOR_INDEX_PATH`
  - `VECTOR_INDEX_MANIFEST_PATH`
- `src/jinrong/cli.py` 新增 `build-vector-index`。
- CLI `search` 新增 `--retrieval bm25|hybrid`。
- FastAPI `POST /search` 新增 `retrieval` 参数。
- 标准库 HTTP fallback 已同步 `retrieval` 参数。
- `src/jinrong/services.py` 已接入 hybrid 检索：
  - BM25 召回。
  - 本地哈希 embedding 向量召回。
  - RRF 融合排序。
  - `/kb/status` 返回向量索引状态。

当前第一版 embedding：

- 名称：`local_hashing_v1`
- 维度：4096
- 特点：不依赖外部模型、不联网、可复现。
- 边界：它是工程第一版，不等价于 bge-m3 这类语义模型；后续可替换为真实 embedding。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli build-vector-index
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --business-domain 银行函证 --retrieval hybrid --top-k 2
python -m jinrong.cli search "2026年2月 人身险 原保险保费收入" --source-type excel --retrieval hybrid --top-k 2
python -m jinrong.cli kb-status
```

生成结果：

| 产物 | 数量 |
| --- | ---: |
| `data/index/text_vectors.jsonl` | 7132 |
| `data/index/table_row_vectors.jsonl` | 15775 |
| `data/index/vector_index_manifest.json` | 1 |

验证结果：

- PDF hybrid 检索返回 `index=hybrid_bm25_hash_embedding`，命中 `nfra_398`。
- Excel hybrid 检索可命中 `nfra_003` 的“原保险保费收入”行。
- FastAPI TestClient smoke 验证 `retrieval=hybrid` 可用。
- `/kb/status` 返回 `vector_index=true`、`text_vectors=7132`、`table_row_vectors=15775`。

当前边界：

- `local_hashing_v1` 主要用于打通 hybrid 检索工程链路，对深层语义改写的提升有限。
- Excel hybrid 示例中仍可能召回相近但不够精确的行，需要 reranker 压制。
- 尚未建立专门的检索评测集来量化 BM25 与 hybrid 的召回差异。

下一步建议进入“reranker 第一版 + 检索评测集”：先构造一组 evidence-level 查询，再用规则 reranker 或可选模型 reranker 对 hybrid 候选重排。

### 2026-07-28：第十一步，reranker 第一版与检索评测集

已完成代码改造：

- 新增 `src/jinrong/reranker.py`，实现 `rule_reranker_v1`。
- 新增 `src/jinrong/eval_retrieval.py`，实现 evidence-level 检索评测。
- 新增 `data/eval/retrieval_eval.jsonl`，当时包含 8 条第一版检索评测样例；第十二步已扩充到 60 条。
- `src/jinrong/config.py` 新增：
  - `EVAL_DIR`
  - `RETRIEVAL_EVAL_PATH`
  - `RETRIEVAL_EVAL_REPORT`
- CLI `search` 新增 `--rerank`。
- FastAPI `POST /search` 新增 `rerank` 参数。
- 标准库 HTTP fallback 已同步 `rerank` 参数。
- CLI 新增：
  - `eval-retrieval --retrieval bm25|hybrid --rerank --top-k N`

reranker 第一版策略：

- 对候选证据计算正文 token 覆盖、整体 token 覆盖、短语命中、日期短语命中、标题命中、元数据命中、位置命中。
- 保留召回阶段分数为 `base_score`。
- 重排后 `score` 使用规则特征重新计算。
- 每条证据返回 `rerank.method=rule_reranker_v1` 和关键特征，便于审计。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank --top-k 5
python -m jinrong.cli search "银行函证 回函 工作日" --source-type pdf --business-domain 银行函证 --retrieval hybrid --rerank --top-k 2
python -m jinrong.cli search "大面积投诉 社会群体性事件 数据安全" --business-domain 消费者权益保护 --retrieval hybrid --rerank --top-k 1
```

评测结果：

| 指标 | 结果 |
| --- | ---: |
| 检索评测样例 | 8 |
| top1 | 8 |
| top3 | 8 |
| top5 | 8 |
| top1_accuracy | 1.0 |
| top3_accuracy | 1.0 |
| top5_accuracy | 1.0 |

当前边界：

- 评测集第一版只有 8 条，属于 smoke/evidence-level 验证，不是完整 benchmark。
- `rule_reranker_v1` 是规则重排器，不等价于 bge-reranker 或 cross-encoder。
- 后续应扩充评测集，加入同义改写、多跳、表格混淆、旧版新规混淆、不可回答问题。

下一步建议进入“模型级 reranker 或开放式检索评测扩充”：如果本机可安装模型依赖，可接入 bge-reranker；如果先不依赖模型，则优先把检索评测集扩到 50-100 条。

### 2026-07-28：第十二步，检索评测集扩充到 60 条

已完成代码改造：

- 新增 `src/jinrong/retrieval_eval_builder.py`。
- CLI 新增：
  - `build-retrieval-eval --target-size N --retrieval bm25|hybrid --rerank`
- 为大 JSONL 加载增加进程内缓存，降低检索评测时反复读取 `text_units/table_rows/vector_index` 的开销。
- `data/eval/retrieval_eval.jsonl` 已从 8 条扩充到 60 条。

生成策略：

- 从 `text_units.jsonl` 生成文本证据候选。
- 从 `table_rows.jsonl` 生成表格行证据候选。
- 文本和表格候选交替验证，避免评测集偏科。
- 使用当前 `hybrid + rerank` 检索链路筛选，只保留 top1 可命中的稳定样例。

已执行：

```powershell
python -m compileall -q src
python -m jinrong.cli build-retrieval-eval --target-size 60 --retrieval hybrid --rerank
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank --top-k 5
python -m jinrong.cli eval-retrieval --retrieval hybrid --top-k 5
python -m jinrong.cli eval-retrieval --retrieval bm25 --top-k 5
```

生成结果：

| 类型 | 数量 |
| --- | ---: |
| `text_unit` | 30 |
| `table_row` | 30 |
| 总计 | 60 |

对比结果：

| 检索模式 | top1 | top3 | top5 |
| --- | ---: | ---: | ---: |
| BM25 | 59/60 | 60/60 | 60/60 |
| Hybrid | 55/60 | 58/60 | 58/60 |
| Hybrid + rule reranker | 60/60 | 60/60 | 60/60 |

当前边界：

- 评测集是自动生成并用当前系统筛选过的 smoke/regression 集，不是人工标注的最终 benchmark。
- 当前生成评测集耗时较长，原因是会对候选逐条运行检索验证。
- 后续需要补人工设计的同义改写、多跳、旧版新规混淆、不可回答问题，才能更真实衡量检索能力。

下一步建议：继续扩充人工检索评测集，或接入模型级 reranker 后用这 60 条作为回归基线。
