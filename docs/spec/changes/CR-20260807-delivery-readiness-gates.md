# CR-20260807 Delivery Readiness Gates

Status: Approved and implementing

Approval basis: the user approved continuing the remaining competition-delivery plan on 2026-08-07. This change does not authorize fabricated source metadata, reviewer identities, holdout gold answers, or compliance decisions.

Related requirements: COMP-001, COMP-006, COMP-007, COMP-008

## Problem

The reproducible Windows build and primary demo flows are working, but four delivery claims remain weaker than the competition scope:

1. all 32 legacy `.doc` files use the portable binary fallback, so extraction success does not prove content fidelity;
2. the supplied public corpus has not been scanned for accidentally included customer, account, or transaction identifiers;
3. only 4 of 500 documents have machine-proven source and version metadata;
4. the competition brief requires acceptable latency but does not publish a numeric platform threshold.

The current reports expose parts of these gaps but do not combine them into a fail-closed competition-readiness decision.

## Requirements

- DOC-01: audit every `.doc` manifest record against build state and extracted chunks.
- DOC-02: fail the machine gate for failed, empty, very short, or corrupted extraction.
- DOC-03: when binary fallback was used, require a separately saved review worksheet bound to source and extracted-text hashes. Code must not approve its own output.
- PRIV-01: scan text units and table cells for high-confidence identity/contact/account patterns.
- PRIV-02: never persist a matched sensitive value or surrounding text in the scan report; persist only location, rule, length, and a run-scoped digest.
- PRIV-03: unresolved candidates block compliance readiness. Confirmed sensitive data always blocks readiness.
- LAT-01: final acceptance must include an explicit positive P95 threshold supplied by the competition platform or deployment owner.
- LAT-02: an absent threshold is `unverified`, never a final pass.
- READY-01: produce a single readiness report with separate reproducibility, source/version, `.doc`, privacy, holdout, final-score, and latency gates.
- READY-02: no local gate may hide another blocked or unverified gate.

## Non-goals

- Do not install LibreOffice, Docling, BGE, or BCEmbedding as part of this change.
- Do not infer source URLs or version status from filenames.
- Do not author or approve the independent holdout.
- Do not rewrite historical generated JSON/JSONL paths.

## Acceptance

- Unit tests cover fail-closed `.doc`, privacy, latency, and readiness behavior.
- Commands run natively under Windows PowerShell and accept an isolated project root through explicit paths or `JINRONG_PROJECT_ROOT`.
- Current evidence produces a truthful blocked report with exact remaining reasons rather than a passing competition claim.

