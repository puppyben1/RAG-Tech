# Source Review Runbook

Use a clean branch or isolated repository copy. Do not edit `wendang/data` and do not overwrite historical reports when preparing a review batch.

1. Rebuild metadata and generate a fresh worklist with `python -m jinrong.cli source-gap-worklist --output data/intermediate/source_gap_worklist_review.csv`.
2. Review the highest-priority rows first. Confirm `doc_id` and `sha256`, then enter real source/attachment URLs, proof evidence, proof method, version state, and effective dates. Statistical snapshots use `not_applicable` and must retain `period`.
3. Run `python -m jinrong.cli verify-source-catalog --source-catalog data/intermediate/source_catalog_batch_01_candidate.jsonl --raw-root D:\Bisai\RAG-Tech\wendang --output data/intermediate/source_catalog_batch_01_proof.json --verified-catalog-output data/intermediate/source_catalog_batch_01_verified.jsonl`. Verification is read-only against source inputs and records official-domain, page metadata, optional `version_evidence_url`, attachment, and SHA-256 checks. The verified catalog is written only when every row passes.
4. Rows with `needs_review` require a real version/proof decision. If the proof is manual, use `approve-source-catalog` with a named reviewer and timestamp to stamp only those rows into a new file. Automated proof records do not invent reviewer fields.
5. Validate the approved output again, then run `python -m jinrong.cli enrich-manifest --source-catalog data/intermediate/source_catalog_batch_01_approved.jsonl` and rebuild document metadata.
6. Run version audit, path audit, tests, and the trusted evaluation. Review all authority/refusal changes before accepting the batch.

Never use placeholder URLs, inferred version states without evidence, or a reviewer name shared by automation. Keep incomplete rows as `unknown`; they remain searchable but are not authoritative.
