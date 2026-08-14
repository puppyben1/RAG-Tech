# QA 复核结果导入命令

## 功能概述

`import-qa-reviews` 命令用于导入人工复核的 QA 迁移结果，执行严格的校验，并生成可用于后续评估的标准化 JSONL 文件。

## 快速开始

```bash
jinrong import-qa-reviews \
  --review-csv data/intermediate/qa_migration_review.csv \
  --candidates data/intermediate/qa_migration_candidates.jsonl \
  --output data/intermediate/qa_migration_reviewed.jsonl
```

## 校验机制

命令执行以下校验（fail-closed 设计）：

1. **文档 ID 校验**: `selected_doc_id` 必须在 manifest 或 candidates 中存在
2. **定位符完整性**:
   - Excel: 必须有 `sheet_name` + `cell_ref`
   - Word: 必须有 `article_no` 或 `page_no`
   - PDF: 必须有 `page_no`
3. **文件存在性**: 校验 `wendang/data/` 下文件存在
4. **定位符有效性**:
   - Excel: 工作表存在、单元格可访问
   - PDF: 页码在有效范围内，且该页文本覆盖证据（原文包含或字符二元组覆盖度≥50%）
   - Word: 文件存在即可（信任人工复核；docx 会校验条号/标题存在于正文）

## 输出说明

### 成功 (status: "passed")

只有完全通过校验的条目进入输出 JSONL：
- `migration_status` 更新为 `"reviewed_and_ready"`
- `gold_evidence` 包含标准化的文档定位信息
- 保留 `review_notes` 人工备注

### 失败 (status: "validation_failed")

命令返回退出码 1，输出详细错误列表：
- `not_reviewed`: 未填写 `selected_doc_id`
- `invalid_doc_id`: doc_id 不存在
- `missing_locators`: 缺少必要定位字段
- `file_not_found`: 文件不存在
- `locator_validation_failed`: 定位符无效

## CSV 填写规则

### Excel 示例
```csv
Q001,ready,excel,...,nfra_145,...,nfra_145,,"人身保险公司（月度）  ",C5,已确认单元格值
```

### Word 示例
```csv
Q101,ready,word,...,nfra_396,...,nfra_396,,第二条,,,原文核对一致
```

### PDF 示例
```csv
Q201,ready,pdf,...,nfra_460,...,nfra_460,2,,,,在第2页找到说明
```

## 典型工作流

```bash
# 1. 生成复核清单
jinrong migrate-qa-data \
  --qa data/raw/QA数据.xlsx \
  --output data/intermediate/qa_migration_candidates.jsonl \
  --review-worklist data/intermediate/qa_migration_review.csv

# 2. 人工填写 CSV（按三个批次：唯一匹配、文档歧义、未解析）

# 3. 导入并校验
jinrong import-qa-reviews \
  --review-csv data/intermediate/qa_migration_review.csv \
  --candidates data/intermediate/qa_migration_candidates.jsonl \
  --output data/intermediate/qa_migration_reviewed.jsonl

# 4. 检查结果
echo $?  # 0 表示成功，1 表示有校验错误
```

## 注意事项

- **不覆盖原始文件**: 输出路径必须与 candidates 不同
- **可增量导入**: 可多次运行，每次处理一部分已复核条目
- **Excel 工作表名**: 支持大小写不敏感匹配
- **PDF 页码**: 使用实际 PDF 页码（从 1 开始），不是文档内标注页码

## 详细文档

完整使用指南和示例见 [docs/qa_review_import_guide.md](./qa_review_import_guide.md)
