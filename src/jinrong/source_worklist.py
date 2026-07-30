from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import (
    DOCUMENT_METADATA_PATH,
    RETRIEVAL_EVAL_PATH,
    SOURCE_GAP_WORKLIST_PATH,
    SOURCE_GAP_WORKLIST_REPORT,
    TRUSTED_EVAL_PATH,
)
from .source_catalog import CATALOG_FIELDS
from .utils import ensure_dir, read_jsonl


WORKLIST_FIELDS = (
    "priority",
    "priority_reasons",
    "missing_fields",
    "source_type",
    "file_ext",
    *CATALOG_FIELDS,
)


def build_source_gap_worklist(
    metadata_path: Path = DOCUMENT_METADATA_PATH,
    trusted_eval_path: Path = TRUSTED_EVAL_PATH,
    retrieval_eval_path: Path = RETRIEVAL_EVAL_PATH,
    output_path: Path = SOURCE_GAP_WORKLIST_PATH,
    report_path: Path = SOURCE_GAP_WORKLIST_REPORT,
    limit: int | None = None,
) -> dict[str, Any]:
    docs = read_jsonl(metadata_path)
    trusted_refs = _eval_doc_refs(trusted_eval_path, multi_field="expected_doc_ids", single_field="expected_doc_id")
    retrieval_refs = _eval_doc_refs(retrieval_eval_path, multi_field="expected_doc_ids", single_field="expected_doc_id")
    rows = [_worklist_row(doc, trusted_refs, retrieval_refs) for doc in docs]
    rows = [row for row in rows if row["missing_fields"]]
    rows.sort(key=lambda row: (-int(row["priority"]), str(row.get("doc_id") or "")))
    if limit:
        rows = rows[:limit]

    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WORKLIST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report = _report(rows, docs, trusted_refs, retrieval_refs, output_path)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _eval_doc_refs(path: Path, multi_field: str, single_field: str) -> Counter[str]:
    refs: Counter[str] = Counter()
    if not path.exists():
        return refs
    for row in read_jsonl(path):
        values = row.get(multi_field)
        if isinstance(values, list):
            for value in values:
                if value:
                    refs[str(value)] += 1
        value = row.get(single_field)
        if value:
            refs[str(value)] += 1
    return refs


def _worklist_row(doc: dict[str, Any], trusted_refs: Counter[str], retrieval_refs: Counter[str]) -> dict[str, Any]:
    doc_id = str(doc.get("doc_id") or "")
    missing = _missing_fields(doc)
    score = 0
    reasons: list[str] = []

    eval_hits = trusted_refs.get(doc_id, 0) + retrieval_refs.get(doc_id, 0)
    if eval_hits:
        score += eval_hits * 100
        reasons.append(f"eval_hit:{eval_hits}")
    if doc.get("source_type") in {"pdf", "word"}:
        score += 30
        reasons.append("regulation_text")
    if doc.get("source_type") == "excel":
        score += 20
        reasons.append("stat_table")
    if not doc.get("source_url") or not doc.get("attachment_url"):
        score += 20
        reasons.append("missing_source")
    if (doc.get("version_status") or "unknown") == "unknown":
        score += 15
        reasons.append("unknown_version")
    if doc.get("doc_no"):
        score += 10
        reasons.append("has_doc_no")
    if doc.get("publish_date"):
        score += 5
        reasons.append("has_publish_date")

    row = {
        "priority": str(score),
        "priority_reasons": ";".join(reasons),
        "missing_fields": ";".join(missing),
        "source_type": str(doc.get("source_type") or ""),
        "file_ext": str(doc.get("file_ext") or ""),
    }
    for field in CATALOG_FIELDS:
        value = doc.get(field)
        if field == "version_status" and not value:
            value = "unknown"
        row[field] = "" if value is None else str(value)
    return row


def _missing_fields(doc: dict[str, Any]) -> list[str]:
    fields = (
        "source_url",
        "attachment_url",
        "source_site",
        "publish_date",
        "version_status",
        "version_group",
        "effective_date",
    )
    missing = []
    for field in fields:
        value = doc.get(field)
        if field == "version_status":
            if not value or value == "unknown":
                missing.append(field)
        elif not value:
            missing.append(field)
    return missing


def _report(
    rows: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    trusted_refs: Counter[str],
    retrieval_refs: Counter[str],
    output_path: Path,
) -> dict[str, Any]:
    top = [
        {
            "doc_id": row.get("doc_id"),
            "title": row.get("title"),
            "source_type": row.get("source_type"),
            "priority": int(row["priority"]),
            "priority_reasons": row["priority_reasons"],
            "missing_fields": row["missing_fields"],
        }
        for row in rows[:20]
    ]
    return {
        "output_path": str(output_path),
        "documents": len(docs),
        "worklist_rows": len(rows),
        "trusted_eval_referenced_docs": len(trusted_refs),
        "retrieval_eval_referenced_docs": len(retrieval_refs),
        "missing_field_counts": {
            field: sum(1 for row in rows if field in row["missing_fields"].split(";"))
            for field in (
                "source_url",
                "attachment_url",
                "source_site",
                "publish_date",
                "version_status",
                "version_group",
                "effective_date",
            )
        },
        "top_priority_sample": top,
    }
