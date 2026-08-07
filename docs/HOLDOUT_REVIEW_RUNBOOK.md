# Independent Holdout Review Runbook

This review is an engineering acceptance control defined by the project change specification, not a claim that the competition brief requires a handwritten approval.

## Reviewer

Use a person who did not implement or tune the retrieval and answer rules. The reviewer must inspect the holdout without using the system's current answer as the gold answer.

For every case, confirm:

- the question is clear and belongs to the declared category;
- `answerable` and `expected_route` are correct;
- each `expected_doc_ids` entry is supported by the original document;
- `must_contain` captures the minimum answer claims without copying the system output;
- threshold and table cases list key numbers, dates, organizations, or document numbers in `critical_entities`;
- `gold_evidence` has one entry per expected document with `page_no`, `article_no`, or both `sheet_name` and `cell_ref`;
- refusal cases are genuinely absent, under-specified, or unsupported;
- no dev question is a paraphrase of a holdout question.

Record disagreements outside the frozen output, correct the pending input in a new candidate file, and repeat the review. Do not tune code against holdout failures.

## Approval Command

Use `data/eval/review/trusted_eval_holdout_candidate.jsonl` as the review worksheet. It contains 30 empty slots, five for each required category. It deliberately contains no questions, answers, locators, reviewer identity, or timestamp. The reviewer authors those values from the original documents; the vague six-question seed in `data/eval/frozen` must not be approved as-is.

After all cases have been completed and checked, the reviewer runs:

```powershell
$env:PYTHONPATH = "src"
$holdout = "data/eval/review/trusted_eval_holdout_candidate.jsonl"
$caseIds = Get-Content -Encoding utf8 $holdout | ForEach-Object { ($_ | ConvertFrom-Json).id }
$approvalArgs = @(
  "approve-eval-holdout", "--holdout", $holdout,
  "--output", "data/eval/frozen/trusted_eval_holdout.reviewed.jsonl",
  "--reviewer", "REAL_REVIEWER_ID",
  "--reviewed-at", "2026-08-07T12:00:00+08:00"
)
foreach ($caseId in $caseIds) { $approvalArgs += @("--case-id", $caseId) }
.\.venv\Scripts\python.exe -m jinrong.cli @approvalArgs
```

`REAL_REVIEWER_ID` and the timestamp must be supplied by the actual reviewer. The command refuses in-place changes and writes a new JSONL file.

Freeze the approved copy into a new directory:

```powershell
.\.venv\Scripts\python.exe -m jinrong.cli freeze-eval `
  --dev data/eval/frozen/trusted_eval_dev.jsonl `
  --holdout data/eval/frozen/trusted_eval_holdout.reviewed.jsonl `
  --output-dir data/eval/accepted `
  --source-label independent_external_review
```

Proceed to the final acceptance run only when `data/eval/accepted/freeze_manifest.json` reports `gate: ready_for_evaluation`. A partial review, missing reviewer identity, or timestamp without a timezone remains blocked.

The freeze manifest also reports category counts, `gold_issue_count`, and `gold_issue_sample`. Fewer than five cases in any category, or any missing answer key, expected document, evidence type, evidence locator, critical entity, or refusal reason keeps the gate blocked.

Run the final metrics only after the gate is ready:

```powershell
.\.venv\Scripts\python.exe -m jinrong.cli eval-acceptance `
  --eval-path data/eval/frozen/trusted_eval_holdout.reviewed.jsonl `
  --holdout-manifest data/eval/accepted/freeze_manifest.json `
  --output reports/acceptance/final/trusted_holdout.json
```

The command rejects a blocked gate or a dataset SHA-256 mismatch. It reports institutional fact accuracy, table lookup accuracy, citation hit rate, critical-entity error rate, refusal success rate, and end-to-end latency. A non-passing metric returns a non-zero exit code.
