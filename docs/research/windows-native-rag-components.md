# Windows 原生可用 RAG 项目与组件调研

调研日期：2026-08-07  
目标：在不使用 WSL、Docker 或 Linux 的前提下，增强 `D:\Bisai\RAG-Tech`，覆盖中文监管制度、Word/PDF/Excel、混合检索、表格取数、证据回链、拒答和评测。

## 结论

没有必要把 `RAG-Tech` 替换成一个完整的 RAG 应用。当前工程已经有监管版本治理、`table_rows/table_cells`、确定性 Excel 计算、可信证据和拒答评测；通用应用通常只解决“导入、召回、对话”，不能直接满足 `sheet!cell`、单位/期间、过期制度过滤和关键数字复算。

推荐保持 `RAG-Tech` 为主工程，按以下顺序抽取组件：

1. **Docling** 替换/增强 PDF、DOCX、XLSX 结构化解析。
2. **BCEmbedding**（轻量中文优先）或 **FlagEmbedding/BGE-M3**（多功能）替换现有 embedding/reranker。
3. **Haystack 的检索算法**借鉴或局部接入：BM25、向量召回、RRF/分数融合和 XLSX sheet 级导入。
4. **Qdrant Client local mode** 作为可选 Windows 持久化向量索引；小规模数据也可继续用当前 JSON 索引。
5. **Ragas** 接入现有评测；`RAGChecker` 仅作为离线研究指标，不作为比赛运行时依赖。

## 候选项目和组件

### 1. Docling：直接引入，优先级最高

- 官方仓库：[docling-project/docling](https://github.com/docling-project/docling)
- 许可证：MIT（仓库 `LICENSE`）。
- 官方 README 明确支持 PDF、DOCX、XLSX、HTML、图片等，并提供表格结构、版面顺序、OCR、Markdown/JSON 导出和本地/离线执行；安装是 `pip install docling`，README 明确写明支持 macOS、Linux 和 **Windows x86_64/arm64**。
- 适合替换 `src/jinrong/text_parser.py` 的复杂 PDF/DOCX 路径，并作为 Excel 结构解析的候选输入层。
- 不应直接替换现有 `excel_parser.py`：Docling 的表格导出需要再映射到现有 `doc_id/sheet_name/cell_ref/row_index/col_index/unit/period` 数据合同。
- 依据：[README.md](https://github.com/docling-project/docling/blob/main/README.md)、[安装文档](https://docling-project.github.io/docling/getting_started/installation/)。

### 2. Haystack：直接引入算法组件，适合真实 Windows 环境

- 官方仓库：[deepset-ai/haystack](https://github.com/deepset-ai/haystack)
- 许可证：Apache-2.0；`pyproject.toml` 要求 Python >=3.10，分类器包含 `Operating System :: OS Independent`。
- 官方源码提供 `InMemoryBM25Retriever`、`InMemoryEmbeddingRetriever` 和 `DocumentJoiner`。Joiner 支持 `reciprocal_rank_fusion`、加权 merge 和分数分布融合，正好可补足当前“关键词/向量双路召回”的融合层。
- 官方 `XLSXToDocument` 使用 pandas/openpyxl，支持指定 sheet 或全部 sheet，并把 sheet 名写入元数据；这可以作为导入层参考。但它输出的是 sheet 级 Document，不是单元格级事实，仍需使用当前表格解析和证据合同。
- 适合“局部接入”而非重写整个应用：保留现有 `retrieval.py` 的治理过滤和结果结构，只调用其 BM25/RRF 逻辑，或者复制经过审查的算法实现。
- 依据：[README.md](https://github.com/deepset-ai/haystack/blob/main/README.md)、[pyproject.toml](https://github.com/deepset-ai/haystack/blob/main/pyproject.toml)、[XLSXToDocument](https://github.com/deepset-ai/haystack/blob/main/haystack/components/converters/xlsx.py)、[BM25](https://github.com/deepset-ai/haystack/blob/main/haystack/components/retrievers/in_memory/bm25_retriever.py)、[DocumentJoiner](https://github.com/deepset-ai/haystack/blob/main/haystack/components/joiners/document_joiner.py)。

### 3. BCEmbedding：直接引入，中文 reranker 首选

- 官方仓库：[netease-youdao/BCEmbedding](https://github.com/netease-youdao/BCEmbedding)
- 许可证：Apache-2.0；README 提供 `pip install BCEmbedding==0.1.5`。
- 官方说明 `EmbeddingModel` 支持中文/英文，`RerankerModel` 支持中文、英文、日文、韩文；reranker 是 cross-encoder，能处理长段落并提供相关性分数，还提供 LangChain/LlamaIndex 适配。
- 适合替换 `src/jinrong/reranker.py`，先对 BM25/向量候选进行 20~50 条重排，再由可信层做阈值拒答。模型下载和 PyTorch 的 CPU/CUDA 选择要在本机单独做 smoke test；不要把 README 的 SOTA 声明当作本赛题指标证明。
- 依据：[README.md](https://github.com/netease-youdao/BCEmbedding/blob/master/README.md)、[LICENSE](https://github.com/netease-youdao/BCEmbedding/blob/master/LICENSE)。

### 4. FlagEmbedding / BGE-M3：直接引入或作为第二候选

- 官方仓库：[FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)
- 许可证：MIT。
- 官方模型表把 `BAAI/bge-m3` 定义为多语言、多功能模型，支持 dense、sparse 和 multi-vector 检索，最大粒度 8192 tokens；同仓库提供 `bge-reranker-v2-m3` 等 cross-encoder reranker，以及 pip 安装和推理示例。
- BGE-M3 的 sparse 输出可以补中文关键词召回，但当前 `RAG-Tech` 需要先设计统一索引格式；短期只启用 dense embedding + `bge-reranker-v2-m3`，不要同时引入 ColBERT/multi-vector。
- 依据：[README.md](https://github.com/FlagOpen/FlagEmbedding/blob/master/README.md)、[BGE-M3 说明](https://github.com/FlagOpen/FlagEmbedding/tree/master/research/BGE_M3)。

### 5. Qdrant Client local mode：直接引入为可选索引

- 官方仓库：[qdrant/qdrant-client](https://github.com/qdrant/qdrant-client)
- 许可证：Apache-2.0；`pyproject.toml` 要求 Python >=3.10。
- 官方 README 提供 `pip install qdrant-client`，并明确支持无需启动 Qdrant server 的 local mode：`QdrantClient(":memory:")` 或 `QdrantClient(path="...")` 持久化到磁盘。
- 这是 Windows 原生环境可行的替代方案：不运行 Linux server、不要求 Docker。先用 `path=data/index/qdrant` 做实验；若索引迁移导致不稳定，可以继续使用现有 JSON 向量索引。
- 依据：[README.md](https://github.com/qdrant/qdrant-client/blob/master/README.md)、[pyproject.toml](https://github.com/qdrant/qdrant-client/blob/master/pyproject.toml)。

### 6. Chroma：可用但不是首选

- 官方仓库：[chroma-core/chroma](https://github.com/chroma-core/chroma)
- 许可证：Apache-2.0；`pyproject.toml` 要求 Python >=3.9，并声明 `Operating System :: OS Independent`；README 提供 `pip install chromadb`。
- 适合快速原型的本地向量库，但 Windows 原生部署应锁定版本并验证 `chroma-hnswlib` wheel；不要让它取代当前的监管元数据和 SQLite 治理库。
- 依据：[README.md](https://github.com/chroma-core/chroma/blob/main/README.md)、[pyproject.toml](https://github.com/chroma-core/chroma/blob/main/pyproject.toml)。

### 6.1 FAISS：Windows CPU 可用，但更适合保留为底层索引

- 官方仓库：[facebookresearch/faiss](https://github.com/facebookresearch/faiss)
- 许可证：MIT。官方 `INSTALL.md` 明确列出 Windows x86-64 可安装 CPU-only `faiss-cpu` conda 包；GPU 包只列 Linux，因此 Windows 方案应按 CPU 处理。
- FAISS 只提供向量索引，不提供 metadata 过滤、BM25、引用或版本治理。它可以替换当前向量相似度计算，但迁移收益小于直接改善 embedding/reranker；若使用 pip wheel，应固定来源和版本，官方推荐的稳定安装路径是 conda。
- 依据：[INSTALL.md](https://github.com/facebookresearch/faiss/blob/main/INSTALL.md)、[LICENSE](https://github.com/facebookresearch/faiss/blob/main/LICENSE)。

### 7. Ragas：直接引入评测，不参与问答运行时

- 官方仓库：[explodinggradients/ragas](https://github.com/explodinggradients/ragas)
- 许可证：Apache-2.0；README 的安装为 `pip install ragas`，提供 RAG 指标和 `ragas quickstart rag_eval`。
- 可把现有 `trusted_eval.jsonl` 转换为 Ragas 输入，增加 context precision/recall、faithfulness 等指标。但 LLM-based 指标通常需要外部或本地可调用模型，必须固定评测模型和提示词，避免指标漂移。
- 依据：[README.md](https://github.com/explodinggradients/ragas/blob/main/README.md)、[LICENSE](https://github.com/explodinggradients/ragas/blob/main/LICENSE)。

### 8. RAGChecker：仅参考/离线评测

- 官方仓库：[amazon-science/RAGChecker](https://github.com/amazon-science/RAGChecker)
- 许可证：Apache-2.0；提供 CLI/Python pipeline 和中英文教程，输出 claim recall、context precision、faithfulness、hallucination 等细粒度指标。
- 但其示例依赖 spaCy 模型和 extractor/checker LLM，README 没有 Windows 原生保证；因此先作为离线分析脚本，不放进比赛服务依赖，也不能替代当前确定性数字/拒答评测。
- 依据：[README.md](https://github.com/amazon-science/RAGChecker/blob/main/README.md)、[pyproject.toml](https://github.com/amazon-science/RAGChecker/blob/main/pyproject.toml)。

## 完整 Windows 应用：只参考，不迁移主线

| 项目 | 官方 Windows 证据 | 价值 | 判定 |
|---|---|---|---|
| [PrivateGPT](https://github.com/zylon-ai/private-gpt) | README 提供 Windows PowerShell 的 `uv tool install` 和 `private-gpt serve`；支持文档摄取、引用、CSV/表格分析。`pyproject.toml` 当前要求 Python >=3.11,<3.12，并依赖 MarkItDown、LlamaIndex/Qdrant 等。 | API、引用、工具和表格分析设计值得参考。 | **仅参考**：迁移整套应用会替换当前数据合同，模型/依赖较重。 |
| [Kotaemon](https://github.com/Cinnamon/kotaemon) | README 要求 Python >=3.10；非 Docker 安装给出 uv/conda 方案，声明混合全文+向量检索、重排、表格/图像、多跳和引用。 | 前端引用预览、低相关警告、问题分解值得参考。 | **仅参考**：依赖 Unstructured/可选 GraphRAG，缺少监管版本和单元格证据合同。 |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | README 明确有 Windows Desktop，支持 PDF/TXT/DOCX 等和 source citations；MIT。 | 可参考 UI、工作区和引用交互。 | **仅参考**：主仓库是 Node/桌面应用，Excel 确定性计算与监管治理不匹配。 |
| [LlamaIndex](https://github.com/run-llama/llama_index) | MIT，pip 安装；提供数据连接器、索引、retriever、query engine 和 reranker。 | 适配层和组件生态很大。 | **仅参考/局部使用**：不要因框架生态重写现有核心。 |
| [LangChain](https://github.com/langchain-ai/langchain) | MIT，pip 安装，生态广。 | 可参考 Runnable/结构化输出和模型适配。 | **仅参考/局部使用**：不能替代表格与可信治理。 |

### LangChain 与 LlamaIndex 的 Windows 判断

- 两者核心包都要求 Python >=3.10,<4.0，许可证均为 MIT，安装和核心运行没有服务端或 Linux 强制依赖；在当前 Windows Python 工程中可以使用。
- Windows 可用性最终取决于所选 connector/vector store/parser 的二进制依赖，而不是框架本身。例如选择 Docling、Qdrant local mode 和 Hugging Face/PyTorch CPU 时可以保持原生 Windows；选择某些 OCR、GPU 或服务端数据库插件时仍可能引入平台限制。
- 现有工程不需要同时引入两套框架。若确实需要现成 pipeline，Haystack 的 BM25/RRF/XLSX 能力更直接；LangChain/LlamaIndex 只用于已有模型或组件没有简单 Python API 时的适配。
- 依据：[LangChain pyproject.toml](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/pyproject.toml)、[LlamaIndex core pyproject.toml](https://github.com/run-llama/llama_index/blob/main/llama-index-core/pyproject.toml)。

## 解析器取舍

- **Docling：首选**。官方明确支持 Windows、PDF/DOCX/XLSX、表格和 OCR，且 MIT；先做 10 份制度 + 20 份表格的 A/B 解析对比。
- **Unstructured：备选**。Apache-2.0 且有 Windows conda 指引，但 PDF/Office 常依赖 poppler、tesseract、LibreOffice，原生 Windows 安装链更长；不要把 `all-docs` 作为第一步。
- **MinerU：可在 Windows 原生安装，但列为第二候选**。当前官方 README 明确支持 Windows、Python 3.10--3.12、纯 CPU，并提供 `uv pip install -U "mineru[all]"`；Docker 才要求 Linux/WSL2。它适合复杂 PDF、OCR、跨页表格的 A/B 解析，但需要较大的模型/磁盘资源，且仓库采用基于 Apache-2.0 的带附加条件的 MinerU Open Source License，比赛交付前必须审查许可证和模型条款。先用 Docling 做轻量基线，再用 MinerU 比较复杂样本。

MinerU 依据：[README.md](https://github.com/opendatalab/MinerU/blob/master/README.md)、[LICENSE.md](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)。

## 最小改造顺序

### P0：建立可回退的组件接口

新增配置开关，不删除旧实现：

```text
PARSER_BACKEND=legacy|docling
EMBEDDING_BACKEND=legacy|bce|bge
VECTOR_BACKEND=json|qdrant_local
RERANKER_BACKEND=none|bce|bge
```

所有后端都必须输出现有 `text_units/table_rows/table_cells` 合同，且保留 `doc_id/source_url/version_status/effective_from/effective_to`。

### P1：先换中文检索质量

1. 安装并 smoke test `BCEmbedding`；若 CPU 太慢，测试 `bge-reranker-v2-m3`。
2. 用同一批候选、同一 top-k 跑现有 `retrieval_eval.jsonl`。
3. 只有在制度题和拒答题不退化时才更新默认 reranker。

### P2：接入 Docling 解析

1. 先只对 PDF/DOCX 做 side-by-side 输出。
2. 对 XLSX 只使用 Docling/Haystack 作为结构提示，最终仍由 `excel_parser.py` 生成 cell facts。
3. 加入页码、表名、sheet 名等 metadata 后再写入索引。

### P3：补真正的混合检索

用 Haystack 的 BM25 + dense + RRF 思路，或直接复制其小型融合算法到 `retrieval.py`。中文分词和字段权重仍由本项目控制；融合结果必须重新经过版本过滤和证据门禁。

### P4：可选迁移向量存储

小规模比赛数据优先保留 JSON/SQLite；仅当索引规模或查询性能成为瓶颈时才启用 Qdrant local mode。索引 manifest 必须记录模型名、维度、归一化方式、代码版本和数据哈希。

### P5：评测门禁

把 Ragas/RAGChecker 的指标作为辅助报告，保留本项目的确定性门禁：制度准确率、表格数值/单位/期间、`sheet!cell` 命中、过期制度过滤和无依据拒答。任何新组件只有通过相同题集 A/B 对比后才成为默认实现。

## 最终建议

在当前电脑条件下，最稳的 Windows 原生路线是：

> **`RAG-Tech` 主工程 + Docling 解析 + BCEmbedding/BGE reranker + Haystack RRF 算法 +（可选）Qdrant local mode + Ragas 辅助评测。**

不要 fork WeKnora、RAGFlow 或 PrivateGPT 作为新主线；它们的完整应用层会带来部署和数据模型迁移成本，且没有直接解决比赛要求的监管版本治理与单元格级证据。

## 官方来源索引

- [Docling README](https://github.com/docling-project/docling/blob/main/README.md)
- [Docling installation](https://docling-project.github.io/docling/getting_started/installation/)
- [Haystack README](https://github.com/deepset-ai/haystack/blob/main/README.md)
- [Haystack pyproject](https://github.com/deepset-ai/haystack/blob/main/pyproject.toml)
- [Haystack XLSXToDocument](https://github.com/deepset-ai/haystack/blob/main/haystack/components/converters/xlsx.py)
- [Haystack BM25 retriever](https://github.com/deepset-ai/haystack/blob/main/haystack/components/retrievers/in_memory/bm25_retriever.py)
- [Haystack DocumentJoiner](https://github.com/deepset-ai/haystack/blob/main/haystack/components/joiners/document_joiner.py)
- [BCEmbedding README/LICENSE](https://github.com/netease-youdao/BCEmbedding/tree/master)
- [FlagEmbedding README](https://github.com/FlagOpen/FlagEmbedding/blob/master/README.md)
- [Qdrant Client README](https://github.com/qdrant/qdrant-client/blob/master/README.md)
- [Chroma README/pyproject](https://github.com/chroma-core/chroma/tree/main)
- [Ragas README](https://github.com/explodinggradients/ragas/blob/main/README.md)
- [RAGChecker README](https://github.com/amazon-science/RAGChecker/blob/main/README.md)
- [Unstructured README](https://github.com/Unstructured-IO/unstructured/blob/main/README.md)
- [PrivateGPT README](https://github.com/zylon-ai/private-gpt/blob/main/README.md)
- [Kotaemon README](https://github.com/Cinnamon/kotaemon/blob/main/README.md)
- [AnythingLLM README/LICENSE](https://github.com/Mintplex-Labs/anything-llm/tree/master)
- [LlamaIndex README](https://github.com/run-llama/llama_index/blob/main/README.md)
- [LangChain README](https://github.com/langchain-ai/langchain/blob/master/README.md)
- [Faiss INSTALL](https://github.com/facebookresearch/faiss/blob/main/INSTALL.md)
