# 更适合作为本赛题基础的 GitHub 项目调研

调研日期：2026-08-07。范围是官方 GitHub 仓库的 README、源码、许可证和仓库测试目录；没有把博客、二手测评或项目自称的“准确率”当作工程能力证据。

## 结论先行

没有一个仓库可以直接满足“中文银行监管制度 + Word/PDF/Excel + 统计计算 + 条款/单元格证据 + 生效/废止治理 + 拒答 + 可复现评测”。但比 `aiarghya1/financial-rag-system` 更合适的选择有明确优先级：

1. **首选主工程候选：腾讯 [WeKnora](https://github.com/Tencent/WeKnora)**。它是当前发现的最接近比赛要求的中文、可本地部署、可扩展平台：支持 Excel、混合检索、引用、RBAC、审计和 DuckDB 数据分析。仍需补监管版本模型、工作表/行列/单元格证据映射和金标评测。
2. **成熟通用底座：[RAGFlow](https://github.com/infiniflow/ragflow)**。文档解析、Excel/复杂 PDF、混合检索、重排、引用和测试最完整，适合替换现有通用 RAG 层；统计题和监管治理仍需在外部实现。
3. **不建议整库替换，但适合吸收组件**：`KAG`（逻辑/知识图谱/数值算子）、`DB-GPT`（数据源和 Agent）、`ST-Raptor`（复杂 Excel 表格问答）、`TableRAG`（SQL+文本表格算法）、`QAnything`（中文本地解析与 BCE 检索）、`FinRAG`（金融检索基准）。

## 赛题要求与候选能力

| 项目 | 本地部署/许可证 | Word/PDF/Excel | 混合检索/重排 | 表格计算 | 证据/拒答/治理 | 分档 |
|---|---|---|---|---|---|---|
| **WeKnora** | 本地/Docker/K8s、MIT（第三方依赖另行遵守） | README 明确列出 PDF、Word、Excel、CSV、PPT 等 | BM25 + Dense、GraphRAG、rerank | DuckDB 只读 SQL；多 sheet 合并并增加 `__sheet_name` | 引用抽屉、来源引用、RBAC/审计；有 fallback，但没有银行法规有效期模型 | **可替换主工程（优先）** |
| **RAGFlow** | Docker、自托管，Apache-2.0 | README 明确支持 Word、Slides、Excel、扫描件、结构化数据；源码有 Excel/合并单元格/表格解析 | 源码实现 BM25+向量融合、rerank、引用插入 | 有结构化 Excel 解析，但问答计算需另接确定性引擎 | grounded citations；测试目录大且持续维护；未见生效/废止/可信拒答闭环 | **可替换主工程（成熟度优先）** |
| **QAnything** | 本地/离线，AGPL-3.0；v2 通过 OpenAI 兼容接口调用模型 | README 支持 PDF、DOCX、PPTX、XLSX、CSV；v2 优化多 sheet、合并单元格和复杂格式 | README/API 明确 BM25+embedding hybrid、两阶段 rerank、BCE | 解析为 chunk；没有确定性 SQL/公式计算和单元格坐标合同 | 有 `source_info`（doc/page/chunk）和引用提示；仅少量测试，许可证有传染性风险 | **仅适合作为组件** |
| **KAG** | Apache-2.0；本地知识库/图谱 | README 宣称 Word 上传；源码注册 PDF/Docx reader，未见 XLSX reader | 逻辑形式引导的 hybrid retrieval/reasoning，支持 rerank | `kg-solver` 含数值计算算子；表格是索引类型 | 可链接原始 reference；不提供银行版本治理/拒答评测 | **仅适合作为组件** |
| **DB-GPT** | MIT；本地模型和多数据源平台 | README/文档强调 Excel、数据库、数据仓库；文档 RAG 格式和证据能力需按模块配置 | 向量、全文 BM25、图索引和 hybrid retrieval | NL2SQL/数据分析强，适合把 Excel 入库后计算 | Agent citation pipeline、RBAC/版本迁移和大量测试；不是法规条款问答专用 | **仅适合作为组件** |
| **ST-Raptor** | MIT；支持本地/API 模型 | 只针对 Excel/HTML/Markdown/CSV 等半结构化表格 | 不是通用文档 hybrid RAG | VLM + HO-Tree，两阶段验证，擅长多行表头/合并单元格 | 输出答案但没有制度来源、版本治理或完整拒答；论文配置显著吃 GPU | **仅适合作为组件** |
| **TableRAG** | 仓库未发现 LICENSE；MySQL/外部数据集依赖 | 主要是 Excel 异构表格；不是 Word/PDF 知识库 | SQL execution + textual retrieval | 目标就是复杂表格操作和多跳异构推理 | 研究代码 24 个文件、测试极少；无法规来源和治理 | **仅适合作为组件（先解决授权）** |
| **FinRAG** | Apache-2.0；小型研究仓库 | 面向英文财报数据集，不是通用本地文件导入 | embedding + CrossEncoder rerank、查询扩展 | 依赖 FinQA/TAT-QA 等基准，不含银行报表处理 | 无条款引用、版本治理或拒答系统；仓库规模和测试较小 | **仅适合作为组件/基准** |
| **CSRC-RAG** | 未发现 LICENSE；课程/实验项目 | 中文证监会案例和法规，Excel 仍在建设中 | BM25/Dense/Hybrid 路由；默认 dense 是 `svd_tfidf` | 没有可交付的表格计算引擎 | 有 Query Plan、证据折叠和模板回退；授权和工程成熟度不足 | **不推荐作为主工程** |

## 重点项目的源码证据

### WeKnora：最值得做一次 PoC

- README 的功能表列出多格式解析（含 Excel）、BM25 sparse/Dense/GraphRAG、引用弹窗、离线/私有部署和 workspace RBAC：[README.md](https://github.com/Tencent/WeKnora/blob/main/README.md)。
- Excel 数据分析不是宣传语：`internal/agent/tools/data_analysis.go` 使用 DuckDB `read_xlsx`，枚举所有 sheet，将多 sheet `UNION ALL BY NAME`，并加 `__sheet_name`；SQL 仅允许 `SELECT/SHOW/DESCRIBE/EXPLAIN/PRAGMA`：[源码](https://github.com/Tencent/WeKnora/blob/main/internal/agent/tools/data_analysis.go)。这比 `financial-rag-system` 的文档向量检索更适合统计报表题。
- 代码有 `citation_enabled`、引用事件和评测 API，且仓库有 Go 单元/集成测试；但 SQL 结果当前主要是列值和 sheet 来源，没有内建 Excel 行号/列号/单元格地址映射，需自行加 `source_row/source_col/cell_ref`。
- `wiki_page`/`chunk` 有 superseded revision 快照，但这不等于监管文件的 `effective_from/effective_to/status`；必须在领域层实现版本过滤。
- 许可证为 MIT，同时明确第三方组件按各自许可证执行：[LICENSE](https://github.com/Tencent/WeKnora/blob/main/LICENSE)。

### RAGFlow：最成熟的通用解析与引用层

- README 明确支持 Word、Slides、Excel、扫描件、结构化数据和 grounded citations：[README](https://github.com/infiniflow/ragflow/blob/main/README.md)。
- Excel 源码使用 `openpyxl`，处理多 sheet、merged cells、继承值和表格结构：[table.py](https://github.com/infiniflow/ragflow/blob/main/rag/app/table.py)。检索源码包含 BM25/向量融合和引用插入：[search.py](https://github.com/infiniflow/ragflow/blob/main/rag/nlp/search.py)。
- 仓库有 `test/unit_test`、`test/integration`、Playwright 等大规模测试和持续工作流，Apache-2.0：[LICENSE](https://github.com/infiniflow/ragflow/blob/main/LICENSE)。
- 其引用锚点仍以 chunk/page/preview 为主；比赛要求的“关键数字与单元格”应由外部表格索引和确定性计算层补齐。部署依赖 Docker、数据库、对象存储和模型服务，开发成本高于 WeKnora。

### QAnything：能力接近但许可证和计算能力不适合做比赛主线

- 这是中文本地 RAG，README/API 支持 `xlsx/docx/pdf`、BM25+embedding hybrid、两阶段 rerank，且 v2 说明多 sheet、合并单元格和复杂 Excel 解析改进：[README](https://github.com/netease-youdao/QAnything/blob/qanything-v2/README.md)、[API](https://github.com/netease-youdao/QAnything/blob/qanything-v2/docs/API.md)。
- Milvus `source_info` 记录 doc/page/chunk；源码注释明确 pdf/csv/xlsx 不做普通候选扩展，未形成单元格级引用：[milvus_client.py](https://github.com/netease-youdao/QAnything/blob/qanything-v2/qanything_kernel/connector/database/milvus/milvus_client.py)。
- 仓库许可证是 AGPL-3.0，且当前默认模型调用路径为 OpenAI 兼容接口；应先做法律审查，不宜把它的服务代码直接并入比赛交付：[LICENSE](https://github.com/netease-youdao/QAnything/blob/qanything-v2/LICENSE)。

## 推荐落地方式

建议先用同一批本地文件做两天 PoC：WeKnora 和 RAGFlow 各导入 10 份制度文件 + 20 份 Excel，固定同一 embedding/reranker，跑 42 条种子问答及新增的拒答集。比较四项硬指标：

1. Excel 数字、单位、期间和多 sheet 取数是否可复算；
2. 每个结论能否回链到条款或 `sheet!cell`；
3. 过期/被替代制度是否被过滤；
4. 无依据问题是否稳定返回拒答而不是编造。

若 PoC 以少量改动达标，优先 **WeKnora 作为应用/Agent 外壳 + 当前项目的监管数据合同和版本策略**；若解析质量或中文表格效果不稳定，采用 **RAGFlow 解析/检索 + 当前项目的表格计算、证据校验和评测**。不要直接 fork `financial-rag-system`：它的官方仓库能力集中在 PDF/TXT/HTML 文档 RAG，不能覆盖本地 Excel 统计计算和监管数据治理。

## 其他项目的官方入口

- [KAG](https://github.com/OpenSPG/KAG) · [DB-GPT](https://github.com/eosphoros-ai/DB-GPT) · [ST-Raptor](https://github.com/OpenDataBox/ST-Raptor) · [TableRAG](https://github.com/yxh-y/TableRAG) · [FinRAG](https://github.com/AI4Finance-Foundation/FinRAG) · [CSRC-RAG](https://github.com/Mindse-Tt/CSRC-RAG)
- 表格推理/评测组件：[FinQA](https://github.com/czyssrs/FinQA) · [TAT-QA](https://github.com/NExTplusplus/TAT-QA) · [OmniEval](https://github.com/RUC-NLPIR/OmniEval) · [RAGChecker](https://github.com/amazon-science/RAGChecker)
