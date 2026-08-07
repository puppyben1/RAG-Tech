# W4-W6 Results

Date: 2026-08-07

## W4

`freeze-eval` now writes normalized frozen JSONL copies and a manifest containing input and output SHA-256 fingerprints, question fingerprints, overlap counts, sample coverage, gold completeness, and gate reasons. The current six-case seed has zero question overlap and one case in each required category, but it is below the five-per-category acceptance minimum. Its gate is intentionally `blocked` because sample size, gold data, and external review are incomplete.

`approve-eval-holdout` provides the auditable handoff to a real non-implementation reviewer. It writes a separate file, requires explicit case IDs, reviewer identity, a timezone-qualified timestamp, and complete answer/evidence gold fields; it does not generate or alter gold answers.

This is a diagnostic freeze, not a final competition acceptance set. A separate 30-slot review worksheet now captures the minimum sample structure. `eval-acceptance` will run only against a ready manifest with a matching dataset hash and will report the five governed quality metrics plus latency.

## W5

`eval-retrieval-ab` ran against the isolated W3 knowledge base using five explicitly labeled diagnostic cases:

- BM25: top1/top3/topk = 1.0; P50 736.08 ms; P95 1777.98 ms.
- Local hybrid: top1/top3/topk = 1.0; P50 1037.45 ms; P95 1895.14 ms.
- Delta: accuracy 0; hybrid P95 +117.16 ms.

Decision: keep BM25 as the default. The report status is `diagnostic_only` because the holdout gate is blocked.

## W6

The React workbench includes five offline demo chains: policy fact, threshold, Excel lookup, cross-file judgement, and refusal/version conflict. Each evidence card displays answer evidence text, title, source link, version status, and page/article or `sheet!cell` location. Desktop and 390x844 mobile browser smoke checks passed; production build passed.

## Remaining gate

The final competition acceptance run is still pending. It requires a sufficiently covered independent holdout with a ready gate and a reproducible end-to-end report. No historical 50/50 or 60/60 report is used as the final score.
