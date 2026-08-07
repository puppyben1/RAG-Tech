# CR-20260806: Source Review Batch 01

Status: Proposed  
Priority: P0-C data  
Created: 2026-08-06

## Scope

Candidate metadata for `nfra_397`, `nfra_398`, `nfra_390`, and `nfra_389`, selected from the highest-priority trusted/retrieval evaluation references.

## Evidence

See `docs/research/source-review-batch-01.md`. Each local file was matched byte-for-byte to a first-party official attachment. The candidate catalog is `data/intermediate/source_catalog_batch_01_candidate.jsonl`.

## Approval gate

The candidate intentionally leaves `reviewed_by` and `reviewed_at` empty. It MUST fail source catalog validation and MUST NOT be enriched or imported until a named human reviewer checks the cited pages, confirms the version interpretation, and signs those fields.

Special review attention is required for the format variants `nfra_397/398` and the staged effective dates in `nfra_389`.

