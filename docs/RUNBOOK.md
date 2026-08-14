# 可复现基线运行手册

## 支持环境

- Windows 10/11 x64
- CPython 3.12.6（允许同一 3.12 补丁系列）
- Node.js 22.18.0（允许同一 22.x LTS 补丁系列）
- npm 10.x
- 默认解析器 profile：`portable`

基线不要求 LLM API Key，也不会自动探测 LibreOffice。

## 安装

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

脚本创建 `.venv`，使用 `requirements-dev.lock.txt` 的哈希严格安装 Python 依赖，并通过 `npm ci` 安装前端依赖。只安装后端时可传 `-SkipFrontend`。

## 快速验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_baseline.ps1 -SkipPathAudit
```

`-SkipPathAudit` 仅用于当前历史产物尚未重建时。正式验收必须移除该参数；发现旧绝对路径、越界引用、无效引用或缺失目标时，路径审计返回非零。

每次运行还会写入 `reports/acceptance/<run-id>/baseline.json`。报告包含锁文件、输入数据快照、核心产物哈希和逐项门禁结果；脏工作区会标记为 `diagnostic_dirty_worktree`，不能作为批准基线。

## 从原始资料重建

以下命令会覆盖 `data/processed`、`data/index` 和部分 `reports` 产物，只能在临时仓库副本中运行：

推荐直接创建隔离副本并完成全量门禁：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rebuild_isolated.ps1 -DestinationRoot "$env:TEMP\jinrong-rebuild-01"
```

目标目录必须不存在且位于当前仓库之外。脚本不会修改当前仓库的历史产物。
如果当前工作树只包含 Git LFS 指针，必须显式指定已经展开的原始 `wendang` 目录；脚本会在复制前拒绝指针文件：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rebuild_isolated.ps1 `
  -DestinationRoot "$env:TEMP\jinrong-rebuild-01" `
  -RawInputRoot "D:\Bisai\RAG-Tech\wendang"
```

```powershell
$env:PYTHONPATH = "src"
$env:JINRONG_PARSER_PROFILE = "portable"
.\.venv\Scripts\python.exe -m jinrong.cli build-manifest
.\.venv\Scripts\python.exe -m jinrong.cli build-kb
.\.venv\Scripts\python.exe -m jinrong.cli build-metadata
.\.venv\Scripts\python.exe -m jinrong.cli build-text-units
.\.venv\Scripts\python.exe -m jinrong.cli enhance-table-rows
.\.venv\Scripts\python.exe -m jinrong.cli build-vector-index
.\.venv\Scripts\python.exe -m jinrong.cli import-db --reset
```

不要对旧 `E:\work\code\JINRONG` 字符串做批量替换。正式迁移方式是从 `wendang/` 原始资料重建全部下游产物。

## API smoke

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m jinrong.cli serve --port 8000
```

另开终端检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/kb/status
Invoke-RestMethod http://127.0.0.1:8000/documents?limit=1
Invoke-RestMethod -Method Post -ContentType application/json -Body '{"query":"银行"}' http://127.0.0.1:8000/search
Invoke-RestMethod -Method Post -ContentType application/json -Body '{"question":"银行监管是什么？"}' http://127.0.0.1:8000/ask
```

## Legacy QA 迁移与复核

以下命令不会修改 `wendang/QA数据.xlsx`。审计发现旧路径、正文型 evidence、歧义或未解析文档时返回非零状态：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m jinrong.cli qa-data-audit `
  --qa wendang/QA数据.xlsx `
  --manifest data/processed/manifest.jsonl
```

生成结构化候选和人工复核清单：

```powershell
.\.venv\Scripts\python.exe -m jinrong.cli migrate-qa-data `
  --qa wendang/QA数据.xlsx `
  --manifest data/processed/manifest.jsonl `
  --output data/intermediate/qa_migration_candidates.jsonl `
  --review-worklist data/intermediate/qa_migration_review.csv
```

候选产物不是冻结 holdout。`ready_candidate` 仅表示文档和 Excel 单元格定位可以确定解析；其余状态必须人工补充文档选择、页码或条款定位，并通过独立 holdout 审核后才能用于最终验收。

## 显式 LibreOffice profile

`libreoffice` 不属于首个批准基线。仅在单独验证时设置：

```powershell
$env:JINRONG_PARSER_PROFILE = "libreoffice"
$env:JINRONG_LIBREOFFICE_EXECUTABLE = "C:\Program Files\LibreOffice\program\soffice.exe"
$env:JINRONG_LIBREOFFICE_VERSION = "24.8"
```

可执行文件或版本不匹配时构建会明确失败，不会回退到 PATH 自动探测。
