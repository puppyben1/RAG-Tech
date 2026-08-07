# Traceability

| Requirement | Contract | Source | Test/acceptance |
| --- | --- | --- | --- |
| COMP-001 | DATA_CONTRACTS manifest and artifact records | `src/jinrong/manifest.py`, `knowledge_base.py` | AC-REPRO-01, path audit |
| COMP-002 | Manifest record | `src/jinrong/manifest.py`, `path_refs.py` | `tests/test_path_refs.py`, AC-DATA-01 |
| COMP-003 | Search response and evidence records | `src/jinrong/services.py` | `tests/test_api_smoke.py`, AC-API-02 |
| COMP-004 | Answer semantics | `src/jinrong/ask.py`, `eval_trusted.py` | trusted evaluation endpoints, AC-EVAL-01 |
| COMP-005 | API endpoint table | `src/jinrong/api/routes.py` | `tests/test_api_smoke.py`, AC-API-02 |
| COMP-006 | Nullable source/version metadata and source proof | `metadata_extractor.py`, `source_catalog.py`, `source_proof.py` | `tests/test_source_proof.py`; batch proof report |
| COMP-007 | Acceptance quality targets | `ACCEPTANCE.md`, `eval_holdout.py` | `tests/test_eval_holdout.py`; independent reviewed holdout required |
| COMP-008 | Reproducibility and path policy | `path_refs.py`, `path_audit.py` | P0-A relocation and artifact fingerprint run |
| COMP-001/003/004/005/006/007/008 | Windows-native competition delivery sequence | `changes/CR-20260807-windows-competition-delivery.md` | S0-S4 gates defined by the change spec |
| COMP-006/007 | Authority gate and evaluation freshness | `governance.py`, `eval_provenance.py` | `tests/test_eval_provenance.py`; W1-W3 in `changes/CR-20260807-windows-competition-delivery.md` |
