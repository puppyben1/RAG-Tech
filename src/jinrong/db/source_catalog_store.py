from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import MANIFEST_PATH, SQLITE_DB_PATH
from ..path_refs import to_project_ref
from ..source_catalog import _clean_value, _match_catalog_row, _read_catalog, _build_catalog_indexes, validate_source_catalog
from ..utils import read_jsonl
from .repository import database_status
from .schema import connect, init_db


def import_source_catalog_to_db(
    source_catalog_path: Path,
    db_path: Path = SQLITE_DB_PATH,
    manifest_path: Path = MANIFEST_PATH,
    reset_catalog: bool = False,
) -> dict[str, Any]:
    validation = validate_source_catalog(source_catalog_path, manifest_path=manifest_path)
    if not validation["valid"]:
        raise ValueError(f"source catalog has {validation['blocking_issue_count']} blocking issue(s)")
    catalog_rows = _read_catalog(source_catalog_path)
    manifest = read_jsonl(manifest_path)
    indexes = _build_catalog_indexes(catalog_rows)
    imported_at = _now()
    with connect(db_path) as conn:
        init_db(conn)
        if reset_catalog:
            conn.execute("DELETE FROM source_catalog_entries")
        for row_index, row in enumerate(catalog_rows, start=1):
            match_doc_id = None
            match_by = None
            for record in manifest:
                if not record.get("doc_id"):
                    continue
                candidate, candidate_match_by = _match_catalog_row(record, indexes)
                if candidate is row:
                    match_doc_id = record.get("doc_id")
                    match_by = candidate_match_by
                    break
            entry_id = _entry_id(source_catalog_path, row_index, row)
            conn.execute(
                """
                INSERT INTO source_catalog_entries(
                  entry_id, imported_at, catalog_path, row_index, match_doc_id, match_by, match_status,
                  doc_id, sha256, file_name, title, source_url, attachment_url, column_name,
                  source_site, version_status, effective_date, expiry_date, supersedes_doc_id, superseded_by_doc_id, version_group,
                  publisher, publish_date, doc_no, business_domain, regulatory_topic, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                  imported_at=excluded.imported_at,
                  match_doc_id=excluded.match_doc_id,
                  match_by=excluded.match_by,
                  match_status=excluded.match_status,
                  doc_id=excluded.doc_id,
                  sha256=excluded.sha256,
                  file_name=excluded.file_name,
                  title=excluded.title,
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
                  publisher=excluded.publisher,
                  publish_date=excluded.publish_date,
                  doc_no=excluded.doc_no,
                  business_domain=excluded.business_domain,
                  regulatory_topic=excluded.regulatory_topic,
                  raw_json=excluded.raw_json
                """,
                (
                    entry_id,
                    imported_at,
                    to_project_ref(source_catalog_path),
                    row_index,
                    match_doc_id,
                    match_by,
                    "matched" if match_doc_id else "unmatched",
                    _clean_value(row.get("doc_id")),
                    _clean_value(row.get("sha256")),
                    _clean_value(row.get("file_name")),
                    _clean_value(row.get("title")),
                    _clean_value(row.get("source_url")),
                    _clean_value(row.get("attachment_url")),
                    _clean_value(row.get("column")),
                    _clean_value(row.get("source_site")),
                    _clean_value(row.get("version_status")) or "unknown",
                    _clean_value(row.get("effective_date")),
                    _clean_value(row.get("expiry_date")),
                    _clean_value(row.get("supersedes_doc_id")),
                    _clean_value(row.get("superseded_by_doc_id")),
                    _clean_value(row.get("version_group")),
                    _clean_value(row.get("publisher")),
                    _clean_value(row.get("publish_date")),
                    _clean_value(row.get("doc_no")),
                    _clean_value(row.get("business_domain")),
                    _clean_value(row.get("regulatory_topic")),
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                ),
            )
        conn.commit()
    return {
        "source_catalog_path": to_project_ref(source_catalog_path),
        "reset_catalog": reset_catalog,
        "validation": validation,
        "database": database_status(db_path),
    }


def _entry_id(path: Path, row_index: int, row: dict[str, Any]) -> str:
    payload = json.dumps({"path": to_project_ref(path), "row_index": row_index, "row": row}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
