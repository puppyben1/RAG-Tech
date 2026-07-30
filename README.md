# 金融监管可信 RAG MVP

当前实现优先打通 Excel 表格题闭环：

- 扫描 `wendang/data` 生成 manifest。
- 读取 `QA数据.xlsx`。
- 解析 `.xlsx` 工作表为单元格事实。
- 支持 Excel 选择题中的表格取数、表格比较、表格计算。
- 解析 `.docx/.pdf` 文本并用选项证据匹配回答 Word/PDF 选择题。
- 输出自动评测结果。

## 运行

使用 Codex 内置 Python：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli build-manifest
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli eval-excel
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli eval-text
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli eval-all
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli ask --qa-id Q001
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jinrong.cli serve --port 8000
```

如使用系统 Python，先设置源码路径：

```powershell
$env:PYTHONPATH = ".\src"
python -m jinrong.cli build-manifest
python -m jinrong.cli build-kb
python -m jinrong.cli export-source-template
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
python -m jinrong.cli build-metadata
python -m jinrong.cli build-text-units
python -m jinrong.cli build-vector-index
python -m jinrong.cli eval-excel
python -m jinrong.cli eval-text
python -m jinrong.cli eval-all
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank
python -m jinrong.cli ask --qa-id Q001
python -m jinrong.cli serve --port 8000
```

## HTTP API

启动服务：

```powershell
$env:PYTHONPATH = ".\src"
python -m jinrong.cli serve --port 8000
```

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/health
```

OpenAPI 风格接口说明：

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/openapi.json
```

按 QA 编号复现：

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/ask -ContentType 'application/json; charset=utf-8' -Body '{"qa_id":"Q001"}'
```

请求体格式：

```json
{
  "question": "问题文本",
  "options": {
    "A": "选项 A",
    "B": "选项 B",
    "C": "选项 C",
    "D": "选项 D"
  }
}
```

证据检索：

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/search -ContentType 'application/json; charset=utf-8' -Body '{"query":"银行函证","source_type":"pdf","top_k":3}'
```

文档列表：

```powershell
Invoke-RestMethod -Method GET -Uri 'http://127.0.0.1:8000/documents?source_type=pdf&limit=5'
```

评测：

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/eval -ContentType 'application/json; charset=utf-8' -Body '{"scope":"excel"}'
```

完整接口规格见 [docs/SPEC.md](docs/SPEC.md)。

系统运行机制与数据清洗说明见 [docs/SYSTEM_AND_DATA_PIPELINE.md](docs/SYSTEM_AND_DATA_PIPELINE.md)。

赛题要求对标、系统差距与后续实现方案见 [docs/REQUIREMENT_GAP_AND_IMPLEMENTATION_PLAN.md](docs/REQUIREMENT_GAP_AND_IMPLEMENTATION_PLAN.md)。

## 数据清洗与结构化

完整本地知识库当前由四类核心产物组成：

- `manifest.jsonl`：500 份文件的基础清单、大小、哈希和本地路径。
- `manifest_enriched.jsonl`：来源补采后的增强清单；存在时服务层优先读取。
- `document_metadata.jsonl`：增强元数据，包含发文机关、发布日期、文号、业务领域、监管主题等第一版抽取结果。
- `text_units.jsonl`：Word/PDF 页码、章节、条款级文本单元。
- `table_cells.jsonl` 与 `table_rows.jsonl`：Excel 单元格事实和行级 RAG 证据。
- `data/index/*_vectors.jsonl`：本地哈希 embedding 向量索引，用于 `retrieval=hybrid`。

推荐重建顺序：

```powershell
python -m jinrong.cli build-manifest
python -m jinrong.cli build-kb
python -m jinrong.cli export-source-template
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
python -m jinrong.cli build-metadata
python -m jinrong.cli build-text-units
python -m jinrong.cli build-vector-index
python -m jinrong.cli kb-status
```

`export-source-template` 会导出 `data/intermediate/source_catalog_template.csv`，用于填写 `source_url/attachment_url/column`。当前已验证状态：500 份文件全部入库，`document_metadata=500`，`text_units=7132`，`text_vectors=7132`，`table_row_vectors=15775`，构建错误数为 0；由于尚未提供真实来源 catalog，`has_source_url=true` 当前返回 0 份文档。

混合检索示例：

```powershell
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --retrieval hybrid --top-k 3
```

启用 reranker：

```powershell
python -m jinrong.cli search "银行函证 工作质量 效率" --source-type pdf --retrieval hybrid --rerank --top-k 3
```

检索评测：

```powershell
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank --top-k 5
```

重建检索评测集：

```powershell
python -m jinrong.cli build-retrieval-eval --target-size 60 --retrieval hybrid --rerank
```

## LLM 受控生成

开放式 RAG 问答支持可选 LLM 受控生成。未配置 API Key 时，系统自动使用本地模板答案；配置后会把检索到的证据发送给 OpenAI-compatible Chat Completions 接口，并要求模型只能依据证据输出 JSON。

```powershell
$env:JINRONG_LLM_API_KEY = "你的 API Key"
$env:JINRONG_LLM_BASE_URL = "https://api.openai.com/v1"
$env:JINRONG_LLM_MODEL = "gpt-4o-mini"
python -m jinrong.cli ask --question "银行函证工作如何提高质量和效率？"
```

可选变量：

- `JINRONG_LLM_API_KEY`：LLM API Key；也兼容 `OPENAI_API_KEY`。
- `JINRONG_LLM_BASE_URL`：OpenAI-compatible API 地址，默认 `https://api.openai.com/v1`。
- `JINRONG_LLM_MODEL`：模型名，默认 `gpt-4o-mini`。
- `JINRONG_LLM_TIMEOUT`：请求超时时间，默认 30 秒。

## 前端

前端已迁移为 Vite + React 工程：

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

使用方式：

1. 启动后端：

```powershell
python -m jinrong.cli serve --port 8000
```

2. 启动前端：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

3. 打开 `http://127.0.0.1:5173`。

页面包含工作台、问答、证据检索、文档库、知识库状态、评测中心六个视图，默认调用 `http://127.0.0.1:8000`。

生产构建：

```powershell
cd frontend
npm run build
```

## 当前边界

第一版对 QA 中的 `.xlsx` Excel 题做确定性求解，并对 `.docx/.pdf` 做文本抽取与选择题匹配。旧 `.doc` 文件当前使用二进制文本兜底抽取，可靠性低于 `.docx/.pdf`；后续建议接入 LibreOffice 或 antiword 做正式转换。
