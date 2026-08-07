# CR-20260806: Source and Version Trust Governance

Status: Verified  
Priority: P0-C  
Created: 2026-08-06

## Goal

Make source and version authority decisions explicit and deterministic before later retrieval or model work.

## Implemented scope

- Added `TRUST_POLICY.md` with version states, source requirements, relation rules, and refusal behavior.
- Added `src/jinrong/governance.py` for normalized status, evidence authority, and relation audits.
- Applied the authority gate to open RAG answers.
- Added governance fields to the existing version audit report.
- Added focused tests for source/version eligibility and invalid relations.

## Explicit non-goals

No URL guessing, web crawling, bulk metadata backfill, embedding change, reranker change, or frontend work.

## Verification

`.venv\\Scripts\\python.exe -m pytest -q` -> 18 passed (one existing httpx deprecation warning).

The current dataset remains non-authoritative where source URLs and confirmed version states are absent. This is an expected P0-C gap, not a passing quality result.

