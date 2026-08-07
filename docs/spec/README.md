# 可信 RAG 规范入口

状态：实施中（W0-W6 工程基线已验证，最终独立 holdout 验收待外部复核）  
建立日期：2026-08-06
更新日期：2026-08-07

## 1. 权威顺序

发生冲突时，按以下顺序处理：

1. `wendang/03-金融大模型与智能体赛道-南京银行-面向银行业监管制度与统计报表的可信RAG问答.docx`
2. 本目录中已批准的稳定规范
3. 已批准的 change spec
4. OpenAPI、Pydantic schema 和数据 schema
5. 源码实现
6. `docs/` 下的历史方案、路线图和执行记录
7. `reports/` 下的历史运行结果

代码或报告不能静默覆盖赛题要求。发现冲突时，应建立 change spec 或缺口记录。

## 2. 当前规范状态

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| `docs/SPEC.md` | 历史快照 | 仅用于了解早期实现，不作为当前验收基线 |
| `docs/competition-requirements-audit.md` | 审计证据 | 记录赛题要求、实现事实和缺口 |
| `docs/SPEC_DRIVEN_RECOVERY_PLAN.md` | 已接受的工作方向 | 定义轻量、增量、验收驱动的 Spec 方法 |
| `REQUIREMENTS.md`、`DATA_CONTRACTS.md`、`API_CONTRACTS.md`、`TRUST_POLICY.md`、`ACCEPTANCE.md`、`TRACEABILITY.md` | 当前基线 | 需求、契约、信任门禁、验收和追踪矩阵 |
| `changes/CR-20260806-reproducible-baseline.md` | Verified | P0-A 可复现基线设计与验证记录 |
| `changes/CR-20260807-windows-competition-delivery.md` | Implementing | Windows 原生参赛交付主 change spec |
| `changes/CR-20260807-w4-w6-results.md` | Verified | holdout 门禁、检索 A/B 和前端链路验证结果 |

最终成绩仍不得引用历史 50/50 或诊断 A/B 报告。只有外部非实现人员完成 30 题独立 holdout 金标复核、冻结门禁为 `ready_for_evaluation`，且 `eval-acceptance` 生成当前且未 stale 的通过报告后，才能声明比赛量化指标通过。

## 3. Change Spec 规则

每个 change spec 必须包含：

- 状态、背景、范围和非目标；
- 可验证的 MUST/SHOULD 要求；
- 契约、兼容性和迁移影响；
- 验收场景、命令和产物；
- 风险、回滚条件和未决事项。

状态流转为：`Proposed -> Approved -> Implementing -> Verified -> Archived`。未经批准的 change spec 不授权修改业务代码、数据或生成产物。

运行结果不回写为规范事实。验收证据应保存在带 run ID 的报告目录，并记录 Git 提交、输入数据指纹和运行环境。
