from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config import SQLITE_DB_PATH
from .schema import connect, init_db


def database_status(db_path: Path = SQLITE_DB_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {"available": False, "db_path": str(db_path)}
    with connect(db_path) as conn:
        init_db(conn)
        tables = [
            "documents",
            "document_versions",
            "text_units",
            "table_rows",
            "source_catalog_entries",
            "metadata_quality_reports",
            "version_audit_reports",
            "import_runs",
        ]
        counts = {table: _count(conn, table) for table in tables}
        latest_run = conn.execute(
            """
            SELECT run_id, started_at, finished_at, status, document_count, text_unit_count, table_row_count, error
            FROM import_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
    return {
        "available": True,
        "db_path": str(db_path),
        **counts,
        "latest_import_run": dict(latest_run) if latest_run else None,
    }


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
