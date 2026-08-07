# CR-20260806: Explicit Source Approval Command

Status: Verified  
Priority: P0-C data  
Created: 2026-08-06

## Goal

Provide a controlled handoff from researched candidate metadata to an approved catalog without silently signing rows.

## Behavior

`approve-source-catalog` requires a named reviewer, an ISO-8601 timestamp, and one or more explicit `doc_id` values. It writes a new CSV/JSONL output, never overwrites the candidate, stamps only selected rows, and reruns full catalog validation before reporting success. Invalid output raises an error and cannot proceed to enrichment/import.

## Verification

The full test suite passes, including selected-row stamping, missing reviewer rejection, and post-stamp validation.

