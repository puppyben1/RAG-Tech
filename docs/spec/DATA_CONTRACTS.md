# Data Contracts

All persisted repository file references use POSIX-style project references such as `wendang/data/file.pdf` or `data/processed/text_units.jsonl`. `null` means the field is known to be absent or not extracted. An empty list means the collection was processed successfully and contains no items. `unknown` is a deliberate metadata value when the system cannot establish a status.

## Manifest record

Required: `doc_id`, `title`, `file_name`, `local_path`, `file_ext`, `file_size`, `sha256`, `source_type`. Optional nullable metadata: `period`, `source_url`, `attachment_url`, `column`. `source_type` is `excel`, `word`, or `pdf`.

## Text chunk and text unit

Both contain `doc_id`, `source_type`, `source_title`, `file_name`, `local_path`, text, and a stable ID (`chunk_id` or `unit_id`). Text units may additionally contain `page_no`, `section_path`, `article_no`, `chunk_id`, `chunk_index`, and `unit_index`; unavailable positions remain `null`.

## Table cell and table row

Table records contain `doc_id`, `source_title`, `local_path`, sheet/row identity, textual representation, and extracted values. Rows may contain `row_id`, `sheet_name`, `row_index`, `row_header`, `cell_refs`, `headers`, `periods`, `indicator`, `unit`, `values`, and `cells`. Missing extraction is `null` or an empty list, never a fabricated value.

## Vector index

The current index is a deterministic local hashed-vector index. Its entries identify the source text unit or table row and store the vector payload and index metadata. It is an implementation detail; clients must use `/search` and must not depend on the embedding algorithm.

## Source catalog

A catalog row is matched by `doc_id`, `sha256`, `file_name`, or normalized title. Authority claims use `source_url`, `attachment_url`, `version_status`, and optional version relations. `version_evidence_url` may identify a separate official page that contains the effective-date clause. Confirmed source or version values require source/version evidence and a proof record; a named reviewer and timestamp are required only when the proof method is manual. `not_applicable` additionally requires `period`. Invalid URLs, unsupported states, insufficient proof, or duplicate stable identities block enrichment and database import.

## Independent holdout

A holdout row contains `id`, `type`, `question`, boolean `answerable`, `expected_route`, and one of the six governed categories. Answerable rows also contain non-empty `expected_doc_ids`, `expected_evidence_type` or `expected_evidence_types`, `must_contain`, and `gold_evidence`. Multi-hop rows list every required evidence type. Each expected document has a gold locator using `page_no`, `article_no`, or `sheet_name` plus `cell_ref`. Threshold and table cases additionally contain `critical_entities`; refusal rows contain `refusal_reason`.

Final review adds `review_status: reviewed`, `reviewed_by`, and timezone-qualified `reviewed_at` without changing the gold fields. The freeze requires five distinct questions per category, no dev/holdout overlap, complete gold, and valid review metadata. The final acceptance command binds the evaluated JSONL to the manifest SHA-256.

## Legacy QA migration candidate

`migrate-qa-data` converts the legacy MCQ workbook into a review candidate without modifying the workbook. Each row preserves the original question, options, answer, evidence, source title, and file label, and adds `migration_status`, `doc_id`, `expected_doc_ids`, `expected_evidence_type`, `gold_evidence`, project-relative `local_path`, nullable `source_url`, tags, and candidate document IDs.

`ready_candidate` means only that document identity and the legacy Excel cell locator were parsed deterministically. It is not an approved gold label or an independent holdout result. Rows with `document_matched_locator_missing`, `ambiguous_document`, or `unresolved_document` remain fail-closed in the CSV review worklist. No migration output may enter the frozen holdout or final acceptance flow until it satisfies the independent holdout contract and receives the required external review metadata.

## Path and compatibility policy

New artifacts MUST use project references. A legacy absolute path is read-only historical data and is reported as `legacy_absolute_path`; it is not silently rewritten or resolved by basename.
