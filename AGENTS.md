# RAG-Tech 项目协作指南

本文件适用于整个仓库。修改代码前先阅读 `README.md`、`docs/RUNBOOK.md`，涉及需求、数据契约或可信策略时同时阅读 `docs/spec/` 下的对应文档。

## 1. 修改原则

- 先确认目标、现状和成功标准，再开始修改。
- 使用最小且完整的改动解决问题，不添加未要求的功能、抽象或配置。
- 保持现有目录结构、命名和代码风格，不顺手重构无关代码。
- 保留用户已有改动；发现无关问题时说明，不擅自清理。
- 新行为应优先复用现有实现，避免保留两套重复逻辑。

## 2. 项目结构

- `src/jinrong/`：Python 3.10+ 后端、CLI、检索、评测和治理逻辑。
- `frontend/`：React 19 + Vite 前端。
- `tests/`：pytest 测试。
- `data/`：原始、处理后、索引及评测数据。
- `reports/`：评测和审计产物。
- `docs/spec/`：需求、接口、数据契约和可信策略。
- `scripts/`：Windows PowerShell 环境与复现脚本。

## 3. 数据与产物安全

- 不删除或覆盖 `wendang/`、`data/raw/` 中的原始资料。
- 除非任务明确要求，不重新生成 SQLite、索引、评测数据或报告。
- 不提交 `.venv/`、`node_modules/`、日志、错误输出或本地密钥。
- 所有持久化路径优先使用项目相对路径，不写入机器相关的绝对路径。
- 涉及来源、版本、评测或可信判断时，保持现有 fail-closed 规则和证据链。

## 4. 实现与验证

- 修复 Bug 时优先添加或运行能够复现问题的测试。
- 后端改动先运行相关测试，再运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\相关测试.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

- 前端改动至少运行：

```powershell
Set-Location frontend
npm run build
```

- CLI 或 API 改动应补充对应 smoke/contract 测试，并确认 `python -m jinrong.cli --help` 可用。
- 不为修复本任务而修改无关的失败测试；在交付说明中单独报告。

## 5. 长时间运行任务

- 空输入轮询的 `write_stdin` 使用至少 `180000` 毫秒的等待时间；不需要中间输出时优先 `300000`。
- `functions.wait` 使用至少 `180000` 毫秒的等待时间。
- 外层执行等待时间应比内部最长等待至少多 `30000` 毫秒。
- 发送交互输入的非空 `write_stdin` 不适用上述长等待。
- 进程仍在运行时不要仅为报告“仍在运行”而唤醒。

## 6. 任务交付

- 交付前检查 `git diff` 和 `git status`，确保没有冲突标记、临时文件或意外改动。
- 说明修改内容、验证结果、未解决风险和未执行的验证。
- 未经明确要求，不创建提交、不推送远端、不删除 worktree。

## 7. 禁用 Superpowers

本仓库不调用或执行 Superpowers 技能及其工作流，也不创建 `docs/superpowers/` 下的计划或设计文档。
