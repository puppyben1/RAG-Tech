from __future__ import annotations

import sqlite3
from pathlib import Path

from ..utils import ensure_dir


SCHEMA_VERSION = 1


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS import_runs (
          run_id TEXT PRIMARY KEY,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          status TEXT NOT NULL,
          manifest_path TEXT,
          metadata_path TEXT,
          text_units_path TEXT,
          table_rows_path TEXT,
          document_count INTEGER DEFAULT 0,
          text_unit_count INTEGER DEFAULT 0,
          table_row_count INTEGER DEFAULT 0,
          error TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
          doc_id TEXT PRIMARY KEY,
          title TEXT,
          file_name TEXT,
          local_path TEXT,
          file_ext TEXT,
          file_size INTEGER,
          sha256 TEXT,
          source_type TEXT,
          period TEXT,
          publisher TEXT,
          publish_date TEXT,
          doc_no TEXT,
          business_domain TEXT,
          regulatory_topic TEXT,
          source_url TEXT,
          attachment_url TEXT,
          column_name TEXT,
          source_site TEXT,
          version_status TEXT DEFAULT 'unknown',
          effective_date TEXT,
          expiry_date TEXT,
          supersedes_doc_id TEXT,
          superseded_by_doc_id TEXT,
          version_group TEXT,
          metadata_json TEXT,
          manifest_json TEXT,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_versions (
          version_id TEXT PRIMARY KEY,
          doc_id TEXT NOT NULL,
          version_status TEXT DEFAULT 'unknown',
          effective_date TEXT,
          expiry_date TEXT,
          publish_date TEXT,
          doc_no TEXT,
          version_group TEXT,
          supersedes_doc_id TEXT,
          superseded_by_doc_id TEXT,
          source_url TEXT,
          attachment_url TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS text_units (
          unit_id TEXT PRIMARY KEY,
          doc_id TEXT NOT NULL,
          source_type TEXT,
          source_title TEXT,
          chunk_id TEXT,
          chunk_index INTEGER,
          unit_index INTEGER,
          page_no INTEGER,
          section_path TEXT,
          article_no TEXT,
          text TEXT,
          norm_text TEXT,
          raw_json TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS table_rows (
          row_id TEXT PRIMARY KEY,
          doc_id TEXT NOT NULL,
          source_type TEXT,
          source_title TEXT,
          sheet_name TEXT,
          row_index INTEGER,
          row_header TEXT,
          indicator TEXT,
          period TEXT,
          periods_json TEXT,
          headers_json TEXT,
          cells_json TEXT,
          unit TEXT,
          cell_refs_json TEXT,
          values_json TEXT,
          text TEXT,
          norm_text TEXT,
          raw_json TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS source_catalog_entries (
          entry_id TEXT PRIMARY KEY,
          imported_at TEXT NOT NULL,
          catalog_path TEXT NOT NULL,
          row_index INTEGER NOT NULL,
          match_doc_id TEXT,
          match_by TEXT,
          match_status TEXT NOT NULL,
          doc_id TEXT,
          sha256 TEXT,
          file_name TEXT,
          title TEXT,
          source_url TEXT,
          attachment_url TEXT,
          column_name TEXT,
          source_site TEXT,
          version_status TEXT,
          effective_date TEXT,
          expiry_date TEXT,
          supersedes_doc_id TEXT,
          superseded_by_doc_id TEXT,
          version_group TEXT,
          publisher TEXT,
          publish_date TEXT,
          doc_no TEXT,
          business_domain TEXT,
          regulatory_topic TEXT,
          raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS metadata_quality_reports (
          report_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          report_path TEXT,
          documents INTEGER NOT NULL,
          publisher_filled INTEGER NOT NULL,
          publish_date_filled INTEGER NOT NULL,
          doc_no_filled INTEGER NOT NULL,
          source_url_filled INTEGER NOT NULL,
          attachment_url_filled INTEGER NOT NULL,
          payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS version_audit_reports (
          report_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          report_path TEXT,
          documents INTEGER NOT NULL,
          current_count INTEGER NOT NULL,
          superseded_count INTEGER NOT NULL,
          unknown_count INTEGER NOT NULL,
          dangling_relation_count INTEGER NOT NULL,
          group_issue_count INTEGER NOT NULL,
          payload_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
        CREATE INDEX IF NOT EXISTS idx_documents_file_ext ON documents(file_ext);
        CREATE INDEX IF NOT EXISTS idx_documents_publisher ON documents(publisher);
        CREATE INDEX IF NOT EXISTS idx_documents_publish_date ON documents(publish_date);
        CREATE INDEX IF NOT EXISTS idx_documents_business_domain ON documents(business_domain);
        CREATE INDEX IF NOT EXISTS idx_documents_regulatory_topic ON documents(regulatory_topic);
        CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);
        CREATE INDEX IF NOT EXISTS idx_document_versions_doc_id ON document_versions(doc_id);
        CREATE INDEX IF NOT EXISTS idx_document_versions_status ON document_versions(version_status);
        CREATE INDEX IF NOT EXISTS idx_document_versions_group ON document_versions(version_group);
        CREATE INDEX IF NOT EXISTS idx_text_units_doc_id ON text_units(doc_id);
        CREATE INDEX IF NOT EXISTS idx_text_units_article_no ON text_units(article_no);
        CREATE INDEX IF NOT EXISTS idx_text_units_section_path ON text_units(section_path);
        CREATE INDEX IF NOT EXISTS idx_table_rows_doc_id ON table_rows(doc_id);
        CREATE INDEX IF NOT EXISTS idx_table_rows_sheet_name ON table_rows(sheet_name);
        CREATE INDEX IF NOT EXISTS idx_table_rows_row_header ON table_rows(row_header);
        CREATE INDEX IF NOT EXISTS idx_table_rows_indicator ON table_rows(indicator);
        CREATE INDEX IF NOT EXISTS idx_source_catalog_entries_catalog_path ON source_catalog_entries(catalog_path);
        CREATE INDEX IF NOT EXISTS idx_source_catalog_entries_match_doc_id ON source_catalog_entries(match_doc_id);
        CREATE INDEX IF NOT EXISTS idx_source_catalog_entries_match_status ON source_catalog_entries(match_status);
        CREATE INDEX IF NOT EXISTS idx_metadata_quality_reports_created_at ON metadata_quality_reports(created_at);
        CREATE INDEX IF NOT EXISTS idx_version_audit_reports_created_at ON version_audit_reports(created_at);
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    _ensure_column(conn, "table_rows", "periods_json", "TEXT")
    _ensure_column(conn, "table_rows", "headers_json", "TEXT")
    _ensure_column(conn, "table_rows", "cells_json", "TEXT")
    for column in (
        "source_site",
        "version_status",
        "effective_date",
        "expiry_date",
        "supersedes_doc_id",
        "superseded_by_doc_id",
        "version_group",
    ):
        _ensure_column(conn, "documents", column, "TEXT")
        _ensure_column(conn, "source_catalog_entries", column, "TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_version_status ON documents(version_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_effective_date ON documents(effective_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_version_group ON documents(version_group)")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
