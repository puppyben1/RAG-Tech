from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import ensure_dir, read_jsonl


MIN_EXTRACTED_CHARS = 100
MAX_ABNORMAL_RATIO = 0.01


def audit_doc_quality(
    manifest_path: Path,
    chunks_path: Path,
    build_state_path: Path,
    report_path: Path,
    *,
    worklist_path: Path | None = None,
    reviewed_path: Path | None = None,
) -> dict[str, Any]:
    manifest = [row for row in read_jsonl(manifest_path) if str(row.get("file_ext") or "").lower() == ".doc"]
    chunks_by_doc: dict[str, list[str]] = defaultdict(list)
    for row in read_jsonl(chunks_path):
        if row.get("doc_id"):
            chunks_by_doc[str(row["doc_id"])].append(str(row.get("text") or ""))
    state_by_doc = {
        str(row.get("doc_id")): row
        for row in read_jsonl(build_state_path)
        if row.get("doc_id")
    }
    reviews = _load_reviews(reviewed_path)

    rows: list[dict[str, Any]] = []
    for source in manifest:
        doc_id = str(source.get("doc_id") or "")
        texts = chunks_by_doc.get(doc_id, [])
        combined = "\n".join(texts)
        state = state_by_doc.get(doc_id, {})
        abnormal_count = sum(1 for char in combined if char == "\ufffd" or (ord(char) < 32 and char not in "\n\r\t"))
        abnormal_ratio = abnormal_count / len(combined) if combined else 1.0
        warning = str(state.get("warning") or "")
        machine_issues = []
        if state.get("status") not in {"success", "success_with_warning"}:
            machine_issues.append("build_not_successful")
        if not texts:
            machine_issues.append("no_text_chunks")
        if len(combined) < MIN_EXTRACTED_CHARS:
            machine_issues.append("extracted_text_too_short")
        if abnormal_ratio > MAX_ABNORMAL_RATIO:
            machine_issues.append("abnormal_character_ratio")
        fallback_used = "fallback" in warning.lower()
        extracted_sha = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        review = reviews.get(doc_id)
        review_current = bool(
            review
            and review.get("source_sha256") == source.get("sha256")
            and review.get("extracted_text_sha256") == extracted_sha
        )
        review_passed = bool(
            review_current
            and review.get("review_status") == "reviewed"
            and review.get("readable") is True
            and review.get("content_complete") is True
            and review.get("tables_complete") is True
            and str(review.get("reviewed_by") or "").strip()
            and _valid_review_time(review.get("reviewed_at"))
        )
        rows.append(
            {
                "doc_id": doc_id,
                "file_name": source.get("file_name"),
                "source_sha256": source.get("sha256"),
                "chunk_count": len(texts),
                "extracted_chars": len(combined),
                "extracted_text_sha256": extracted_sha,
                "abnormal_character_ratio": round(abnormal_ratio, 6),
                "build_warning": warning or None,
                "fallback_used": fallback_used,
                "machine_issues": machine_issues,
                "machine_passed": not machine_issues,
                "manual_review_required": fallback_used,
                "manual_review_current": review_current,
                "manual_review_passed": review_passed,
            }
        )

    machine_failed = [row["doc_id"] for row in rows if not row["machine_passed"]]
    review_required = [row["doc_id"] for row in rows if row["manual_review_required"]]
    review_pending = [row["doc_id"] for row in rows if row["manual_review_required"] and not row["manual_review_passed"]]
    gate_reasons = []
    if not rows:
        gate_reasons.append("no_doc_files")
    if machine_failed:
        gate_reasons.append(f"machine_quality_failed:{len(machine_failed)}")
    if review_pending:
        gate_reasons.append(f"manual_review_pending:{len(review_pending)}")
    report = {
        "schema_version": "doc_quality_audit_v1",
        "documents": len(rows),
        "machine_passed": len(rows) - len(machine_failed),
        "machine_failed": len(machine_failed),
        "fallback_used": len(review_required),
        "manual_review_required": len(review_required),
        "manual_review_pending": len(review_pending),
        "gate": "passed" if not gate_reasons else "blocked",
        "gate_reasons": gate_reasons,
        "documents_detail": rows,
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if worklist_path is not None:
        _write_worklist(worklist_path, rows, reviews)
    return report


def approve_doc_reviews(
    review_path: Path,
    output_path: Path,
    reviewer: str,
    reviewed_at: str,
    doc_ids: list[str],
) -> dict[str, Any]:
    if review_path.resolve() == output_path.resolve():
        raise ValueError("approved output must differ from review input")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if not _valid_review_time(reviewed_at):
        raise ValueError("reviewed_at must be ISO-8601 with timezone")
    selected = {str(value).strip() for value in doc_ids if str(value).strip()}
    rows = read_jsonl(review_path)
    available = {str(row.get("doc_id") or "") for row in rows}
    missing = sorted(selected - available)
    if not selected or missing:
        raise ValueError("reviewed doc_ids must be present in the review worklist")
    for row in rows:
        if str(row.get("doc_id") or "") not in selected:
            continue
        if not all(row.get(field) is True for field in ("readable", "content_complete", "tables_complete")):
            raise ValueError(f"manual checks are incomplete for {row.get('doc_id')}")
        row["review_status"] = "reviewed"
        row["reviewed_by"] = reviewer.strip()
        row["reviewed_at"] = reviewed_at
    ensure_dir(output_path.parent)
    output_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return {
        "approved_doc_ids": sorted(selected),
        "pending_doc_ids": sorted(str(row.get("doc_id")) for row in rows if row.get("review_status") != "reviewed"),
    }


def _write_worklist(path: Path, rows: list[dict[str, Any]], prior: dict[str, dict[str, Any]]) -> None:
    output = []
    for row in rows:
        existing = prior.get(row["doc_id"], {})
        output.append(
            {
                "doc_id": row["doc_id"],
                "file_name": row["file_name"],
                "source_sha256": row["source_sha256"],
                "extracted_text_sha256": row["extracted_text_sha256"],
                "chunk_count": row["chunk_count"],
                "extracted_chars": row["extracted_chars"],
                "readable": existing.get("readable"),
                "content_complete": existing.get("content_complete"),
                "tables_complete": existing.get("tables_complete"),
                "notes": existing.get("notes"),
                "review_status": existing.get("review_status", "pending_external_review"),
                "reviewed_by": existing.get("reviewed_by"),
                "reviewed_at": existing.get("reviewed_at"),
            }
        )
    ensure_dir(path.parent)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in output) + "\n", encoding="utf-8")


def _load_reviews(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    return {str(row.get("doc_id") or ""): row for row in read_jsonl(path)}


def _valid_review_time(value: Any) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
