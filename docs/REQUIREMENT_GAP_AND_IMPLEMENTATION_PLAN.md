# 赛题要求对标、系统差距与后续实现方案

本文档基于赛题描述，对当前系统进行逐项检查，说明已经做到的能力、尚未完成的缺口，以及这些缺口后续如何生成和实现。

> 2026-07-28 更新：阶段 A 的第一版已经完成。系统已生成 `document_metadata.jsonl` 和 `text_units.jsonl`，并已将 `/documents` 与 `/search` 接入增强元数据和文本结构单元。本文档保留完整设计方案，同时用“当前状态”说明哪些缺口已经从“未完成”变为“初版完成”。

## 1. 当前总体判断

当前系统已经完成一个可运行的可信 RAG MVP：

- 已清洗入库 500 份本地监管资料。
- 已形成文本 chunk、Excel 单元格事实和 Excel 行级证据。
- 已实现 BM25 证据检索。
- 已实现 Excel 选择题、Word/PDF 选择题和开放式 RAG 问答。
- 已实现无证据拒答、证据充分性判断、答案数字一致性检查。
- 已提供 FastAPI 后端和 Vite + React 前端。
- 300 条 QA 验证题当前为 `300/300`。

但与赛题完整要求相比，当前仍属于“可演示 MVP + 初版可信问答”，还不是完整竞赛级系统。主要缺口集中在：

- 来源 URL、附件 URL、栏目仍未补齐；发文机关、发布日期、文号已有规则抽取第一版，但覆盖率仍有限。
- 文本 chunk 已生成章节/条款级 `text_units` 第一版，但复杂版式、条款边界和页码定位仍需继续校准。
- 检索已支持 BM25、`local_hashing_v1` hybrid 检索和 `rule_reranker_v1`，但还没有模型级 embedding/reranker。
- 元数据过滤能力仍较弱，业务领域和监管主题已有规则标签第一版，但尚未建立版本关系。
- 跨文件、多跳、跨模态推理还没有形成独立流程。
- 场景合规判断还没有专门的规则化回答模板和评测集。
- LLM 受控生成已接入接口，但本地尚未配置真实模型 Key，因此未做真实生成质量评测。

## 2. 赛题要求逐项对标

| 赛题要求 | 当前状态 | 说明 |
| --- | --- | --- |
| 多源异构资料处理 | 部分完成 | 已处理 `.xls/.xlsx/.pdf/.doc/.docx`，但网页正文、来源页面 URL 尚未补齐。 |
| Word/PDF 制度原文解析 | MVP 完成 | 已抽取文本并切分 chunk，但章节、条款、页码结构还不够精细。 |
| Excel 统计附件解析 | 已完成较好 | 已生成 83555 条单元格事实和 15775 条行级证据，保留 sheet/cell/row/col/unit/value。 |
| doc_id、标题、文件类型 | 已完成 | `manifest.jsonl` 已覆盖 500 个文件。 |
| 发文机关、发布日期 | 初版完成 | 已生成 `document_metadata.jsonl`，当前发文机关 117/500、发布日期 5/500、文号 11/500，仍需补采和规则增强。 |
| 来源 URL、附件 URL | 未完成 | 本地数据没有提供原始下载 manifest，因此当前字段为 null。 |
| 章节/条款/表格位置 | 初版完成 | 表格位置已较完整；文本已生成 7132 条 `text_units`，其中 3409 条带页码、1828 条带条款编号。 |
| 关键词检索 | 已完成 | 当前 `/search` 使用本地 BM25。 |
| 语义检索 | 初版完成 | 已实现 `local_hashing_v1` 本地 embedding 索引、`retrieval=hybrid` 和 `rule_reranker_v1`；后续仍需接入 bge/OpenAI embedding 与模型级 reranker。 |
| 元数据过滤 | 初版完成 | 支持 `source_type/doc_id/file_ext/query/publisher/publish_date/business_domain/regulatory_topic/doc_no/column/has_source_url/article_no`。 |
| 表格结构检索 | 部分完成 | 有 cell facts 和 row text，但还未做专门 SQL/DSL 查询层。 |
| 制度定义、适用范围、流程要求 | 部分完成 | 可通过 RAG 检索回答，但尚未针对条款类问题做结构化 route。 |
| 金额阈值、保存期限、禁止性规定 | 部分完成 | 能检索和受控生成，但还未做专门数字/期限/规范强度抽取。 |
| 统计取数 | 已完成较好 | Excel QA 已稳定支持。 |
| 场景合规判断 | 未完成 | 尚未形成“事实抽取 -> 规则匹配 -> 合规/不合规/无法判断”的链路。 |
| 可追溯证据 | 部分完成 | 已返回文件、表格位置、文本片段；URL、条款编号、页码字段仍需增强。 |
| 幻觉抑制 | 部分完成 | 已有拒答、证据充分性、数字一致性检查；还需 LLM 输出引用校验和人工评测集。 |
| 评测报告 | 部分完成 | 有 300 条 QA 自动评测；缺开放式问答、拒答、多跳、场景判断评测。 |

## 3. 当前已经生成的数据

当前原始数据目录：

```text
wendang/data
```

当前清洗产物：

| 文件 | 数量 | 作用 |
| --- | ---: | --- |
| `data/processed/manifest.jsonl` | 500 | 文档清单与基础元数据。 |
| `data/processed/document_metadata.jsonl` | 500 | 文档增强元数据，包含发文机关、发布日期、文号、业务领域和监管主题第一版。 |
| `data/processed/text_chunks.jsonl` | 1094 | Word/PDF 文本片段。 |
| `data/processed/text_units.jsonl` | 7132 | Word/PDF 页码、章节、条款级文本结构单元。 |
| `data/processed/table_cells.jsonl` | 83555 | Excel 单元格级结构化事实。 |
| `data/processed/table_rows.jsonl` | 15775 | Excel 行级 RAG 证据。 |
| `data/index/text_vectors.jsonl` | 7132 | Word/PDF 本地哈希 embedding 索引。 |
| `data/index/table_row_vectors.jsonl` | 15775 | Excel 表格行本地哈希 embedding 索引。 |
| `data/processed/kb_build_state.jsonl` | 500 | 每个文件的构建状态。 |
| `reports/kb_build_errors.json` | 0 个错误 | 清洗错误报告。 |
| `reports/excel_eval.json` | 100 条 | Excel QA 评测报告。 |
| `reports/text_eval.json` | 200 条 | Word/PDF QA 评测报告。 |
| `data/eval/retrieval_eval.jsonl` | 60 | 检索评测集第一版，文本证据 30 条、表格行证据 30 条。 |
| `reports/retrieval_eval.json` | 1 | 检索评测报告。 |

当前文件类型：

| 类型 | 数量 |
| --- | ---: |
| `.xls` | 232 |
| `.xlsx` | 157 |
| `.pdf` | 45 |
| `.doc` | 32 |
| `.docx` | 34 |

## 4. 关键缺口与生成方案

### 4.1 缺口一：来源 URL、附件 URL、栏目不完整

当前状态：补采入口已完成，真实 URL 数据仍待提供。

已实现：

```text
src/jinrong/source_catalog.py
data/intermediate/source_catalog_template.csv
```

新增命令：

```powershell
python -m jinrong.cli export-source-template
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
```

合并后的正式产物：

```text
data/processed/manifest_enriched.jsonl
reports/source_enrichment_report.json
```

服务层已支持：如果 `manifest_enriched.jsonl` 存在，则 `/documents` 和 `/search` 优先读取增强 manifest；否则继续使用 `manifest.jsonl`。

当前问题：

- `manifest.jsonl` 中已有 `source_url`、`attachment_url`、`column` 字段，但当前均为 `null`。
- 原因是本地 `wendang/data` 只有下载后的附件文件，没有原始页面抓取 manifest。

如何生成：

1. 如果有下载脚本或历史下载日志：
   - 从日志中恢复来源页面 URL 和附件 URL。
   - 按文件名或 SHA-256 与当前 manifest 对齐。

2. 如果没有下载日志：
   - 建立 `source_catalog.csv/jsonl`。
   - 字段包括：

```json
{
  "file_name": "001_...",
  "title": "...",
  "source_url": "...",
  "attachment_url": "...",
  "column": "监管统计/政策法规/通知公告",
  "publisher": "国家金融监督管理总局",
  "publish_date": "2026-02-xx"
}
```

3. 半自动补采：
   - 用文件标题在官网或原下载站点搜索。
   - 抓取搜索结果 URL。
   - 下载附件或比对附件名、文件大小、SHA-256。
   - 匹配成功后写回 `source_catalog.jsonl`。

4. 入库合并：
   - 已新增命令：

```powershell
python -m jinrong.cli enrich-manifest --source-catalog data/source_catalog.jsonl
```

   - 将 `source_url/attachment_url/column/publisher/publish_date` 合并进 `manifest_enriched.jsonl`。

建议生成产物：

```text
data/processed/manifest_enriched.jsonl
reports/source_enrichment_report.json
```

优先级：高。因为来源 URL 是可溯源能力的重要组成。

### 4.2 缺口二：发文机关、发布日期、文号未结构化

当前状态：初版已完成。

已生成：

```text
data/processed/document_metadata.jsonl
reports/metadata_extraction_report.json
```

当前覆盖情况：

| 字段 | 已填充数量 |
| --- | ---: |
| `publisher` | 117 |
| `publish_date` | 5 |
| `doc_no` | 11 |
| `source_url` | 0 |
| `attachment_url` | 0 |

后续仍需要来源补采、更多机关别名、日期位置规则和人工抽样校验来提升质量。

当前问题：

- 文件标题中隐含了一些发文机关和文号，但系统没有专门抽取。
- 文本 chunk 里能看到文号，如 `财会〔2022〕39号`，但没有进入元数据字段。

如何生成：

1. 文件名规则抽取：
   - 形如 `财政部办公厅_金融监管总局办公厅关于印发...` 可抽出候选发文机关。
   - 形如 `中国银保监会关于印发...` 可抽出机关。

2. 正文首页抽取：
   - 对 Word/PDF 前 1-2 个 chunk 使用正则抽取：
     - 发文机关：`中国人民银行`、`国家金融监督管理总局`、`中国银保监会`、`国务院` 等。
     - 文号：`〔2022〕39号`、`银保监发〔2021〕xx号`。
     - 发布日期：`YYYY年M月D日`。

3. LLM 辅助抽取：
   - 对规则无法抽出的文件，使用 LLM 做结构化抽取。
   - 必须保存原文证据片段，不直接相信模型。

建议新增字段：

```json
{
  "publisher": "财政部办公厅、金融监管总局办公厅",
  "publish_date": "2024-xx-xx",
  "doc_no": "财会〔2022〕39号",
  "metadata_evidence": "原文片段"
}
```

建议新增模块：

```text
src/jinrong/metadata_extractor.py
```

建议新增命令：

```powershell
python -m jinrong.cli build-metadata
```

建议生成产物：

```text
data/processed/document_metadata.jsonl
reports/metadata_extraction_report.json
```

优先级：高。

### 4.3 缺口三：文本没有章节/条款级结构

当前状态：初版已完成。

已生成：

```text
data/processed/text_units.jsonl
reports/text_units_report.json
```

当前覆盖情况：

| 指标 | 数量 |
| --- | ---: |
| `text_units` | 7132 |
| 带 `page_no` | 3409 |
| 带 `section_path` | 7005 |
| 带 `article_no` | 1828 |

`/search` 当前对 Word/PDF 优先检索 `text_units.jsonl`，证据位置会返回 `unit_id/unit_index/chunk_id/chunk_index/page_no/section_path/article_no`。

当前问题：

- 当前 `text_chunks.jsonl` 只有 `chunk_index`，PDF 文本中保留了 `[page N]` 文本标记。
- 没有结构化字段：`page_no`、`section_path`、`article_no`、`clause_no`。
- 对“第几条规定了什么”“适用范围是什么”这类问题，证据定位还不够精确。

如何生成：

1. 正则识别章节：
   - `第一章`
   - `第一节`
   - `第十二条`
   - `一、`
   - `（一）`
   - `1.`

2. 构建层级状态机：
   - 遍历文本行。
   - 遇到章/节/条更新当前 `section_path`。
   - 每个条款生成一个 article chunk。

3. PDF 页码抽取：
   - 当前文本已有 `[page N]`，可以解析为 `page_no` 字段。

建议新增字段：

```json
{
  "page_no": 3,
  "section_path": "第一章 总则 / 第三条",
  "article_no": "第三条",
  "clause_no": null,
  "char_start": 1234,
  "char_end": 1560
}
```

建议新增模块：

```text
src/jinrong/structure_parser.py
```

建议生成产物：

```text
data/processed/text_units.jsonl
```

后续 `text_chunks.jsonl` 可以由 `text_units.jsonl` 进一步切分或直接替代。

优先级：高。

### 4.4 缺口四：语义检索和 reranker 未完成

当前状态：混合检索第一版和规则 reranker 第一版已完成，模型级 reranker 尚未完成。

已生成：

```text
data/index/text_vectors.jsonl
data/index/table_row_vectors.jsonl
data/index/vector_index_manifest.json
```

新增命令：

```powershell
python -m jinrong.cli build-vector-index
python -m jinrong.cli search "..." --retrieval hybrid
python -m jinrong.cli search "..." --retrieval hybrid --rerank
python -m jinrong.cli build-retrieval-eval --target-size 60 --retrieval hybrid --rerank
python -m jinrong.cli eval-retrieval --retrieval hybrid --rerank
```

当前实现：

- 使用 `local_hashing_v1`，不依赖外部模型和网络。
- 对 `text_units` 和 `table_rows` 构建 4096 维稀疏哈希 embedding。
- `retrieval=hybrid` 同时执行 BM25 和向量召回，再用 RRF 融合排序。
- `rerank=true` 使用 `rule_reranker_v1` 对候选证据二次重排。
- `/search` 返回 `index=hybrid_bm25_hash_embedding`，单条证据返回 `index=hybrid`。
- 检索评测集第一版包含 60 条 evidence-level 查询，报告输出 `top1/top3/topk`。

后续仍需增强：

- 替换或并行接入 `bge-m3`、`bge-large-zh-v1.5` 或 OpenAI-compatible embeddings。
- 接入模型级 reranker，进一步压制相近但不够精确的表格行或条款。
- 建立检索评测集，比较 BM25 与 hybrid 的召回率和证据命中率。

当前问题：

- 当前检索是本地 BM25。
- 对关键词明确的问题效果不错。
- 对同义改写、复杂语义、多跳问题，BM25 召回可能不足。

如何实现：

1. Embedding 模型：
   - 本地优先：`BAAI/bge-m3`、`bge-large-zh-v1.5`。
   - API 优先：OpenAI-compatible embeddings。

2. 向量索引：
   - 原型：FAISS。
   - 服务化：Qdrant 或 Milvus。

3. 混合检索：

```text
query
  -> BM25 top 50
  -> dense top 50
  -> 合并去重
  -> reranker top 8
```

4. Reranker：
   - 本地：`bge-reranker-v2-m3`。
   - API：可配置 rerank endpoint。

建议新增模块：

```text
src/jinrong/vector_index.py
src/jinrong/hybrid_retrieval.py
src/jinrong/reranker.py
```

建议新增产物：

```text
data/index/faiss_text.index
data/index/faiss_table_rows.index
data/index/embedding_manifest.json
```

建议新增命令：

```powershell
python -m jinrong.cli build-vector-index
python -m jinrong.cli search "..." --retrieval hybrid
```

优先级：中高。先有 BM25 可用，但要冲赛题完整能力，语义检索必须补。

### 4.5 缺口五：业务领域、监管主题、版本关系缺失

当前问题：

- 当前只支持 `source_type`、`file_ext`、`doc_id`、标题关键词过滤。
- 缺少业务领域，如信贷、资本、消保、反洗钱、支付结算、普惠金融、监管统计。
- 缺少新旧版本关系。

如何生成：

1. 规则分类：
   - 根据标题关键词打标签。
   - 示例：
     - `资本`、`偿付能力` -> 资本管理/偿付能力。
     - `绿色信贷` -> 绿色金融。
     - `函证` -> 审计函证。
     - `投诉`、`消费者权益` -> 消保。
     - `支付`、`结算` -> 支付结算。

2. LLM 辅助分类：
   - 输入标题、前两个 chunk。
   - 输出 `business_domain`、`regulatory_topic`、`applicable_subjects`。
   - 必须保存分类证据。

3. 版本关系：
   - 根据标题、文号、发布日期、关键词“废止、修订、印发、施行”识别。
   - 建立 `supersedes/superseded_by/effective_status` 字段。

建议生成产物：

```text
data/processed/document_tags.jsonl
data/processed/version_relations.jsonl
```

建议新增字段：

```json
{
  "business_domain": "监管统计",
  "regulatory_topic": "绿色信贷统计",
  "applicable_subjects": ["银行业金融机构"],
  "effective_status": "active|expired|unknown",
  "supersedes": [],
  "superseded_by": []
}
```

优先级：中高。它会明显提升检索过滤和答辩说服力。

### 4.6 缺口六：跨文件、多跳、跨模态推理不足

当前问题：

- 当前 `/ask` 对开放式问题主要是检索 top evidence 后生成答案。
- 还没有专门的多跳 planner。
- 对“先从制度定位指标口径，再去 Excel 取数，再解释变化”这类题，尚未形成稳定流程。

如何实现：

建议增加查询规划器：

```text
question
  -> classify intent
  -> extract entities
  -> decide route
     - text_fact
     - table_lookup
     - table_compare
     - table_calc
     - text_then_table
     - compliance_judgement
  -> retrieve evidence
  -> execute structured step
  -> compose answer
```

新增模块：

```text
src/jinrong/query_planner.py
src/jinrong/multihop_qa.py
```

`text_then_table` 示例：

1. 从制度文本检索指标定义。
2. 从定义中抽取指标名、口径、期间。
3. 到 Excel 表格事实中查询数值。
4. 返回制度证据 + 表格证据 + 计算过程。

建议新增评测集：

```text
data/eval/multihop_qa.jsonl
```

优先级：中。它是赛题亮点，但需要前面的元数据和结构化条款先稳定。

### 4.7 缺口七：场景合规判断未完成

当前问题：

- 当前系统能检索条款，但还没有专门回答“某业务场景是否合规”的流程。
- 金融合规判断不能只回答“是/否”，必须说明依据、适用条件、例外情形和不确定点。

如何实现：

1. 场景要素抽取：
   - 主体：银行、分支机构、客户、借款人。
   - 行为：发放贷款、办理函证、报送统计、信息披露。
   - 时间：发生日期、生效日期。
   - 金额/比例/期限。
   - 条件：是否首次、是否逾期、是否豁免。

2. 条款检索：
   - 检索定义条款。
   - 检索义务条款。
   - 检索禁止性条款。
   - 检索例外条款。

3. 判断模板：

```json
{
  "judgement": "合规|不合规|无法判断",
  "reason": "...",
  "applicable_rules": [...],
  "missing_facts": [...],
  "evidence": [...]
}
```

4. 拒答规则：
   - 如果缺少关键事实，必须返回“无法判断”，并列出缺少的信息。
   - 如果只有定义条款，没有义务/禁止条款，不能直接判断违规。

建议新增模块：

```text
src/jinrong/compliance_qa.py
```

建议新增 route：

```text
compliance_judgement
```

建议新增评测集：

```text
data/eval/compliance_cases.jsonl
```

优先级：中高。它直接对应赛题“真实监管与银行业务场景”。

### 4.8 缺口八：开放式评测与拒答评测不足

当前问题：

- 当前 300/300 是选择题评测。
- 还没有开放式问题、拒答问题、多跳问题、场景合规问题的自动评测。

如何生成：

1. 从现有证据自动生成候选问题：
   - 文本条款 -> 定义题、期限题、禁止性规定题。
   - Excel cell -> 取数题、比较题、变化计算题。

2. 人工审核一批高质量评测题。

3. 建立评测数据格式：

```json
{
  "id": "OPEN_001",
  "question": "...",
  "expected_answer": "...",
  "required_evidence": [
    {"doc_id": "nfra_398", "chunk_id": "nfra_398_chunk_0000"}
  ],
  "must_contain": ["银行函证", "质量和效率"],
  "must_not_contain": [],
  "answerable": true,
  "type": "text_fact"
}
```

拒答题：

```json
{
  "id": "REFUSE_001",
  "question": "宇宙飞船发动机保修期是多少？",
  "answerable": false,
  "expected_route": "rag_refusal"
}
```

建议新增模块：

```text
src/jinrong/eval_open.py
src/jinrong/eval_refusal.py
```

建议新增报告：

```text
reports/open_eval.json
reports/refusal_eval.json
reports/trusted_qa_eval.json
```

优先级：高。因为“可信”必须靠评测证明。

## 5. 后续实现路线

建议按下面顺序推进，而不是同时铺开所有功能。

### 阶段 A：补元数据与条款结构

目标：让知识库从“能检索”升级为“能定位条款和版本”。

当前状态：第一版已完成；来源补采入口和元数据过滤接口也已完成，真实来源 URL 数据仍待补齐。

任务：

1. 已新增 `metadata_extractor.py`。
2. 已生成 `document_metadata.jsonl`。
3. 已新增 `structure_parser.py`。
4. 已生成 `text_units.jsonl`。
5. 已将 `/documents` 合并增强元数据，`/search` 优先返回 `text_unit` 证据。
6. 已将 `/documents` 和 `/search` 扩展为显式支持 `publisher/publish_date/business_domain/article_no` 等过滤。
7. 已新增 `source_catalog` 补采模板导出和 manifest 合并流程。
8. 待做：填充真实 `source_url/attachment_url/column`，并建立版本关系。

验收：

- 第一版已验证 PDF/Word 证据能返回 `page_no/article_no/section_path`。
- 后续质量目标：至少 80% 文本类文件能抽到发文机关或文号。

### 阶段 B：补语义检索与重排序

目标：提升自然语言改写、多事实、多跳问题召回。

当前状态：混合检索第一版和规则 reranker 第一版已完成，模型级 embedding 和 reranker 待做。

任务：

1. 已新增本地 `local_hashing_v1` embedding。
2. 已构建文本和表格 row 向量索引。
3. 已实现 BM25 + vector hybrid search。
4. 待做：接入 bge/OpenAI-compatible embedding。
5. 已新增 `rule_reranker_v1`。
6. 已新增检索评测集第一版。
7. 待做：接入模型级 reranker。

验收：

- `/search` 已返回 `index=hybrid_bm25_hash_embedding`。
- 对同义改写问题，召回优于纯 BM25。
- 保存检索评测报告。

### 阶段 C：补多跳和场景合规判断

目标：覆盖赛题中的复杂推理和真实业务场景。

任务：

1. 新增 query planner。
2. 新增 text_then_table 流程。
3. 新增 compliance_judgement 流程。
4. 设计合规判断输出 schema。
5. 构造多跳和合规评测集。

验收：

- 能回答“制度口径 + 表格取数”组合题。
- 能对场景题输出“合规/不合规/无法判断 + 依据 + 缺失事实”。

### 阶段 D：补可信评测

目标：证明系统低幻觉、可核验。

任务：

1. 生成开放式 QA 评测集。
2. 生成拒答评测集。
3. 生成多跳评测集。
4. 输出综合评测报告。

验收：

- 选择题评测继续保持不回退。
- 开放式答案必须引用证据。
- 拒答题不能强答。
- 数字/日期/文号一致性错误可被检测。

## 6. 建议新增文件清单

建议后续逐步新增：

```text
src/jinrong/metadata_extractor.py
src/jinrong/structure_parser.py
src/jinrong/vector_index.py
src/jinrong/hybrid_retrieval.py
src/jinrong/reranker.py
src/jinrong/query_planner.py
src/jinrong/multihop_qa.py
src/jinrong/compliance_qa.py
src/jinrong/eval_open.py
src/jinrong/eval_refusal.py
```

建议新增数据产物：

```text
data/processed/manifest_enriched.jsonl
data/processed/document_metadata.jsonl
data/processed/text_units.jsonl
data/processed/document_tags.jsonl
data/processed/version_relations.jsonl
data/index/faiss_text.index
data/index/faiss_table_rows.index
data/eval/open_qa.jsonl
data/eval/refusal_qa.jsonl
data/eval/multihop_qa.jsonl
data/eval/compliance_cases.jsonl
reports/metadata_extraction_report.json
reports/open_eval.json
reports/refusal_eval.json
reports/trusted_qa_eval.json
```

## 7. 最小优先开发任务

阶段 A 的工程入口已经完成。如果下一步只做最关键的一步，建议改为：

```text
真实来源 catalog 补齐 + 模型级 reranker
```

原因：

- `source_url/attachment_url/column` 当前仍为 0，是可溯源链路最大的业务数据短板。
- 工程上已经有模板和合并命令，下一步需要真实数据或爬虫补齐 catalog。
- 元数据过滤、hybrid 检索和规则 reranker 第一版已经能用，检索质量的下一块短板是模型级 reranker 和更系统的检索评测集。

建议下一条开发命令目标：

```text
补齐 source_catalog.jsonl 的真实 URL 数据；同时接入模型级 reranker，并扩充检索评测集。
```

## 8. 总结

当前系统已经完成了可运行 RAG MVP，尤其在 Excel 表格结构化、全量入库、BM25 检索、API、前端和基础可信问答方面已经形成闭环。

但若要完整对齐赛题，还需要继续补齐：

1. 来源 URL、附件 URL、栏目和版本关系。
2. 发文机关、发布日期、文号抽取质量提升。
3. 文本章节/条款级结构质量校准。
4. 语义检索和 reranker。
5. 业务领域和监管主题标签。
6. 跨文件、多跳、跨模态推理。
7. 场景合规判断。
8. 开放式、拒答、多跳、合规评测集。

这些能力补齐后，系统才能从“能演示的 RAG 系统”进一步升级为“面向真实监管业务场景的可信 RAG 问答系统”。
