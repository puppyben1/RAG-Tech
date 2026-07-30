from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "wendang" / "data"
WENDANG_DIR = PROJECT_ROOT / "wendang"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
INTERMEDIATE_DIR = PROJECT_ROOT / "data" / "intermediate"
REPORTS_DIR = PROJECT_ROOT / "reports"
INDEX_DIR = PROJECT_ROOT / "data" / "index"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
DB_DIR = PROJECT_ROOT / "data" / "db"

MANIFEST_PATH = PROCESSED_DIR / "manifest.jsonl"
MANIFEST_ENRICHED_PATH = PROCESSED_DIR / "manifest_enriched.jsonl"
TEXT_CHUNKS_PATH = PROCESSED_DIR / "text_chunks.jsonl"
TABLE_CELLS_PATH = PROCESSED_DIR / "table_cells.jsonl"
TABLE_ROWS_PATH = PROCESSED_DIR / "table_rows.jsonl"
DOCUMENT_METADATA_PATH = PROCESSED_DIR / "document_metadata.jsonl"
TEXT_UNITS_PATH = PROCESSED_DIR / "text_units.jsonl"
METADATA_EXTRACTION_REPORT = REPORTS_DIR / "metadata_extraction_report.json"
METADATA_QUALITY_REPORT = REPORTS_DIR / "metadata_quality_report.json"
VERSION_AUDIT_REPORT = REPORTS_DIR / "version_audit_report.json"
SOURCE_CATALOG_TEMPLATE_PATH = INTERMEDIATE_DIR / "source_catalog_template.csv"
SOURCE_GAP_WORKLIST_PATH = INTERMEDIATE_DIR / "source_gap_worklist.csv"
SOURCE_GAP_WORKLIST_REPORT = REPORTS_DIR / "source_gap_worklist_report.json"
SOURCE_ENRICHMENT_REPORT = REPORTS_DIR / "source_enrichment_report.json"
SOURCE_CATALOG_VALIDATION_REPORT = REPORTS_DIR / "source_catalog_validation_report.json"
TEXT_VECTOR_INDEX_PATH = INDEX_DIR / "text_vectors.jsonl"
TABLE_VECTOR_INDEX_PATH = INDEX_DIR / "table_row_vectors.jsonl"
VECTOR_INDEX_MANIFEST_PATH = INDEX_DIR / "vector_index_manifest.json"
RETRIEVAL_EVAL_PATH = EVAL_DIR / "retrieval_eval.jsonl"
RETRIEVAL_EVAL_REPORT = REPORTS_DIR / "retrieval_eval.json"
TRUSTED_EVAL_PATH = EVAL_DIR / "trusted_eval.jsonl"
TRUSTED_EVAL_REPORT = REPORTS_DIR / "trusted_eval.json"
TRUSTED_EVAL_SUMMARY_REPORT = REPORTS_DIR / "trusted_eval_summary.json"
KB_STATS_PATH = PROCESSED_DIR / "kb_stats.json"
KB_BUILD_STATE_PATH = PROCESSED_DIR / "kb_build_state.jsonl"
KB_BUILD_ERRORS_PATH = REPORTS_DIR / "kb_build_errors.json"
EXCEL_EVAL_REPORT = REPORTS_DIR / "excel_eval.json"
SQLITE_DB_PATH = DB_DIR / "jinrong.sqlite3"
TABLE_SEMANTICS_REPORT = REPORTS_DIR / "table_semantics_report.json"


SUPPORTED_EXTENSIONS = {".doc", ".docx", ".pdf", ".xls", ".xlsx", ".jsonl", ".csv"}
