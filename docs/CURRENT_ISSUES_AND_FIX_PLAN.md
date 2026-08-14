# 当前问题与修复计划

更新时间：2026-08-14
适用范围：当前工作区代码、QA 迁移产物、来源治理与比赛验收门禁。

## 1. 当前结论

代码层面的用户体验、结构化拒答、Legacy QA 审计/迁移和复核导入能力已经实现。当前验证结果为：

- 后端测试：67 passed，1 个第三方弃用警告；
- 前端生产构建：通过；
- Legacy QA：300 条已迁移，其中 100 条 Excel 定位由程序验证；
- 复核 CSV 中的另外 200 条目前可通过机器定位校验。

但项目仍不能声明“最终验收通过”。主要原因不是代码无法运行，而是独立 holdout、人工复核审计、官方来源与版本数据尚未满足可信门禁。自动生成或自动填充的结果只能作为诊断证据。

## 2. 已完成修复

| 范围 | 已完成内容 | 验证方式 |
| --- | --- | --- |
| 前端体验 | 演示入口切换正确、动态文档数、API 设置弹层、Enter 发送/搜索、移除无实现入口、移动端适配 | `npm run build`，桌面/移动端浏览器检查 |
| 可信展示 | 显示结构化 `refusal_reason`、来源链接和版本状态；过期评测不再显示为当前成绩 | API/前端测试与构建 |
| QA 审计 | 新增 `qa-data-audit`，识别旧路径、正文型 evidence、歧义和未解析条目 | pytest 与 300 条实数审计 |
| QA 迁移 | 新增 `migrate-qa-data`；源 Excel 不被覆盖；Excel sheet/cell/value 实文件验证 | 100 条 Excel、265 个证据单元格验证通过 |
| 复核导入 | 新增 `import-qa-reviews`；限制候选文档、严格页码、PDF 证据相似度、DOCX 条款和 Excel 单元格校验 | 200/200 机器定位校验通过 |

## 3. 未解决问题

### P0-1：200 条 QA 尚无可审计的独立人工确认

**现状**

`data/intermediate/qa_migration_review.csv` 已填入 200 条定位，`import-qa-reviews` 可返回 200/200。但这些字段由自动脚本批量生成，当前格式没有 `reviewed_by`、`reviewed_at`、复核结论或第二人抽查记录。

**风险**

机器选择证据后再用同一证据评价机器，会形成循环验证。`reviewed_and_ready` 目前只能解释为“机器定位校验通过”，不能解释为“人工金标已批准”。

**修复办法**

1. 扩展复核 CSV 和导入器，增加 `review_status`、`reviewed_by`、`reviewed_at`；时间必须包含时区。
2. 保留自动填充结果作为候选，不直接签为人工结果。
3. 由非实现人员打开原始文档核对：文档身份、题目答案、页码/条款、版本。
4. 对 29 条原始歧义项和 16 条原始未解析项执行双人复核；其余条目至少抽查并记录抽样规则。
5. 导入器只有在审计字段完整且定位校验通过时，才能输出人工批准状态。

**验收条件**

- 每条批准记录都有真实复核者和带时区时间；
- 自动候选与人工批准记录分文件保存；
- 分歧项有处理结论；
- 不覆盖 `wendang/QA数据.xlsx`。

### P0-2：独立 holdout 门禁仍被阻塞

**现状**

`data/eval/frozen/freeze_manifest.json` 只有 6 条 holdout，每个类别 1 条；要求是 6 类各至少 5 条，共至少 30 条。当前还有 13 个 gold 字段问题，状态为 `pending_external_review`，门禁原因包括：

- `pending_external_review`；
- `incomplete_gold_cases:6`；
- `insufficient_category_samples`。

**修复办法**

1. 由非实现人员独立编写/复核 30 条 holdout，不从系统回答反推金标。
2. 补齐 `must_contain`、`critical_entities`、`gold_evidence`、拒答题 `refusal_reason`。
3. 使用 `approve-eval-holdout` 写出带复核身份的新文件。
4. 使用 `freeze-eval` 检查 dev/holdout 重叠、类别覆盖和数据指纹。
5. 门禁为 `ready_for_evaluation` 后才能运行 `eval-acceptance`。

**验收条件**

- 六类各不少于 5 条；
- gold 完整，无 dev/holdout 问题重复；
- 全部具有外部复核元数据；
- 最终报告绑定 holdout SHA-256，且未 stale。

### P0-3：当前 Legacy QA 不能直接作为 trusted-eval 输入

**现状**

最新 `reports/trusted_eval_summary.json` 显示 `total: 0`、`passed: 0`。原因是迁移后的 Legacy MCQ 结构与 trusted-eval 的六类契约不同，现有评测命令没有消费这些记录。0/0 不是通过，也不是有效成绩。

**修复办法**

1. 明确 Legacy MCQ 只作为回归集，或实现显式 schema 转换器；不能隐式混入独立 holdout。
2. 在 `eval-trusted` 增加空数据门禁：有效用例数为 0 时返回非零状态。
3. 为 MCQ、开放题、拒答、表格和多跳分别做契约测试。
4. 评测报告记录输入 schema、有效/跳过数量和跳过原因。

**验收条件**

- 输入 200 条时报告必须明确“评测了多少、跳过多少、为何跳过”；
- 0 个有效用例不能产生成功状态；
- Legacy 回归成绩不冒充独立 holdout 成绩。

### P0-4：官方来源和版本信息大面积缺失

**现状**

历史版本审计显示 500 个文档全部为 `version_status: unknown`；`source_url`、`attachment_url`、`effective_date` 覆盖均为 0。来源候选目录仅覆盖 4/500，且 4 条均缺 `reviewed_by` 和 `reviewed_at`，因此 `valid: false`。

**修复办法**

1. 按来源缺口清单分批查找监管机构官方网站和官方附件链接。
2. 保存来源页、附件哈希、发布日期、生效/失效日期和版本关系。
3. 使用 `verify-source-catalog` 做机器证明，再由具名人员 `approve-source-catalog`。
4. 只有批准后才执行 `import-source-catalog` 和 manifest enrichment。
5. 未确认项保持 `unknown`，禁止猜测 URL 或版本。

**验收条件**

- 权威性声明均有机器证明或具名人工复核；
- 当前/废止/未知状态可解释；
- 问答默认不把未知或废止版本描述为现行依据。

### P1-1：项目级路径审计尚未闭环

**现状**

历史 `reports/path_audit.json` 包含 524 个问题：514 个 legacy absolute path、10 个 invalid project ref。新的 reviewed QA 产物单独路径审计为 0 个问题，但不能代表全项目已通过。

**修复办法**

1. 区分只读历史字段与新持久化字段。
2. 新产物统一写项目相对路径。
3. 原始 QA 和原始资料不原地改写；通过迁移层保存标准化引用。
4. 在最终候选产物上重新运行全量 path audit。

**验收条件**

- 新生成和最终提交的产物无机器绝对路径；
- 历史绝对路径仅存在于明确标记的只读 legacy 字段。

### P1-2：旧 `.doc` 文档仍需要质量审计

**现状**

`.docx` 可以做正文条款检查；旧 `.doc` 当前只能使用弱提取或人工确认。仓库中没有当前、完整且已批准的 doc-quality 报告。

**修复办法**

1. 运行 `doc-quality-audit` 生成 `.doc` 工作清单。
2. 必要时转换副本用于解析，但不覆盖原始 `.doc`。
3. 对空文本、乱码、低覆盖文档做具名人工复核。
4. 将批准记录与原文件哈希绑定。

**验收条件**

- 每个 `.doc` 有可用提取结果或人工批准记录；
- 空提取和乱码不会静默进入检索库。

### P1-3：工作区混有非交付产物

**现状**

当前工作区包含 SQLite、历史评测报告、日志、自动填充 CSV、多版中间文件、探针/补丁脚本和测试输出。它们不都属于本次代码修复。

**修复办法**

GitHub 提交使用显式文件清单，只包含源码、正式测试、正式规范和必要的候选/工作清单。排除：

- `data/db/jinrong.sqlite3`；
- `backend.err`、`frontend/vite.err`；
- `scripts/_probe_*`、`scripts/_patch_*` 等临时脚本；
- `qa_review_test_*`、多版自动填充 CSV；
- 未经批准重新生成的 trusted-eval/source/version 报告。

**验收条件**

- `git diff --check` 通过；
- 提交中没有日志、临时脚本、本地数据库和伪人工产物；
- PR 描述明确测试结果与未解决门禁。

### P2-1：测试依赖存在弃用警告

**现状**

pytest 通过，但 FastAPI TestClient 报告 Starlette/httpx 兼容层弃用警告。

**修复办法**

单独评估依赖升级和兼容性，更新锁文件后运行完整 API 契约测试。该问题不应与本次可信数据修复混在一个提交中。

## 4. 推荐执行顺序

1. 清理 GitHub 提交范围并发布当前代码修复 PR。
2. 修复 Legacy QA 复核审计字段和 trusted-eval 的 0 用例门禁。
3. 组织 200 条 QA 的独立人工复核，自动定位只作为辅助。
4. 完成六类各 5 条的独立 holdout，批准并冻结。
5. 分批完成官方来源/版本治理和 `.doc` 质量审计。
6. 运行绑定当前代码、当前数据指纹的最终 acceptance。

## 5. 当前不得宣称的结论

在上述 P0 门禁完成前，不得宣称：

- 200 条 QA 已完成人工复核；
- 0/0 trusted-eval 是通过；
- 历史 50/50、60/60 或诊断 A/B 是当前最终成绩；
- 500 个文档均有官方来源或均为现行版本；
- 比赛准确率、引用率、拒答率或延迟已经最终达标。
