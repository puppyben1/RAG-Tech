# CR-20260806：可复现基线

状态：Implementing  
优先级：P0-A  
创建日期：2026-08-06  
实施授权：是；2026-08-06 按默认决策进入实施，生成产物只能在隔离副本中重建

## 1. 背景

仓库已有完整功能型 MVP 和历史评测产物，但当前工作机不能直接复跑：系统 Python 缺少 `openpyxl`，Codex 运行时缺少 `xlrd`，前端没有安装 `node_modules`。现有 manifest、知识库产物和报告还保存旧机器 `E:\work\code\JINRONG` 的绝对路径。

路径问题来自实现契约，而不只是旧文件：`manifest.py` 将 `path.resolve()` 写入 `local_path`；知识库、索引、评测和审计模块又把绝对路径继续复制到 JSONL、JSON、SQLite 和 API 响应。因此，直接替换历史文件文本不能建立可复现基线。

本变更先恢复“可安装、可构建、可换目录运行、可审计”的基线，不改变 RAG 算法和业务回答策略。

## 2. 目标

本变更完成后，维护者必须能够在一台符合支持矩阵的新环境中：

1. 使用锁定依赖完成后端和前端安装；
2. 从原始 `wendang/` 数据重建 manifest 和最小知识库；
3. 启动 API 并完成问答、检索和健康检查；
4. 构建前端生产包；
5. 将仓库复制到另一个绝对路径后重复上述流程；
6. 证明持久化产物和 API 业务响应不依赖开发机绝对路径；
7. 生成包含环境、代码、数据和检查结果的基线验收报告。

## 3. 非目标

本变更不包括：

- 补采官方来源 URL、附件 URL、发布日期或版本关系；
- 替换 hashing embedding、规则 reranker 或 LLM；
- 调整检索排序、拒答阈值或当前评测规则；
- 重做前端视觉和信息架构；
- 宣称历史 `300/300`、`60/60`、`50/50` 已在当前环境重新通过；
- 解决所有 `.doc`、复杂 PDF 或复杂表格解析问题；
- 引入 Docker、任务队列或云部署。

## 4. 运行时与依赖契约

### 4.1 支持矩阵

首个可复现基线只承诺以下组合：

| 组件 | 基线 |
| --- | --- |
| 操作系统 | Windows 10/11 x64 |
| Python | CPython 3.12.x |
| Node.js | Node.js 22.x LTS |
| npm | 随 Node.js 22 提供的 npm 10.x |
| 解析 profile | `portable`，禁止自动探测外部转换器 |

Python 3.10/3.11、Linux 和 macOS 可以继续尝试运行，但在产生独立验收证据前不属于本变更的受支持矩阵。后续扩展支持范围必须新增 change spec。

当前构建会通过 `PATH` 自动探测 `soffice/libreoffice`，导致安装了 LibreOffice 的机器与未安装的机器采用不同解析路径。实施时必须改为显式 parser profile：

- `portable`：本基线唯一允许的验收 profile；禁用外部转换器，`.xls` 使用 `xlrd`，`.doc` 使用现有兜底并记录 warning。
- `libreoffice`：后续可选 profile；必须显式配置可执行文件和版本，不能通过静默自动探测启用。

验收报告必须记录 parser profile 和外部工具版本。未经独立 change spec 验证，`libreoffice` profile 不得用于生成本次批准基线。

### 4.2 Python 依赖

- `pyproject.toml` 继续作为人工维护的直接依赖来源。
- 实施时新增 `requirements.lock.txt`，固定全部传递依赖和哈希。
- 锁文件必须由声明式输入生成，不得手工从某台已污染环境执行无筛选的 `pip freeze`。
- 安装命令必须使用隔离虚拟环境和 `pip install --require-hashes -r requirements.lock.txt`。
- 测试/维护工具与运行时依赖分离；若本变更新增 `pytest`、`httpx` 或锁文件生成工具，应记录在独立开发依赖声明中。
- CI 或验收脚本必须验证锁文件与 `pyproject.toml` 未漂移。

具体锁文件生成器属于实现选择；批准本 Spec 时需要在“未决事项”中确定。无论选择何种工具，安装端不得依赖该生成器。

### 4.3 Node 依赖

- `frontend/package-lock.json` 是前端锁文件，必须继续提交。
- 可复现安装统一使用 `npm ci`，不得在验收流程中使用 `npm install` 更新锁文件。
- 实施时新增 `.node-version`，内容固定到已验收的 Node 22 补丁版本。
- `package.json` 与 `package-lock.json` 不一致时，安装必须失败。

### 4.4 环境文件

- 实施时新增 `.python-version` 和 `.env.example`；`.env.example` 只能包含非敏感占位符和说明。
- API Key 继续只从环境变量读取，任何锁文件、报告和日志都不得包含密钥。
- 默认基线不得要求真实 LLM Key；无 Key 时必须走当前受控降级路径。

## 5. 持久化路径契约

### 5.1 规范表示

所有指向仓库内文件的持久化路径 MUST 使用相对于仓库根目录的 POSIX 风格引用：

```text
wendang/data/001_...xls
data/processed/text_chunks.jsonl
reports/retrieval_eval.json
```

以下位置不得写入盘符、UNC 前缀、用户目录或仓库绝对路径：

- manifest 和 enriched manifest；
- text chunks、text units、table cells、table rows 和向量索引；
- 知识库状态、构建状态、错误报告和评测报告；
- SQLite 中的 `local_path`、输入路径和报告路径字段；
- 面向前端的 API 业务响应。

外部官方 `source_url`、`attachment_url` 不属于本路径契约，它们必须继续保存完整 URL。

### 5.2 解析规则

实施时新增唯一的路径序列化/解析边界，所有模块复用该边界：

- `to_project_ref(path)`：确认目标位于项目根目录内，返回 POSIX 相对路径；越界时抛出结构化错误。
- `resolve_project_ref(ref)`：拒绝包含 `..` 的越界引用，将相对引用解析到当前项目根目录。
- API 需要展示来源时返回稳定相对引用；服务端访问文件前再解析为绝对路径。

不允许在各模块内重复使用 `str(path)`、`path.resolve()` 或字符串替换实现持久化路径策略。

### 5.3 旧产物兼容策略

- 旧绝对路径仅作为历史数据被识别，不自动猜测或重写盘符。
- 读取不存在的旧绝对路径时，命令必须明确报告 `legacy_absolute_path`，不得静默回退到同名文件。
- 正式迁移方式是从 `wendang/` 原始输入重新生成 manifest，并按依赖顺序重建下游产物。
- 历史报告先只读归档并标记原 Git 提交、路径和日期；新报告使用新的 run ID，不覆盖历史证据后冒充同一次运行。

## 6. 构建与运行设计

### 6.1 建议新增的交付文件

实施阶段预计新增或修改：

```text
.python-version
.node-version
.env.example
requirements.lock.txt
docs/RUNBOOK.md
scripts/bootstrap.ps1
scripts/verify_baseline.ps1
src/jinrong/path_refs.py
tests/test_path_refs.py
tests/test_api_smoke.py
tests/test_cli_smoke.py
```

实际文件列表可以在不改变本 Spec 契约的前提下缩减，但不得省略依赖锁、路径边界、自动验证和运行说明四类产物。

### 6.2 命令分层

验收流程分为两层：

**快速门禁**，用于每次提交：

```powershell
python -m compileall -q src
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
```

**发布门禁**，用于批准基线：

1. 在隔离目录创建全新 Python 虚拟环境；
2. 严格按锁文件安装 Python 依赖；
3. 使用 `npm ci` 安装前端依赖；
4. 在仓库的临时副本中重建 500 份文件的 manifest、知识库、元数据、文本单元、表格语义和索引；
5. 启动 API，检查 `/health`、`/ask`、`/search`、`/documents`、`/kb/status`；
6. 构建前端；
7. 将同一提交复制到第二个不同的绝对路径，重复最小构建和 API smoke；
8. 运行结构化路径审计和产物一致性比较。

发布门禁必须在临时副本或独立 worktree 中运行，避免覆盖开发者当前的 `data/processed` 和 `reports`。

### 6.3 路径审计

实施时提供一个可脚本化的结构化审计入口。审计必须：

- 只检查 schema 中声明为路径/文件引用的字段，避免把正文中的示例路径误报为缺陷；
- 检出 Windows 盘符、UNC、`/Users/`、`/home/` 和项目根绝对路径；
- 对越界相对路径、缺失文件引用和非法路径类型分别计数；
- 发现任一未允许问题时返回非零退出码；
- 输出 JSON 报告，供 CI 和最终验收引用。

## 7. 验收报告设计

每次发布门禁生成：

```text
reports/acceptance/<run-id>/baseline.json
```

`run-id` 格式为 UTC 时间加短 Git SHA。报告至少包含：

```json
{
  "schema_version": "1.0",
  "run_id": "20260806T120000Z-9d1c573",
  "git_sha": "9d1c573...",
  "dirty_worktree": false,
  "platform": "windows-x86_64",
  "python_version": "3.12.x",
  "node_version": "22.x",
  "parser_profile": "portable",
  "external_tools": {},
  "python_lock_sha256": "...",
  "node_lock_sha256": "...",
  "input_dataset_sha256": "...",
  "checks": [],
  "path_audit": {},
  "artifact_fingerprints": {},
  "started_at": "...",
  "finished_at": "...",
  "overall_status": "passed|failed"
}
```

`dirty_worktree=true` 的运行可以用于开发诊断，但不得作为批准基线的最终证据。

## 8. 验收场景

### AC-01：干净安装

Given 一台仅有受支持 Python、Node、npm 和 Git 的 Windows 环境  
When 按 `docs/RUNBOOK.md` 执行安装  
Then Python 严格锁定安装和 `npm ci` 均成功，且没有修改锁文件。

### AC-02：后端最小运行

Given 依赖已安装且原始数据存在  
When 执行编译、测试并启动 API  
Then `/health` 返回 200，代表性 `/ask`、`/search`、`/documents`、`/kb/status` 请求均返回符合当前 schema 的成功响应。

### AC-03：前端生产构建

Given 已执行 `npm ci`  
When 执行 `npm --prefix frontend run build`  
Then 构建退出码为 0，产物位于 `frontend/dist`，没有未处理的模块解析错误。

### AC-04：相对路径持久化

Given 从原始数据新建 manifest 和下游产物  
When 对所有声明的路径字段运行结构化审计  
Then 不存在机器绝对路径、越界引用或无法解析的仓库内引用。

### AC-05：换目录复跑

Given 同一 Git 提交和同一份原始数据位于两个不同绝对路径  
When 分别执行最小构建和 API smoke  
Then 两处均通过，API 不泄露各自根目录；核心确定性产物在排除明确声明的时间字段后内容一致。

### AC-06：全量重建

Given 发布门禁在独立副本中运行  
When 对 500 份原始文件完成全量构建  
Then manifest 文档数和成功处理文档数均为 500，`error_count=0`，允许的 `.doc` 兜底 warning 被结构化记录；任一构建错误均返回非零退出码，且原始 `wendang/` 的文件哈希保持不变。

### AC-07：失败可诊断

Given 锁文件漂移、依赖缺失、旧绝对路径或无效文件引用中的任一情况  
When 执行基线验证  
Then 命令返回非零退出码，报告包含稳定错误代码、失败阶段和可操作说明，不把部分成功标记为通过。

## 9. 确定性边界

以下核心产物在相同输入、代码和依赖下 SHOULD 字节稳定：

- `manifest.jsonl`；
- `text_chunks.jsonl`、`text_units.jsonl`；
- `table_cells.jsonl`、`table_rows.jsonl`；
- 向量索引内容。

构建时间、run ID、执行耗时和诊断栈属于允许变化字段。验收工具必须显式列出忽略字段，不得用“整体报告不同”代替差异分析。

## 10. 实施任务顺序

1. 批准本 change spec，并解决第 12 节未决事项。
2. 添加运行时版本声明和 Python 锁文件，验证全新虚拟环境安装。
3. 实现统一路径引用模块及其单元测试。
4. 将 manifest、知识库、索引、评测、审计、SQLite 和 API 逐步迁移到路径引用边界。
5. 增加结构化路径审计与 CLI/脚本入口。
6. 增加最小 API/CLI 测试和前端 `npm ci` 构建门禁。
7. 编写运行说明与自动基线验证脚本。
8. 在独立副本完成全量重建，再在第二绝对路径复跑。
9. 归档历史产物，生成首份 `baseline.json`，经审阅后将状态改为 `Verified`。

第 4 步必须按依赖链迁移，不允许只修 manifest 后继续让下游模块写绝对路径。

## 11. 失败与回滚

出现以下任一情况时，不得批准基线：

- 锁定安装不能在支持矩阵内完成；
- 新路径格式导致已有问答或检索无法访问原始文件；
- API schema 出现未声明的破坏性变化；
- 全量重建修改原始资料；
- 路径审计仍发现机器绝对路径；
- 验收报告缺少代码、依赖或输入指纹。

回滚时保留旧读取逻辑和历史报告为只读参考，撤销新产物的发布，不回写或删除原始 `wendang/`。若需要临时兼容旧绝对路径，必须使用显式开关并输出警告，且不能作为通过 AC-04/AC-05 的依据。

## 12. 未决事项

批准实施前必须确认：

1. Python 锁文件生成器采用 `pip-tools`、`uv` 还是其他支持哈希的工具；推荐以团队现有工具可用性和 CI 支持为准，安装端契约不变。
2. 发布门禁是使用独立 worktree、临时复制目录还是 CI 新 checkout；必须保证不覆盖当前工作区产物。
3. 历史报告归档位置及是否继续提交大型生成产物。
4. “核心确定性产物”的完整清单，以及每类报告允许变化的字段。
5. 首个基线是否只支持 Windows，还是在同一变更中增加 Linux 验收；默认按本 Spec 的 Windows-only 基线执行。

### 12.1 已批准的实施决策

1. 使用 `uv 0.8.13` 从 `pyproject.toml` 生成带哈希的 Python 运行时与开发锁文件。
2. 本地发布门禁使用临时仓库副本；后续 CI 使用全新 checkout。
3. 历史产物由 Git 历史保留，不额外复制大型归档；新验收报告使用独立 run ID。
4. manifest、文本/表格结构产物和向量索引属于核心确定性产物；报告仅允许时间、run ID、耗时和诊断栈变化。
5. 首个基线只验收 Windows 10/11 x64；Linux 支持另立 change spec。

## 13. 批准条件

本 Spec 只有在以下内容被评审确认后才可从 `Proposed` 改为 `Approved`：

- 支持矩阵和锁文件策略；
- 相对路径字段格式和旧产物迁移规则；
- 发布门禁的隔离方式；
- AC-01 至 AC-07 的可执行性；
- 不会覆盖现有用户改动或原始比赛资料。
