# GitHub 开源项目调研：银行监管制度与统计报表可信 RAG

调研时间：2026-08-07。以下结论只根据项目自己的 GitHub README、源码/许可证文件整理；项目链接同时是核验入口。没有发现一个开箱即用、覆盖“中国银行监管制度 + 监管统计报表 + 可信问答”全流程的项目，因此建议组合复用，而不是直接 fork 某一个仓库。

## 最值得借鉴的项目

| 项目 | 一手资料中明确的能力 | 对本赛题的匹配点 | 主要风险/边界 |
|---|---|---|---|
| [RAGFlow](https://github.com/infiniflow/ragflow)（Apache-2.0） | [README](https://github.com/infiniflow/ragflow#-key-features) 明确提供深度文档理解、模板化切分、可视化切分、可追溯引用；支持 Word、Slides、Excel、TXT、图片、扫描件、结构化数据和网页；支持多路召回与融合重排。 | 最接近可运行的工程底座：制度 PDF/DOCX 和统计 Excel 可统一入库，引用片段可作为答案证据展示，已有 API/Agent 工作流可接现有服务。 | 依赖 Docker、较高内存和较新 Python；通用引擎不会自动理解监管口径、版本生效日期或指标公式，仍需自定义解析、权限、时效和答案校验；升级版本需做兼容性回归。 |
| [FinRAG](https://github.com/AI4Finance-Foundation/FinRAG)（Apache-2.0） | [README](https://github.com/AI4Finance-Foundation/FinRAG/blob/master/README.md) 展示 Milvus 向量库、BCE embedding + reranker、本地配置和启动流程；路线图包含多级索引、多查询、query 与解析优化。 | 中文金融 RAG 的直接参考：向量检索 + cross-encoder 重排、Milvus 部署方式可映射到监管文档检索。 | README 的实现仍偏 demo/骨架，路线图中的关键优化未完成；没有看到监管版本治理、证据强制、报表计算校验，不能把默认检索结果当作可信答案。 |
| [FinanceRAG](https://github.com/linq-rag/FinanceRAG)（MIT） | [README](https://github.com/linq-rag/FinanceRAG#-3-example-code) 将 `retrieval`（dense embedding）、`rerank`（cross-encoder）、`tasks`（FinDER/FinQA/TATQA）和 `generate` 分层，并提供 retrieve/rerank/save 代码。 | 适合借鉴清晰的评测和检索接口：可把赛题制度问答、指标问答分别做成 task，固定检索、重排、生成的可替换边界。 | 项目主要是金融数据集实验框架，README 没有生产级文档解析、权限、多租户或引用协议；默认 E5/MS-MARCO 模型和英文数据需替换并在中文监管语料上重新评估。 |
| [FinanceRAG（ICAIF 2024）](https://github.com/cv-lee/FinanceRAG)（MIT） | [README](https://github.com/cv-lee/FinanceRAG) 描述金融专用 RAG 竞赛实现：query expansion/corpus refinement、dense retrieval、多阶段 rerank，并覆盖 FinQA、TAT-QA、ConvFinQA、FinanceBench 等任务。 | 可直接参考多金融任务的统一检索/重排实验设计，比单一数据集更适合做模型横评和消融。 | README 明确生成/长上下文部分未完全实现；偏英文 10-K/金融数据集，且实验环境依赖 OpenAI/Kaggle/CUDA，不是生产底座。 |
| [CentralBank-LLM](https://github.com/viczommers/CentralBank-LLM)（GPL-2.0） | [README](https://github.com/viczommers/CentralBank-LLM) 说明从美联储、英格兰银行、欧洲央行抓取一手文本，RAG 问答并生成宏观经济图表，答案提供来源、作者和页码引用；基于 LangChain、Chroma、Dash。 | 场景与监管制度最相近：展示了“只使用央行原文 + 页码引用 + 可视化”的端到端交互方式，可借鉴来源字段和问答 UX。 | 目标是宏观公开资料，不是中国银行监管制度/报表；GPL-2.0 对闭源/商用集成有合规影响；README 还记录 Chroma 删除/重建的状态问题，不宜直接照搬本地向量库生命周期。 |
| [TableRAG](https://github.com/yxh-y/TableRAG)（仓库未提供 LICENSE 文件，需先取得授权） | [README](https://github.com/yxh-y/TableRAG) 定义 SQL 执行 + 文本检索的混合框架，离线写入 MySQL，在线最多迭代推理，并用 HeteQA 评测异构文档多跳推理。 | 统计报表问答的关键参考：数值、同比/环比、跨行列聚合应走 SQL/确定性计算，制度解释再走文本 RAG；可借鉴离线入库与在线查询服务拆分。 | 依赖 MySQL、外部 LLM URL 和 HybridQA Excel 数据；仓库未见许可证，不能默认用于比赛交付；SQL 生成仍可能错误，必须做字段白名单、单位/期间检查和结果复算。 |
| [MinerU](https://github.com/opendatalab/MinerU)（MinerU Open Source License，Apache-2.0 加附加条款） | [README 中文版](https://github.com/opendatalab/MinerU/blob/master/README_zh-CN.md) 明确支持 PDF/DOCX/PPTX/XLSX/图片/网页到 Markdown/JSON，VLM+OCR，表格转 HTML、跨页表格合并、扫描件和复杂版面；[许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) 有商业阈值和在线服务署名条款。 | 适合作为制度 PDF、扫描件、带复杂表格的报表解析层，保留页码、表格结构和图片区域，降低切块前的信息损失。 | 解析质量会随扫描质量、印章、表格版式变化；需要对关键页/关键数字做人工或规则抽检；附加许可证条款需让法务确认，不能只看“Apache”标签。 |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag)（MIT） | [README](https://github.com/microsoft/graphrag) 将项目定位为从非结构化文本抽取结构化数据的 pipeline，并使用知识图谱记忆增强私有数据推理；同时明确索引成本高、代码是方法演示而非官方支持产品。 | 适合把监管机构、制度、条款、指标、报表、版本和引用关系建成图，支持跨制度/跨期追问和全局摘要；可作为复杂问题的二级召回。 | 图谱抽取本身可能产生实体/关系幻觉，索引成本和更新成本高；不能取代条款级原文引用。建议只在高价值跨文档问题启用，并保留原文证据链。 |
| [Ragas](https://github.com/vibrantlabsai/ragas)（Apache-2.0） | [README](https://github.com/vibrantlabsai/ragas) 提供 LLM 应用评估、生产对齐测试集生成和预置指标，覆盖 RAG/检索/生成评测。 | 可建立赛题的离线回归集：检索命中、上下文相关性、答案正确性、引用覆盖率、拒答率和表格数值误差，持续比较不同 chunk/embedding/reranker。 | LLM-as-a-judge 具有偏差，通用指标不等于监管可信度；应补充确定性检查（引用页存在、公式重算、版本有效期、单位一致）和人工审计。 |

## 更贴近监管/可信问答的研究原型

| 项目 | 可借鉴点 | 主要风险/边界 |
|---|---|---|
| [CSRC-RAG](https://github.com/Mindse-Tt/CSRC-RAG)（仓库未提供 LICENSE） | [README](https://github.com/Mindse-Tt/CSRC-RAG) 给出中文证监会处罚案例的 `意图分类 -> Query Plan -> Hybrid Retrieval -> 本地回复 -> 折叠证据` 链路，已有 BM25/dense hybrid、法规依据检索、证据片段展示和按问题类型评估。是“中文监管 + 证据展示”最接近的代码参考。 | README 自称第一版/baseline，数据是证券处罚而非银行制度和统计报表；默认 dense backend 仍是 `svd_tfidf`，需要换成中文金融 embedding/reranker 并补充制度版本治理；无许可证时不能直接复制代码。 |
| [regulatory-ai-agent](https://github.com/cdpedrobastos/regulatory-ai-agent) | [README](https://github.com/cdpedrobastos/regulatory-ai-agent) 展示基于 LangGraph 的 Self-RAG：Qdrant 检索后验证事实忠实度，低分时改写并重试，三次仍失败则走“不确定”节点；适合借鉴可信问答中的复核与拒答状态机。 | 面向 LGPD/EU AI Act，非中文银行监管；README 报告的评测仅小样本且 context precision 仍有限，自我评分不能替代证据蕴含和人工审计；依赖外部模型/API。采用前需确认许可证。 |
| [OmniEval](https://github.com/RUC-NLPIR/OmniEval) | [README](https://github.com/RUC-NLPIR/OmniEval) 是金融域 RAG 自动评测基准，提供知识语料构建、多个中文/多语 retriever 比较，以及 accuracy、completeness、utilization、numerical accuracy、hallucination 五类模型指标。 | 自动生成/模型评分仍会继承评委模型偏差；指标模型与语料域不完全等同于银行监管。适合做横向实验，不应作为唯一验收标准。 |
| [RAGChecker](https://github.com/amazon-science/RAGChecker) | [README](https://github.com/amazon-science/RAGChecker) 将指标拆成整体、retriever 和 generator 诊断，并要求输入问题、金标答案、模型回复和检索上下文；可定位错误来自“没召回”还是“召回后乱答”。 | 通用 benchmark 不是中文监管语料；claim-level/LLM 评估有调用成本和判断偏差，必须配合本地金标、规则计算与人工复核。 |
| [ST-Raptor](https://github.com/OpenDataBox/ST-Raptor)（MIT） | [README](https://github.com/OpenDataBox/ST-Raptor) 面向 Excel/HTML/Markdown/CSV 的半结构化表格问答，覆盖嵌套单元格、多行列头、不规则布局和金融表，可借鉴复杂监管统计表的结构化检索。 | 研究原型，不包含监管口径、引用和权限治理；README 的论文复现实例算力要求很高，中文适配也需实测，不能用公开 benchmark 准确率替代本地报表回归。 |

## 评测数据与算法参考（不是生产底座）

| 项目 | 能力与可借鉴点 | 风险 |
|---|---|---|
| [TAT-QA](https://github.com/NExTplusplus/TAT-QA) | README 给出 16,552 个问题、2,757 个来自真实财务报告的表格+文本混合上下文，并提供 TagOp 代码与测试集 ground truth；适合验证“表格 + 上下文段落”的问题类型。 | 财报英文数据、非监管制度；数据集和代码需遵守其引用/许可说明，不能代表中文监管指标口径。 |
| [FinQA](https://github.com/czyssrs/FinQA) | README 定义金融数据数值推理任务；每条样本含 `pre_text`、`post_text`、`table`、问题、推理程序、支持事实和执行答案，提供 retriever + program generator 与公私测试集。 | 适合借鉴“证据事实 + 可执行计算程序”的答案协议，不宜直接用于监管数据；老版本依赖 PyTorch 1.7/Transformers 4.4，工程环境过时。 |

## 对本赛题的组合建议

1. **解析层**：MinerU（或 RAGFlow 内置解析）输出带页码/表格坐标的 Markdown/JSON；对 OCR、跨页表格和关键数字建立抽检队列。
2. **检索层**：参考 FinRAG/FinanceRAG 的 dense embedding + cross-encoder rerank；制度条款增加 BM25/关键词和元数据过滤（发布机构、文号、生效/废止日期、适用范围）。
3. **数值层**：参考 TableRAG/FinQA，将统计报表的加总、占比、同比、环比等转为受控 SQL/程序执行；模型只负责意图和字段映射，最终数字由确定性执行器产生。
4. **证据与图谱层**：参考 RAGFlow 的可追溯引用；对跨制度关系再引入 GraphRAG，但每个结论必须回链到原文页/表格单元格。
5. **评测层**：以 TAT-QA/FinQA 的混合表格问题形式设计内部样本，使用 Ragas 做批量回归，同时加入引用存在性、版本时效、单位一致、计算误差和拒答准确率等金融监管专用指标。

## 采用前的检查清单

- 逐项核对许可证：CentralBank-LLM 为 GPL-2.0，TableRAG 当前仓库未见 LICENSE，MinerU 有 Apache-2.0 附加条款。
- 不把 GitHub README 的“支持引用/降低幻觉”当成监管可信保证；必须在本地制度和报表上做可复现实验，并保存检索快照与模型版本。
- 生产环境需要补齐权限隔离、敏感数据脱敏、文档版本/生效期管理、审计日志、失败拒答和人工复核，这些项目均未完整替代赛题工程要求。
