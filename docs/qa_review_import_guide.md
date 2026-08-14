# QA 复核结果导入指南

## 命令功能

`import-qa-reviews` 命令用于导入人工复核的 QA 迁移结果，校验填写内容的正确性，并生成可用于后续评估的 JSONL 文件。

## 使用方法

```bash
jinrong import-qa-reviews \
  --review-csv data/intermediate/qa_migration_review.csv \
  --candidates data/intermediate/qa_migration_candidates.jsonl \
  --output data/intermediate/qa_migration_reviewed.jsonl
```

### 参数说明

- `--review-csv`: 人工填写完成的复核 CSV 文件路径
- `--candidates`: 原始候选 JSONL（由 `migrate-qa-data` 生成）
- `--output`: 输出的已复核 JSONL 文件路径
- `--manifest`: （可选）Manifest JSONL 路径，默认使用 `data/processed/manifest.jsonl`

## 复核 CSV 填写规则

### 必填字段

根据 `source_type` 不同，必填字段要求如下：

#### Excel 文档
- `selected_doc_id`: 从候选中选择的 doc_id
- `sheet_name`: 工作表名称（精确匹配）
- `cell_ref`: 单元格引用（如 "C5"）

#### Word 文档
- `selected_doc_id`: 从候选中选择的 doc_id
- `article_no` 或 `page_no`: 至少填写一项
  - `article_no`: 条款号（如"第十二条"）
  - `page_no`: 页码（整数）

#### PDF 文档
- `selected_doc_id`: 从候选中选择的 doc_id
- `page_no`: PDF 页码（整数，从 1 开始）

### 可选字段

- `review_notes`: 复核备注，记录人工确认的依据或上下文

## 校验规则

命令会执行以下校验：

### 1. 文档 ID 校验
- `selected_doc_id` 必须存在于 manifest 中
- 或者存在于原始 candidates 的候选列表中

### 2. 定位符完整性校验
- Excel: 必须同时有 `sheet_name` 和 `cell_ref`
- Word: 必须有 `article_no` 或 `page_no` 之一
- PDF: 必须有 `page_no`

### 3. 文件存在性校验
- 校验 `wendang/data/` 下对应文件存在

### 4. 定位符有效性校验

#### Excel 校验
- 工作表名称在文件中存在（支持大小写不敏感匹配）
- 单元格引用格式正确（如 A1, AB123）
- 单元格在工作表中可访问

#### PDF 校验
- 页码为正整数
- 页码不超过 PDF 实际页数
- 证据覆盖度：该页文本应包含证据原文；若不包含，则证据字符二元组在该页文本中的覆盖度须不低于 0.5（QA 数据中的证据常为原文改写，因此采用模糊覆盖校验，保持 fail-closed）

#### Word 校验
- 仅校验文件存在性（条款号校验成本高，信任人工复核）

## 输出结果

### 成功输出 (status: "passed")

```json
{
  "status": "passed",
  "review_csv": "data/intermediate/qa_migration_review.csv",
  "candidate_jsonl": "data/intermediate/qa_migration_candidates.jsonl",
  "output_jsonl": "data/intermediate/qa_migration_reviewed.jsonl",
  "total_reviews": 200,
  "passed": 195,
  "failed": 5,
  "not_reviewed": 5,
  "validation_errors": 0,
  "errors": null,
  "failed_items": null
}
```

### 失败输出 (status: "validation_failed")

```json
{
  "status": "validation_failed",
  "total_reviews": 200,
  "passed": 190,
  "failed": 10,
  "not_reviewed": 3,
  "validation_errors": 7,
  "errors": [
    {
      "id": "Q123",
      "error": "invalid_doc_id",
      "selected_doc_id": "nfra_999",
      "message": "selected_doc_id 'nfra_999' not in manifest and not in candidates"
    },
    {
      "id": "Q456",
      "error": "missing_locators",
      "source_type": "pdf",
      "errors": ["PDF requires page_no"]
    }
  ],
  "failed_items": [...]
}
```

命令在 `validation_errors > 0` 时返回退出码 1。

## 失败原因分类

### `not_reviewed`
- CSV 中 `selected_doc_id` 为空
- 该条目未完成人工复核

### `invalid_doc_id`
- `selected_doc_id` 不在 manifest 中
- 也不在原始 candidates 候选列表中

### `doc_id_not_in_manifest`
- `selected_doc_id` 在 candidates 中，但不在 manifest 中
- 可能是 manifest 未更新或文件缺失

### `missing_locators`
- 缺少必要的定位字段
- 如 PDF 缺 `page_no`，Excel 缺 `sheet_name` 或 `cell_ref`

### `file_not_found`
- `wendang/data/` 下找不到对应文件

### `locator_validation_failed`
- 定位符格式或内容不合法
- 如页码超出范围、工作表不存在、单元格引用错误

## 输出 JSONL 格式

成功通过校验的条目会被写入输出 JSONL，每条记录包含：

```json
{
  "id": "Q101",
  "migration_status": "reviewed_and_ready",
  "source_type": "word",
  "question": "...",
  "answer": "A",
  "doc_id": "nfra_396",
  "selected_doc_id": "nfra_396",
  "expected_doc_ids": ["nfra_396"],
  "gold_evidence": [
    {
      "doc_id": "nfra_396",
      "article_no": "第二条"
    }
  ],
  "local_path": "wendang/data/396_消费金融公司管理办法_消费金融公司管理办法.doc",
  "review_notes": "原文核对一致，定义条款",
  ...
}
```

关键字段：
- `migration_status`: 更新为 `"reviewed_and_ready"`
- `selected_doc_id`: 人工选定的文档 ID
- `gold_evidence`: 标准证据定位，包含 `doc_id` 和定位符
- `review_notes`: 人工复核备注

## 典型工作流

### 1. 生成复核清单

```bash
jinrong migrate-qa-data \
  --qa data/raw/QA数据.xlsx \
  --output data/intermediate/qa_migration_candidates.jsonl \
  --review-worklist data/intermediate/qa_migration_review.csv
```

### 2. 人工复核

打开 `qa_migration_review.csv`，按批次填写：
- **第一批（155条）**: 唯一匹配但缺定位
- **第二批（29条）**: 文档歧义
- **第三批（16条）**: 未解析 PDF

每批建议 25-40 条为一组，双人复核更稳妥。

### 3. 导入复核结果

```bash
jinrong import-qa-reviews \
  --review-csv data/intermediate/qa_migration_review.csv \
  --candidates data/intermediate/qa_migration_candidates.jsonl \
  --output data/intermediate/qa_migration_reviewed.jsonl
```

### 4. 检查校验报告

- 若 `status: "passed"` 且 `validation_errors: 0`，继续后续流程
- 若有 validation_errors，根据 `errors` 列表修正 CSV 后重新导入

### 5. 合并到评估集

将 `qa_migration_reviewed.jsonl` 与其他已通过的 QA 条目合并，用于完整测试和数据审计。

## 注意事项

1. **不覆盖原始文件**: 输出路径必须与候选 JSONL 不同
2. **Fail-closed 设计**: 只有完全通过校验的条目才会进入输出 JSONL
3. **批量处理**: 可多次运行，每次处理一部分复核完成的条目
4. **Excel 工作表名**: 支持大小写不敏感和空格差异的模糊匹配
5. **PDF 页码**: 必须是 PDF 文件的实际页码（从 1 开始），不是文档内标注页码

## 示例

### 示例 CSV（部分）

```csv
id,migration_status,source_type,source_title,file_label,candidate_doc_ids,candidate_file_names,original_evidence,selected_doc_id,page_no,article_no,sheet_name,cell_ref,review_notes
Q101,document_matched_locator_missing,word,消费金融公司管理办法,消费金融公司管理办法.doc,nfra_396,396_消费金融公司管理办法_消费金融公司管理办法.doc,消费金融公司是经...,nfra_396,,第二条,,,原文核对一致
Q201,document_matched_locator_missing,pdf,寿险合同负债评估折现率曲线,附件1.pdf,nfra_460,460_附件1.pdf,折现率曲线由...,nfra_460,2,,,,在第2页找到说明
```

### 测试命令

```bash
# 创建测试样本（2条）
cat > data/intermediate/qa_review_test.csv << 'EOF'
id,migration_status,source_type,source_title,file_label,candidate_doc_ids,candidate_file_names,original_evidence,selected_doc_id,page_no,article_no,sheet_name,cell_ref,review_notes
Q101,document_matched_locator_missing,word,消费金融公司管理办法,消费金融公司管理办法.doc,nfra_396,396_消费金融公司管理办法_消费金融公司管理办法.doc,消费金融公司是经...,nfra_396,,第二条,,,原文核对一致
Q201,document_matched_locator_missing,pdf,寿险合同负债评估折现率曲线,附件1.pdf,nfra_460,460_附件1.pdf,折现率曲线由...,nfra_460,2,,,,在第2页找到
EOF

# 运行导入
jinrong import-qa-reviews \
  --review-csv data/intermediate/qa_review_test.csv \
  --candidates data/intermediate/qa_migration_candidates.jsonl \
  --output data/intermediate/qa_review_test_output.jsonl

# 检查输出
cat data/intermediate/qa_review_test_output.jsonl | jq '.migration_status'
```

## 后续工作

导入完成后，建议执行：

1. **数据审计**
   ```bash
   jinrong qa-data-audit \
     --qa data/intermediate/qa_migration_reviewed.jsonl \
     --manifest data/processed/manifest.jsonl
   ```

2. **完整测试**
   ```bash
   jinrong eval-trusted \
     --eval-path data/intermediate/qa_migration_reviewed.jsonl
   ```

3. **路径审计**
   ```bash
   jinrong path-audit \
     --root data/intermediate/qa_migration_reviewed.jsonl \
     --output reports/qa_reviewed_path_audit.json
   ```
