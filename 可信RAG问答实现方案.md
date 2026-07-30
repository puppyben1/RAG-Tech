# 面向银行业监管制度与统计报表的可信 RAG 问答实现方案

## 1. 任务理解

本项目面向南京银行赛题“面向银行业监管制度与统计报表的可信 RAG 问答”。系统需要从公开监管制度、政策规章、Word/PDF 文本文件、Excel 统计附件中检索依据，并回答监管条款、指标口径、统计取数、表格比较、表格计算、多事实检索和场景合规判断类问题。

核心目标不是普通问答，而是“可溯源、可核验、低幻觉”的监管知识问答。每个答案都应能返回最小充分证据，包括文件名、章节/条款、页码或表格单元格、工作表、单位、原始值和本地路径。

当前已读材料显示：

- 赛题要求支持 Word、PDF、Excel 三类文件解析。
- 本地 `wendang/data` 是下载后的全部原始附件数据，共约 500 个文件，主要为 `.xls/.xlsx`，另有 `.pdf/.docx/.doc`。
- `QA数据.xlsx` 中有 300 条选择题，来源类型为 Excel、Word、PDF 各 100 条。
- QA 题型包括表格取数、表格比较、表格计算、单事实检索、多事实检索。
- Excel 题的 evidence 已细到工作表、单元格、单位和原始值，因此表格必须结构化处理，不能只转纯文本。

## 2. 总体架构

建议实现为一套离线入库 + 在线问答的 RAG 服务：

```text
原始文件
  -> 文档解析层
  -> 结构化知识库
  -> 混合索引
  -> 查询理解
  -> 多路检索
  -> 重排序与证据压缩
  -> 受控生成/选择题判别
  -> 答案 + 证据 + 拒答/澄清
```

推荐技术栈：

- 语言：Python。
- API：FastAPI。
- 文本解析：python-docx、LibreOffice headless、PyMuPDF/pdfplumber。
- 表格解析：LibreOffice 将 `.xls` 转 `.xlsx`，openpyxl 读取单元格、合并单元格、sheet、坐标。
- 结构化存储：SQLite 或 DuckDB 保存文档元数据、文本块、表格单元格、行列语义。
- 检索索引：BM25 + 向量索引。原型阶段用 FAISS，服务化阶段可换 Qdrant/Milvus。
- 中文向量模型：`BAAI/bge-m3` 或 `bge-large-zh-v1.5`。
- 重排序：`bge-reranker-v2-m3`。
- 大模型：可配置 OpenAI API、通义、智谱、DeepSeek 等，接口层统一抽象。

## 3. 数据处理设计

### 3.1 文件清单与元数据

为每个文件生成统一 `doc_id`，并记录：

- `doc_id`
- `title`
- `file_name`
- `local_path`
- `file_ext`
- `source_type`: `word/pdf/excel`
- `business_domain`: 银行业、保险业、资本管理、函证、行政许可等，可由文件名规则 + LLM 辅助标注
- `period`: 年/月/季度，主要从 Excel 文件名抽取
- `source_url`: 若原始 manifest 不存在，则先留空或后续补采
- `sha256`
- `created_at`

注意：赛题说明中“每个下载文件均在 manifest 中记录来源页面 URL、附件 URL、本地路径、文件大小、SHA-256、标题、栏目、doc_id”等描述，是理想的数据管理形态。当前本地可直接以 `wendang/data` 作为原始下载数据目录；若没有单独提供 manifest 文件，则入库脚本应主动扫描 `wendang/data` 并生成项目自己的 manifest，至少补齐本地路径、文件大小、SHA-256、标题、文件类型、期间、doc_id 等字段。来源页面 URL 和附件 URL 若本地数据中没有，则先置空，后续需要时再补采。

### 3.2 Word/PDF 解析

输出两类数据：

1. 文档级元数据：标题、文号、发布机关、发布日期、附件名。
2. 条款级文本块：保留标题层级、条款编号、页码或段落序号。

文本块建议字段：

- `chunk_id`
- `doc_id`
- `section_path`
- `article_no`
- `page_no`
- `text`
- `norm_text`
- `char_start`
- `char_end`
- `evidence_label`

切分策略：

- 优先按“章、节、条、（一）、1.”等监管文本层级切分。
- 每个 chunk 控制在 300-800 中文字。
- 对定义、禁止性规定、金额阈值、期限等句子保留完整上下文。
- 对 PDF 同时保存页码，便于证据定位。
- 对 `.doc` 先用 LibreOffice 转 `.docx` 或 `.pdf` 后解析。

### 3.3 Excel 结构化解析

Excel 是本赛题的关键。每个工作表需要生成两个索引视图：

1. 表格单元级事实表，用于精确取数。
2. 表格文本化块，用于语义召回。

单元级事实字段：

- `table_id`
- `doc_id`
- `sheet_name`
- `cell_ref`: 如 `C5`
- `row_index`
- `col_index`
- `row_header`: 如“全国合计”“原保险保费收入”
- `col_header`: 如“合计”“本年累计/截至当期”
- `unit`: 如“亿元”“万件”“%”
- `value_raw`
- `value_num`
- `period`
- `table_title`
- `evidence_label`

表头识别规则：

- 前 1-3 行通常包含标题和单位。
- 识别包含“单位：”的单元格作为单位。
- 识别第一个非空标题行作为表名。
- 对纵向指标表，首列多为指标名，后续列为口径。
- 对地区表，首列多为地区，后续列为险种/指标。
- 对合并单元格要展开父表头，形成多级列名。

文本化块示例：

```text
文件：2023年12月全国各地区原保险保费收入情况表
工作表：各地区数据（月度）
单位：亿元
行：全国合计
合计=51246.71(C4)，财产保险=13606.98(D4)，寿险=27646.42(E4)，意外险=958.77(F4)，健康险=9034.54(G4)
```

这样既支持语义检索，也支持最终答案精确回填。

## 4. 索引设计

### 4.1 文本索引

建立三类索引：

- BM25：处理文件名、条款编号、精确术语、金额/日期/文号。
- 向量索引：处理自然语言改写、同义表达和多事实问题。
- 元数据过滤：处理文件名、年份、月份、季度、文件类型、主题。

文本 chunk 入库时，索引内容建议拼接：

```text
标题 + 发文机关 + 文件名 + 章节路径 + 条款编号 + 正文
```

### 4.2 表格索引

表格建立两层索引：

- `table_cell_index`：结构化精确查询。
- `table_row_text_index`：每一行或逻辑行文本化后进入 BM25/向量索引。

表格题优先通过结构化查询解决：从问题中抽取文件名、工作表、行名、列名、期间、单位，然后在 `table_cell_index` 中匹配。若抽取不完整，再用 row text 检索召回候选表格行。

## 5. 在线问答流程

### 5.1 查询理解

先对用户问题分类：

- `excel_lookup`: 表格取数。
- `excel_compare`: 表格比较。
- `excel_calc`: 表格计算。
- `text_single_fact`: 单事实检索。
- `text_multi_fact`: 多事实检索。
- `compliance_judgement`: 场景合规判断。
- `out_of_scope`: 资料库外或依据不足。

同时抽取：

- 文件名或标题。
- 时间维度：年、月、季度。
- 指标名、行名、列名、单位。
- 监管主题、条款编号、主体、期限、金额阈值。
- 选择题选项 A/B/C/D，若存在。

### 5.2 检索策略

文本题：

1. 用文件名/主题/条款编号做元数据过滤。
2. BM25 召回 top 30。
3. 向量召回 top 30。
4. 合并去重后 rerank top 8。
5. 用证据压缩保留最相关句子和上下文。

表格题：

1. 若问题含明确文件名，先定位文件。
2. 若含工作表名，直接过滤 sheet。
3. 从单元级事实表匹配行头、列头、指标名。
4. 取数题返回单元格原值。
5. 比较题将候选指标数值排序，返回最大/最小/符合条件项。
6. 计算题执行明确算术，如差值、增长、占比，并返回计算公式。

选择题：

1. 不直接让模型“猜 A/B/C/D”。
2. 对每个选项分别做证据匹配或事实校验。
3. 计算每个选项的 evidence score。
4. 选择证据最强且不冲突的选项。
5. 输出 `answer`、`answer_text`、`evidence`。

### 5.3 生成控制

回答提示词必须约束：

- 只能依据检索证据回答。
- 数字、日期、文号、机构名称必须逐字引用或由表格计算得到。
- 若证据不足，返回“无法根据当前资料确定”，并说明缺少什么。
- 必须输出证据列表。
- 对规范强度区分“应当、不得、可以、原则上、鼓励”等。

开放问答输出格式：

```json
{
  "answer": "...",
  "evidence": [
    {
      "doc_id": "...",
      "source_title": "...",
      "local_path": "...",
      "section_path": "...",
      "page_no": null,
      "sheet_name": null,
      "cell_ref": null,
      "quote": "..."
    }
  ],
  "confidence": "high|medium|low",
  "need_clarification": false
}
```

选择题输出格式：

```json
{
  "id": "Q001",
  "answer": "A",
  "answer_text": "31739.18",
  "evidence": "文件...；工作表...；单元格 C5；单位...；原始值..."
}
```

## 6. 项目目录建议

```text
JINRONG/
  data/
    raw/                         # 原始文件，不修改
    processed/
      documents.jsonl
      chunks.jsonl
      tables.jsonl
      cells.parquet
    index/
      bm25/
      faiss/
      sqlite.db
  src/
    ingest/
      scan_files.py
      parse_word.py
      parse_pdf.py
      parse_excel.py
      build_metadata.py
    index/
      build_bm25.py
      build_vector.py
      build_table_index.py
    rag/
      query_analyzer.py
      retriever.py
      table_qa.py
      text_qa.py
      reranker.py
      generator.py
      answer_schema.py
    eval/
      run_qa_eval.py
      metrics.py
    api/
      main.py
  prompts/
    query_analyzer.md
    answer_generator.md
    option_verifier.md
  reports/
    eval_report.md
  README.md
```

## 7. 核心模块实现细节

### 7.1 `scan_files.py`

职责：

- 遍历 `wendang/nfra_page_attachments_500(1)`。
- 计算 sha256。
- 从文件名抽取序号、标题、年份、月份/季度。
- 生成 `documents.jsonl`。

### 7.2 `parse_excel.py`

职责：

- 将 `.xls` 通过 LibreOffice 转为临时 `.xlsx`。
- 用 openpyxl 读取所有工作表。
- 抽取标题、单位、表头、行头、单元格值。
- 生成 `tables.jsonl` 和 `cells.parquet`。
- 生成每行文本化 chunk，进入通用检索。

关键难点：

- 合并单元格表头展开。
- “本年累计/截至当期”等多级列头识别。
- 单位可能在标题行附近，也可能混在表格说明中。
- 数值需保留原始字符串和标准化数值。

### 7.3 `parse_word.py` / `parse_pdf.py`

职责：

- 解析正文、标题层级、条款编号。
- PDF 保存页码。
- Word 保存段落序号和章节路径。
- 对旧 `.doc` 做格式转换。

### 7.4 `query_analyzer.py`

职责：

- 问题分类。
- 抽取文件名、指标名、行列语义、时间、选项。
- 生成检索计划。

可先用规则 + 少量 LLM JSON 抽取，避免纯 LLM 不稳定。

### 7.5 `table_qa.py`

职责：

- 对 Excel 取数、比较、计算题执行确定性查询。
- 返回数值、单元格、单位、计算公式。

这是最应优先实现的模块，因为 QA 中 Excel 题完全可由结构化表格命中，准确率提升明显。

### 7.6 `text_qa.py`

职责：

- 对 Word/PDF 文本做混合检索和证据重排。
- 对多事实题做多证据合并。
- 对选择题逐项验证。

## 8. 评测方案

基于 `QA数据.xlsx` 建立自动评测：

- 选择题准确率：预测 `answer` 是否等于标准答案。
- 答案文本准确率：数值题比较数值容差，文本题比较归一化字符串。
- 证据命中率：预测证据中是否包含标准 `source_title/file_label`，Excel 题是否命中 sheet/cell。
- 拒答率：对人工构造库外问题，检查是否拒答。
- 关键字段错误率：统计数字、日期、文号、机构名错误。

阶段性目标：

- 第一阶段：Excel 100 题准确率达到 90% 以上。
- 第二阶段：Word/PDF 单事实题达到 85% 以上。
- 第三阶段：多事实题和混合场景题达到 80% 以上。

## 9. 实施里程碑

### M1：数据扫描与解析

- 完成文件扫描、sha256、基础元数据。
- 完成 `.xlsx/.xls` 解析和单元格事实表。
- 完成 `.docx/.pdf/.doc` 文本抽取。
- 产出 `documents.jsonl/chunks.jsonl/cells.parquet`。

### M2：检索与表格问答

- 建立 BM25、向量、表格索引。
- 实现表格取数、比较、计算。
- 跑通 Excel 100 条 QA 自动评测。

### M3：文本问答与选择题验证

- 实现文本混合检索、rerank、证据压缩。
- 实现 A/B/C/D 逐选项校验。
- 跑通 Word/PDF 200 条 QA 自动评测。

### M4：API 与可复现交付

- 提供 FastAPI `/ask` 和 `/batch_eval`。
- 输出评测报告。
- 编写 README、环境配置、复现实验命令。

## 10. 风险与对策

- `.xls` 解析不稳定：统一先用 LibreOffice 转 `.xlsx`，保留转换日志。
- 表头结构复杂：先做常见模板规则，再用 LLM 辅助识别异常表。
- 旧版/新版法规混淆：检索时强制加入发布日期、年份、标题过滤和版本排序。
- 多事实题漏证据：对每个事实子句单独检索，再合并证据。
- 模型幻觉：答案生成前做 evidence-only 约束，生成后做数字/日期/文号一致性校验。
- 来源 URL 缺失：当前以 `wendang/data` 作为原始下载数据目录；若未提供官方来源 URL/附件 URL，则先用本地路径和 SHA-256 溯源，后续需要时再补充官方 URL。

## 11. 推荐优先级

最优实现顺序：

1. 先做文件扫描和 Excel 单元格事实库。
2. 再做 QA 读取和 Excel 题自动评测。
3. 然后做 Word/PDF 文本 chunk、BM25 和向量混合检索。
4. 最后接入大模型生成、拒答策略和 API。

原因是当前 QA 中 Excel 题证据最结构化，能最快建立可验证闭环；文本题再通过混合检索和选项校验逐步提高准确率。

## 12. 开发路线选择

当前有两种思路：

### 路线一：从 0 开发

适合本赛题的核心模块：

- 文件扫描与自生成 manifest。
- Excel 单元格事实库。
- 表头、单位、期间、单元格坐标解析。
- 表格取数、比较、计算。
- 选择题逐选项证据验证。
- 证据格式化输出。

优点：

- 完全贴合赛题数据和评测方式。
- 对 Excel 题、证据命中、单元格定位更可控。
- 代码轻，便于解释和写报告。

缺点：

- 前期要自己搭建解析、索引、评测链路。
- 文本 RAG 的工程细节需要逐步补齐。

### 路线二：参考 GitHub 相似项目开发

可借鉴的开源方向包括：

- 普通 PDF/文档 RAG 项目：常见组合是 Streamlit/FastAPI + LangChain/LlamaIndex + FAISS/Chroma。
- 混合检索项目：可参考 BM25 + 向量召回 + rerank 的组织方式。
- 表格文档 RAG 项目：可参考表格转文本、表格行级索引、结构化字段抽取等做法。

适合借鉴的部分：

- API 服务结构。
- 向量库封装。
- 文档 chunk 和 embedding 流程。
- 前端问答页面。
- Docker/README/评测脚本组织方式。

不建议直接照搬的部分：

- PDF-only RAG 流程。
- 只把 Excel 转成纯文本 chunk 的做法。
- 完全依赖 LLM 从表格里猜数值的做法。
- 没有单元格级证据的数据结构。

### 推荐策略

采用“核心从 0 写，外围借鉴开源项目”的混合路线。

具体来说：

1. 数据解析、Excel 事实库、证据结构、评测脚本从 0 开发。
2. 文本 RAG 的工程骨架参考 LangChain/LlamaIndex/FAISS 类项目，但保持接口简单。
3. UI 和 API 可以后置，先保证命令行批量评测跑通。
4. 如果时间紧，第一版先不做复杂 Agent，只做确定性查询 + 混合检索 + 受控生成。

这样既能避免重复造基础轮子，又不会被通用 RAG 项目的局限拖住。对于这个赛题，真正拉开差距的是 Excel 结构化解析和证据可追溯，不是聊天界面。
