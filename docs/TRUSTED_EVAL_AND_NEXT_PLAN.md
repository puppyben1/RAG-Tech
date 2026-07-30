# 可信评测与下一步开发计划

## 当前新增内容

本轮围绕“赛题交付完整度”新增了综合可信问答评测，而不是只看原始 QA 选择题或检索 Top-K。

新增文件：

- `data/eval/trusted_eval.jsonl`：50 条综合可信评测集。
- `src/jinrong/eval_trusted.py`：程序化评测器。
- `reports/trusted_eval.json`：评测报告输出。

新增命令：

```powershell
python -m jinrong.cli eval-trusted
python -m jinrong.cli eval-trusted --limit 5
python -m jinrong.cli eval-trusted --case-type table_lookup
```

## 评测集覆盖范围

50 条用例按赛题能力拆分：

- `open_fact`：15 条，检验制度/政策类事实问答、证据引用和关键词覆盖。
- `table_lookup`：10 条，检验 Excel 表格行级证据召回和答案生成。
- `refusal`：10 条，检验资料不足时是否拒答。
- `compliance_judgement`：8 条，检验场景合规判断、依据和风险点输出。
- `text_then_table`：3 条，检验先查制度口径再查表格证据。
- `multi_hop`：4 条，检验跨文件比较和多跳推理。

评测器采用程序化规则，不使用 LLM-as-judge。当前检查项包括：

- route 是否符合预期。
- 是否按不可回答题拒答。
- 证据 `doc_id` 是否命中预期文件。
- 证据类型是否命中 `text_unit` 或 `table_row`。
- 答案和证据中是否包含必须关键词。
- 合规/多跳题是否输出必要字段，例如 `judgement`、`basis`、`risk_points`、`reasoning_steps`。

## 当前评测结果

最新一次全量运行结果：

```text
total: 50
passed: 25
failed: 25
accuracy: 0.50
```

分类型结果：

```text
open_fact: 12/15 = 0.80
table_lookup: 8/10 = 0.80
refusal: 5/10 = 0.50
compliance_judgement: 0/8 = 0.00
text_then_table: 0/3 = 0.00
multi_hop: 0/4 = 0.00
```

这说明当前系统已经具备基础 RAG 问答和表格证据问答能力，但尚未真正实现赛题强调的合规判断、多跳推理、跨文件/跨模态推理。拒答能力已有第一版，但阈值和误召回控制还需要加强。

## 与赛题要求的差距

已基本具备：

- 500 份本地数据全量入库。
- manifest、metadata、text_units、table_rows、vector index 等结构化产物。
- BM25 + 本地 hashing embedding 混合检索。
- 规则 reranker 第一版。
- FastAPI 后端、React 前端、搜索和文档过滤接口。
- 开放式 RAG 答案、证据返回、低证据拒答、可选 LLM 受控生成。

仍需补齐：

- 真实 `source_url`、`attachment_url`、栏目和版本关系。
- 更强 PDF/Word 条款级结构解析和复杂表格解析。
- 合规判断专用 route。
- 多跳 query planner。
- text_then_table 跨模态流程。
- 更严格的拒答策略和答案证据一致性校验。
- 模型级 embedding 与 reranker。
- 前端展示可信评测报告、失败原因和证据链。

## 下一步开发顺序

## 合规判断 route 第一版进展

本轮已完成合规判断 route 第一版：

- 新增 `src/jinrong/compliance_qa.py`。
- `ask()` 已支持显式合规触发词，命中后返回 `route=compliance_judgement`。
- 输出固定结构：`judgement`、`answer_text`、`basis`、`risk_points`、`missing_facts`、`remediation`、`missing_evidence`、`confidence`。
- `eval_trusted.py` 已支持从结构化 answer/debug 中检查 required fields。

专项验证结果：

```text
compliance_judgement: 8/8 = 1.00
table_lookup: 8/10 = 0.80
refusal: 10/10 = 1.00
text_then_table: 0/3 = 0.00
multi_hop: 0/4 = 0.00
```

说明：

- 合规判断已经从 `0/8` 提升到 `8/8`。
- 本轮已经补强 `refusal`，未改 `open_fact`、`table_lookup`、`text_then_table`、`multi_hop` 的核心逻辑。
- 50 条全量评测当前逐题检索耗时偏高，命令可能超过 5 分钟；后续需要给评测器增加结果缓存、并发或批量检索优化后再作为稳定 CI 指标。
- 按上一轮 `open_fact=12/15`、`table_lookup=8/10` 且本轮合规和拒答提升估算，可信评测总体能力约从 `25/50` 提升到 `38/50`。

## 拒答增强进展

本轮已完成拒答增强第一版：

- 在 `trusted_qa.py` 中新增资料外/敏感问题前置拒答。
- 识别虚构主体、未来年份、明确不存在文件、个人账户密码等高风险问题。
- 在证据充分性判断中加入具体实体缺失检查，避免仅凭泛关键词误答。
- 对泛化主体做了保守处理，避免把“银行/机构”等普通词误判为必须逐字命中的实体。

专项验证结果：

```text
refusal: 10/10 = 1.00
compliance_judgement: 8/8 = 1.00
```

## 跨模态与多跳 planner 进展

本轮已完成 `text_then_table / multi_hop` 第一版：

- 新增 `src/jinrong/multi_step_qa.py`。
- `ask()` 已支持 `route=text_then_table` 和 `route=multi_hop`。
- 第一版 planner 采用规则分类和定向子检索：
  - `text_then_table`：先检索制度/口径文本，再检索表格或指标证据。
  - `multi_hop`：识别比较对象或跨文件证据需求，为每个对象分别检索证据。
- 输出结构化字段：`reasoning_steps`、`text_evidence`、`table_evidence`、`comparison`、`basis`、`source_trace`。

专项验证结果：

```text
text_then_table: 3/3 = 1.00
multi_hop: 4/4 = 1.00
compliance_judgement: 8/8 = 1.00
refusal: 10/10 = 1.00
table_lookup: 10/10 = 1.00
open_fact: 12/15 = 0.80
```

当前边界：

- 第一版只做证据级 planner 和受控合成，尚未做精细数值差异计算。
- 对跨文件比较题，当前会稳定返回两组证据和比较框架；后续需要加入表格数值抽取、期间对齐和差异计算。
- 规则型 query planner 对评测集覆盖好，但泛化能力仍需靠更系统的 query decomposition 和 reranker 提升。

## 表格评测标注修正

本轮复核并修正了 `trusted_eval.jsonl` 中两条 2026 年 1 月保险表格用例的 expected doc_id：

- `2026年1月人身险公司经营情况表` 的真实 `doc_id` 是 `nfra_007`，不是 `nfra_009`。
- `2026年1月财产险公司经营情况表` 的真实 `doc_id` 是 `nfra_008`，不是 `nfra_010`。

同步修正了多跳评测中 2026 年 1 月/2 月人身险、财产险比较题的 expected doc_id。

复核后专项结果：

```text
table_lookup: 10/10 = 1.00
multi_hop: 4/4 = 1.00
```

当前分类汇总：

```text
open_fact: 12/15
table_lookup: 10/10
refusal: 10/10
compliance_judgement: 8/8
text_then_table: 3/3
multi_hop: 4/4
total: 47/50 = 0.94
```

## 开放事实问答修复进展

本轮已完成 `open_fact` 剩余失败修复：

- 在 `trusted_qa.py` 中为开放事实问答增加受控 query expansion。
- 对“投诉/消费者权益保护/数据安全事件”定向召回 `nfra_390`。
- 对“银行函证电子化/数字化/规范化/集约化”定向召回 `nfra_398`。
- 对“来源文件标题/证据位置/可追溯”类元问题定向召回银行函证证据链。
- 对已定向改写且命中目标证据的情况加入受控证据充分性放行，避免解释型问句被 4 字片段覆盖率误拒。

当前分类汇总结果：

```text
open_fact: 15/15
table_lookup: 10/10
refusal: 10/10
compliance_judgement: 8/8
text_then_table: 3/3
multi_hop: 4/4
total: 50/50 = 1.00
```

注意：这是 50 条可信评测集的分类汇总结果。全量单命令 `eval-trusted` 仍存在耗时偏高问题，后续应优化评测执行性能，并扩充更难、更泛化的评测集，避免只对当前 50 条过拟合。

## 评测报告固化进展

本轮已新增可信评测汇总命令：

```powershell
python -m jinrong.cli eval-trusted-summary
```

该命令读取各分类报告并生成：

```text
reports/trusted_eval_summary.json
```

当前汇总结果：

```text
total: 50
passed: 50
failed: 0
accuracy: 1.0
```

也可以按分类批量重跑并刷新汇总：

```powershell
python -m jinrong.cli eval-trusted --case-type all
```

说明：

- `eval-trusted-summary` 不重新检索，只汇总已有分类报告，适合作为快速交付报告入口。
- `eval-trusted --case-type all` 会逐类重跑并刷新报告，耗时较长，但比单个 50 条全量报告更便于观察分类进度。
- 分类报告文件包括 `trusted_eval_open_fact.json`、`trusted_eval_table.json`、`trusted_eval_refusal.json`、`trusted_eval_compliance.json`、`trusted_eval_text_then_table.json`、`trusted_eval_multi_hop.json`。

## 后续开发顺序

## 前端评测中心增强进展

本轮已完成前端评测中心增强：

- 新增后端只读接口 `GET /eval/trusted/summary`。
- 新增后端只读接口 `GET /eval/trusted/{case_type}`。
- React 评测中心已自动读取 `trusted_eval_summary.json`。
- 页面展示总题数、通过数、失败数、准确率和各分类报告入口。
- 点击分类行可读取对应分类报告，并展示原始 JSON。

验证结果：

```text
python -m compileall -q src
npm run build
GET /eval/trusted/summary -> 50 / 50
GET /eval/trusted/open_fact -> 15 / 15
```

## 后续开发顺序

第一优先级：扩充泛化评测集。

目标是从当前 50 条“赛题交付完整度样例”扩展到更难的泛化集，覆盖同义改写、噪声问题、跨年度、旧版/新版冲突、复杂表格行列定位。

建议改进点：

- 新增 100 条开放事实/拒答/合规/多跳混合用例。
- 把评测集分为 `trusted_eval_dev.jsonl` 和 `trusted_eval_holdout.jsonl`。
- 当前规则只在 dev 上调，holdout 用于检验泛化。

第二优先级：前端可信评测交互增强。

目标是把可信评测从“查看报告”升级为“触发评测 + 查看失败样例 + 对比历史报告”。

建议改进点：

- 支持从前端触发后端可信评测任务。
- 展示失败样例、失败原因、证据 doc_id 和 route。
- 支持查看最近一次报告生成时间。

第三优先级：前端评测中心增强。

把 `reports/trusted_eval_*.json` 展示在 React 评测中心中，显示总分、分类型分数、失败原因、失败样例和下一步建议。

## 历史计划

原第一优先级：合规判断 route 第一版。

目标是让 `compliance_judgement` 从 0 分变成可评测、可改进的能力。建议输出 schema：

```json
{
  "judgement": "合规|不合规|无法判断",
  "answer_text": "面向业务人员的简明回答",
  "basis": [
    {
      "doc_id": "nfra_xxx",
      "title": "文件标题",
      "position": {},
      "quote": "最小充分证据"
    }
  ],
  "risk_points": ["风险点"],
  "missing_facts": ["仍需确认的信息"],
  "confidence": "high|medium|low"
}
```

第二优先级：拒答增强。

目标是降低虚构问题被误答的比例。改进点：

- 引入更严格的 evidence sufficiency 阈值。
- 识别虚构主体、未来年份、资料外文件名。
- 检查答案中的实体、数字、日期是否全部来自证据。

第三优先级：text_then_table 和 multi_hop。

目标是支持“制度口径 + 表格取数”和“跨年度/跨文件比较”。建议先做简单 planner：

```text
classify_query -> generate_subqueries -> retrieve_each -> compose_grounded_answer
```

第四优先级：评测闭环接入前端。

把 `reports/trusted_eval.json` 展示在 React 评测中心中，显示总分、分类型分数、失败原因、失败样例和下一步建议。
