from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import DOCUMENT_METADATA_PATH, MANIFEST_ENRICHED_PATH, MANIFEST_PATH, SQLITE_DB_PATH, TABLE_ROWS_PATH, TEXT_UNITS_PATH
from ..path_refs import to_project_ref
from ..utils import read_jsonl
from .repository import database_status
from .schema import connect, init_db


def import_processed_jsonl(
    db_path: Path = SQLITE_DB_PATH,
    manifest_path: Path | None = None,
    metadata_path: Path = DOCUMENT_METADATA_PATH,
    text_units_path: Path = TEXT_UNITS_PATH,
    table_rows_path: Path = TABLE_ROWS_PATH,
    reset: bool = False,
) -> dict[str, Any]:
    selected_manifest = manifest_path or (MANIFEST_ENRICHED_PATH if MANIFEST_ENRICHED_PATH.exists() else MANIFEST_PATH)
    started_at = _now()
    run_id = f"import_{started_at.replace(':', '').replace('-', '').replace('.', '')}_{uuid.uuid4().hex[:8]}"
    with connect(db_path) as conn:
        init_db(conn)
        _insert_import_run(conn, run_id, started_at, selected_manifest, metadata_path, text_units_path, table_rows_path)
        try:
            if reset:
                _clear_imported_tables(conn)
            documents = _import_documents(conn, selected_manifest, metadata_path)
            text_units = _import_text_units(conn, text_units_path)
            table_rows = _import_table_rows(conn, table_rows_path)
            conn.execute(
                """
                UPDATE import_runs
                SET finished_at = ?, status = ?, document_count = ?, text_unit_count = ?, table_row_count = ?
                WHERE run_id = ?
                """,
                (_now(), "success", documents, text_units, table_rows, run_id),
            )
            conn.commit()
        except Exception as exc:
            conn.execute(
                "UPDATE import_runs SET finished_at = ?, status = ?, error = ? WHERE run_id = ?",
                (_now(), "failed", str(exc), run_id),
            )
            conn.commit()
            raise
    status = database_status(db_path)
    return {"run_id": run_id, "reset": reset, "manifest_path": str(selected_manifest), **status}


def _insert_import_run(
    conn: sqlite3.Connection,
    run_id: str,
    started_at: str,
    manifest_path: Path,
    metadata_path: Path,
    text_units_path: Path,
    table_rows_path: Path,
) -> None:
    conn.execute(
        """
        INSERT INTO import_runs(run_id, started_at, status, manifest_path, metadata_path, text_units_path, table_rows_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            started_at,
            "running",
            to_project_ref(manifest_path),
            to_project_ref(metadata_path),
            to_project_ref(text_units_path),
            to_project_ref(table_rows_path),
        ),
    )


def _clear_imported_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM document_versions")
    conn.execute("DELETE FROM table_rows")
    conn.execute("DELETE FROM text_units")
    conn.execute("DELETE FROM documents")


def _import_documents(conn: sqlite3.Connection, manifest_path: Path, metadata_path: Path) -> int:
    manifest_rows = read_jsonl(manifest_path)
    metadata = {row["doc_id"]: row for row in read_jsonl(metadata_path)} if metadata_path.exists() else {}
    updated_at = _now()
    count = 0
    for row in manifest_rows:
        doc_id = row.get("doc_id")
        if not doc_id:
            continue
        meta = metadata.get(doc_id, {})
        merged = {**row, **{k: v for k, v in meta.items() if v is not None}}
        conn.execute(
            """
            INSERT INTO documents(
              doc_id, title, file_name, local_path, file_ext, file_size, sha256, source_type, period,
              publisher, publish_date, doc_no, business_domain, regulatory_topic,
              source_url, attachment_url, column_name, source_site, version_status, effective_date, expiry_date,
              supersedes_doc_id, superseded_by_doc_id, version_group, metadata_json, manifest_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
              title=excluded.title,
              file_name=excluded.file_name,
              local_path=excluded.local_path,
              file_ext=excluded.file_ext,
              file_size=excluded.file_size,
              sha256=excluded.sha256,
              source_type=excluded.source_type,
              period=excluded.period,
              publisher=excluded.publisher,
              publish_date=excluded.publish_date,
              doc_no=excluded.doc_no,
              business_domain=excluded.business_domain,
              regulatory_topic=excluded.regulatory_topic,
              source_url=excluded.source_url,
              attachment_url=excluded.attachment_url,
              column_name=excluded.column_name,
              source_site=excluded.source_site,
              version_status=excluded.version_status,
              effective_date=excluded.effective_date,
              expiry_date=excluded.expiry_date,
              supersedes_doc_id=excluded.supersedes_doc_id,
              superseded_by_doc_id=excluded.superseded_by_doc_id,
              version_group=excluded.version_group,
              metadata_json=excluded.metadata_json,
              manifest_json=excluded.manifest_json,
              updated_at=excluded.updated_at
            """,
            (
                doc_id,
                merged.get("title"),
                merged.get("file_name"),
                merged.get("local_path"),
                merged.get("file_ext"),
                merged.get("file_size"),
                merged.get("sha256"),
                merged.get("source_type"),
                merged.get("period"),
                merged.get("publisher"),
                merged.get("publish_date"),
                merged.get("doc_no"),
                merged.get("business_domain"),
                merged.get("regulatory_topic"),
                merged.get("source_url"),
                merged.get("attachment_url"),
                merged.get("column"),
                merged.get("source_site"),
                merged.get("version_status") or "unknown",
                merged.get("effective_date"),
                merged.get("expiry_date"),
                merged.get("supersedes_doc_id"),
                merged.get("superseded_by_doc_id"),
                merged.get("version_group"),
                _json(meta),
                _json(row),
                updated_at,
            ),
        )
        _upsert_document_version(conn, merged, updated_at)
        count += 1
    return count


def _upsert_document_version(conn: sqlite3.Connection, row: dict[str, Any], updated_at: str) -> None:
    doc_id = row.get("doc_id")
    if not doc_id:
        return
    version_id = f"{doc_id}:{row.get('sha256') or 'unknown'}"
    conn.execute(
        """
        INSERT INTO document_versions(
          version_id, doc_id, version_status, effective_date, expiry_date, publish_date, doc_no,
          version_group, supersedes_doc_id, superseded_by_doc_id, source_url, attachment_url, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(version_id) DO UPDATE SET
          version_status=excluded.version_status,
          effective_date=excluded.effective_date,
          expiry_date=excluded.expiry_date,
          publish_date=excluded.publish_date,
          doc_no=excluded.doc_no,
          version_group=excluded.version_group,
          supersedes_doc_id=excluded.supersedes_doc_id,
          superseded_by_doc_id=excluded.superseded_by_doc_id,
          source_url=excluded.source_url,
          attachment_url=excluded.attachment_url,
          updated_at=excluded.updated_at
        """,
        (
            version_id,
            doc_id,
            row.get("version_status") or "unknown",
            row.get("effective_date"),
            row.get("expiry_date"),
            row.get("publish_date"),
            row.get("doc_no"),
            row.get("version_group"),
            row.get("supersedes_doc_id"),
            row.get("superseded_by_doc_id"),
            row.get("source_url"),
            row.get("attachment_url"),
            updated_at,
        ),
    )


def _import_text_units(conn: sqlite3.Connection, path: Path) -> int:
    if not path.exists():
        return 0
    updated_at = _now()
    count = 0
    for row in read_jsonl(path):
        unit_id = row.get("unit_id")
        doc_id = row.get("doc_id")
        if not unit_id or not doc_id:
            continue
        conn.execute(
            """
            INSERT INTO text_units(
              unit_id, doc_id, source_type, source_title, chunk_id, chunk_index, unit_index,
              page_no, section_path, article_no, text, norm_text, raw_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(unit_id) DO UPDATE SET
              doc_id=excluded.doc_id,
              source_type=excluded.source_type,
              source_title=excluded.source_title,
              chunk_id=excluded.chunk_id,
              chunk_index=excluded.chunk_index,
              unit_index=excluded.unit_index,
              page_no=excluded.page_no,
              section_path=excluded.section_path,
              article_no=excluded.article_no,
              text=excluded.text,
              norm_text=excluded.norm_text,
              raw_json=excluded.raw_json,
              updated_at=excluded.updated_at
            """,
            (
                unit_id,
                doc_id,
                row.get("source_type"),
                row.get("source_title"),
                row.get("chunk_id"),
                row.get("chunk_index"),
                row.get("unit_index"),
                row.get("page_no"),
                row.get("section_path"),
                row.get("article_no"),
                row.get("text"),
                row.get("norm_text"),
                _json(row),
                updated_at,
            ),
        )
        count += 1
    return count


def _import_table_rows(conn: sqlite3.Connection, path: Path) -> int:
    if not path.exists():
        return 0
    updated_at = _now()
    count = 0
    for row in read_jsonl(path):
        row_id = row.get("row_id")
        doc_id = row.get("doc_id")
        if not row_id or not doc_id:
            continue
        conn.execute(
            """
            INSERT INTO table_rows(
              row_id, doc_id, source_type, source_title, sheet_name, row_index, row_header,
              indicator, period, periods_json, headers_json, cells_json, unit, cell_refs_json, values_json, text, norm_text, raw_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(row_id) DO UPDATE SET
              doc_id=excluded.doc_id,
              source_type=excluded.source_type,
              source_title=excluded.source_title,
              sheet_name=excluded.sheet_name,
              row_index=excluded.row_index,
              row_header=excluded.row_header,
              indicator=excluded.indicator,
              period=excluded.period,
              periods_json=excluded.periods_json,
              headers_json=excluded.headers_json,
              cells_json=excluded.cells_json,
              unit=excluded.unit,
              cell_refs_json=excluded.cell_refs_json,
              values_json=excluded.values_json,
              text=excluded.text,
              norm_text=excluded.norm_text,
              raw_json=excluded.raw_json,
              updated_at=excluded.updated_at
            """,
            (
                row_id,
                doc_id,
                row.get("source_type"),
                row.get("source_title"),
                row.get("sheet_name"),
                row.get("row_index"),
                row.get("row_header"),
                row.get("indicator") or row.get("row_header"),
                row.get("period") or _first_or_none(row.get("periods")),
                _json(row.get("periods")),
                _json(row.get("headers")),
                _json(row.get("cells")),
                row.get("unit"),
                _json(row.get("cell_refs")),
                _json(row.get("values")),
                row.get("text"),
                row.get("norm_text"),
                _json(row),
                updated_at,
            ),
        )
        count += 1
    return count


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _first_or_none(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
