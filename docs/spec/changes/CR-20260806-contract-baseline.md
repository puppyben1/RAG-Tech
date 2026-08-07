# CR-20260806: Contract Baseline

Status: Verified  
Priority: P0-B  
Created: 2026-08-06

## Goal

Establish one source of truth for competition requirements, persisted data, API behavior, acceptance checks, and traceability, based on the current implementation after P0-A.

## Non-goals

No retrieval algorithm changes, source URL backfill, version governance, embedding/reranker replacement, or frontend redesign.

## Acceptance

The five contract documents exist, every public endpoint and core artifact has a documented shape, null/empty/unknown/error/refusal semantics are explicit, and automated tests cover request validation and the key API response envelope. Unmet competition requirements remain labeled `gap` or `unverified`.

## Change record

- Added `REQUIREMENTS.md`, `DATA_CONTRACTS.md`, `API_CONTRACTS.md`, `ACCEPTANCE.md`, and `TRACEABILITY.md`.
- Added contract tests without changing production behavior.

## Verification

`\.venv\Scripts\python.exe -m pytest -q` -> 14 passed (one dependency deprecation warning).
