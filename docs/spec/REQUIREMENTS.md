# Requirements Baseline

This document is the current, testable interpretation of the competition brief. It describes the implemented MVP and records unmet requirements as gaps; it does not claim historical reports are current acceptance evidence.

| ID | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| COMP-001 | Ingest heterogeneous Word, PDF, and Excel source files | implemented | `src/jinrong/manifest.py`, `src/jinrong/knowledge_base.py` |
| COMP-002 | Preserve document identity, title, file type, hash, and local project reference | implemented | `docs/spec/DATA_CONTRACTS.md` |
| COMP-003 | Retrieve text and table evidence with document and position metadata | implemented | `/search`, text/table JSONL contracts |
| COMP-004 | Answer open questions, MCQ, table lookup/calculation, refusal, compliance, and multi-hop cases | implemented | `/ask`, `src/jinrong/ask.py` |
| COMP-005 | Expose runnable service and evaluation interfaces | implemented | `docs/spec/API_CONTRACTS.md` |
| COMP-006 | Provide source URL, attachment URL, and version lineage for every source | gap | source catalog and metadata reports show missing values |
| COMP-007 | Meet competition accuracy, citation, refusal, and latency targets on independent holdout data | unverified | requires a separately governed acceptance run |
| COMP-008 | Provide reproducible build and relocation-safe artifacts | verified by P0-A run | `CR-20260806-reproducible-baseline.md` |

## Scope

The baseline covers the checked-in Python API, JSONL artifacts, SQLite import, CLI, and trusted evaluation read-only endpoints. It excludes new embedding models, rerankers, source collection, and frontend redesign.

