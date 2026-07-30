# 生产级 RAG 后续完整路线图

## 1. 目标

后续建设以生产级 RAG 系统完整能力为主，同时标注赛题必需能力。系统目标不是只完成一次演示，而是形成可持续增量更新、可审计、可评测、可追溯的银行业监管知识服务。

## 2. 能力分层

| 层级 | 生产能力 | 赛题必需 |
| --- | --- | --- |
| 数据来源 | source catalog、来源页、附件 URL、栏目、站点 | 是 |
| 版本管理 | version_status、版本链、现行优先 | 是 |
| 文档解析 | Word/PDF/Excel 结构化、复杂表格、条款位置 | 是 |
| 数据底座 | SQLite 第一版，后续 PostgreSQL | 否 |
| 检索 | 元数据过滤、版本过滤、BM25、embedding、reranker | 是 |
| 生成 | LLM 受控生成、schema、引用校验、数字校验 | 是 |
| 推理 | 表格取数、多跳、合规判断、新旧规提示 | 是 |
| 评测 | 模块级评测、可信问答、回归 smoke | 是 |
| 生产运维 | 任务记录、日志、反馈、权限、异步队列 | 否 |
| 前端 | P0 最小展示，P1 生产管理台 | 部分 |

## 3. P0 主线

### P0-1 来源与版本追溯

目标：让每个文档具备来源和版本字段，并支持后续检索过滤。

字段：

```text
source_url
attachment_url
source_site
column
publish_date
doc_no
version_status: current | superseded | unknown
effective_date
expiry_date
supersedes_doc_id
superseded_by_doc_id
version_group
```

交付：

- source catalog schema 扩展。
- catalog 校验报告。
- manifest_enriched 合并。
- document_metadata 继承版本字段。
- SQLite documents/source_catalog_entries 承载版本字段。
- 后续增加 document_versions 表和版本过滤。

赛题必需：是。

### P0-2 版本/元数据过滤闭环

目标：检索默认可优先现行版本，并支持发文机关、发布日期、文号、栏目、版本状态过滤。

赛题必需：是。

### P0-3 表格语义与指标过滤

当前已完成第一版 `indicator / periods / headers / cells`。下一步接入检索参数：

```text
indicator
period
unit
cell_ref
```

赛题必需：是。

### P0-4 LLM 受控生成

目标：只基于 evidence 生成 JSON schema 答案。

要求：

- 证据不足拒答。
- 每个结论绑定证据。
- 数字、日期、金额必须来自证据。
- 写入 qa_logs。

赛题必需：是。

## 4. P1 主线

- 接入模型级 embedding 后端。
- 接入模型级 reranker 后端。
- 前端生产管理台。
- document_versions 版本链展示。
- 评测失败样例分析。
- 人工反馈闭环。
- 异步任务队列。

## 5. P2 主线

- PostgreSQL 迁移。
- 权限与用户体系。
- 自动爬虫补采。
- 复杂 PDF/MinerU/OCR 解析。
- 新旧规条款 diff。
- 监控、告警和部署脚本。

## 6. 当前执行状态

已完成：

- 500 份文档 JSONL 知识库。
- SQLite 数据底座。
- source catalog 校验与入库留痕。
- 元数据质量审计。
- 元数据增强：publisher 466/500，column 383/500。
- 表格语义增强：15775 行全部具备 indicator/periods/headers/cells。
- 可信评测汇总 50/50。

当前 P0-1 已完成第一版字段贯通：

```text
source_catalog_template_v2.csv fields: 19
catalog_rows: 500
matched_documents: 500
match_rate: 1.0
documents: 500
document_versions: 500
version_status: unknown 500
trusted_eval_summary: 50/50
```

说明：版本字段、来源字段和版本关系字段已经进入 catalog、metadata、SQLite `documents` 和 `document_versions`。由于尚未补真实来源 catalog，当前 `version_status` 全部为 `unknown`，`source_url/attachment_url/effective_date/version_group` 仍为空。

### P0-2 执行结果

已完成版本/元数据过滤闭环第一版。

新增文档级过滤：

```text
source_site
version_status
effective_date_from
effective_date_to
version_group
has_version_relation
```

新增表格级过滤：

```text
indicator
period
```

已接入：

```text
CLI search/documents
FastAPI POST /search
FastAPI GET /documents
fallback HTTP server
evidence metadata return
```

验证结果：

```text
documents --version-status unknown -> 500
documents --version-status current -> 0
documents --has-version-relation -> 0
search --indicator 原保险保费收入 --period 2026年2月 -> 返回结构化表格证据
FastAPI TestClient /search -> indicator/periods 正常返回
trusted_eval_summary: 50/50
```

说明：当前 `current` 和版本关系过滤返回 0 是符合事实的，因为真实 catalog 仍未标注现行/替代关系。下一步应进入 P0-3：真实来源 catalog 补齐与版本状态标注，或进入 P0-4：LLM 受控生成。

### P0-3 执行结果：版本与溯源审计闭环

已新增 `version-audit` 命令，用于检查来源 URL、附件 URL、版本状态、版本组、生效/失效日期、替代关系是否足够支撑“现行优先、旧规抑制、证据可追溯”。

输出报告：

```text
reports/version_audit_report.json
```

当前审计结果：

```text
documents: 500
version_status:
  unknown: 500
current_count: 0
superseded_count: 0
source_url: 0/500
attachment_url: 0/500
effective_date: 0/500
version_group: 0/500
dangling_relation_count: 0
group_issue_count: 0
```

结论：系统已经具备版本字段、版本表、版本/元数据过滤接口和版本审计能力；但真实来源 URL 与现行/废止/替代关系尚未人工或半自动补齐。因此比赛交付时必须明确标注：版本治理能力已实现第一版，真实版本标注覆盖率当前为 0，需要进入来源 catalog 补采阶段。

### P0-3 补充：来源补采优先级清单

已新增 `source-gap-worklist` 命令，自动结合元数据缺口、可信 QA 评测集、检索评测集生成补采排序表。

输出文件：

```text
data/intermediate/source_gap_worklist.csv
reports/source_gap_worklist_report.json
```

当前结果：

```text
documents: 500
worklist_rows: 500
trusted_eval_referenced_docs: 13
retrieval_eval_referenced_docs: 30
source_url missing: 500
attachment_url missing: 500
version_status unknown: 500
```

优先补采样例：

```text
nfra_002 2026年2月全国各地区原保险保费收入情况表
nfra_398 银行函证工作操作指引
nfra_397 银行函证工作操作指引
nfra_390 附件：数据安全事件分级
nfra_361 绿色信贷统计信息披露说明-中文
```

生产用法：先补 `source_gap_worklist.csv` 的前 30-50 个高优先级文档，再执行 `validate-source-catalog`、`import-source-catalog`、`build-metadata`、`import-db --reset`、`version-audit` 完成闭环验收。

### P0-4 执行结果：现行版本优先与旧版抑制

已在检索结果排序层新增版本策略：

```text
prefer_current: true
include_superseded: true
method: current_boost_superseded_penalty_v1
```

接入范围：

```text
CLI search
FastAPI POST /search
fallback HTTP POST /search
BM25 / hybrid / reranker / fallback search final ranking
```

行为：

- `version_status=current`：加分，优先返回。
- `version_status=superseded`：降权，避免默认优先引用旧规。
- `include_superseded=false`：直接过滤已废止/被替代文档。
- `version_status=unknown`：不加分也不降权，避免在未补真实 catalog 前误伤召回。

验证：

```text
current 0.8 -> 1.1
unknown 0.9 -> 0.9
superseded 1.0 -> 0.4
include_superseded=false -> superseded 被过滤
trusted_eval_summary: 50/50
```

说明：当前 500 份文档仍全部为 `unknown`，所以真实检索结果排序暂不变化；一旦补齐 `source_catalog` 中的现行/替代关系，该策略会立即生效。
