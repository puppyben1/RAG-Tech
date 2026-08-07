from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import (
    MANIFEST_ENRICHED_PATH,
    MANIFEST_PATH,
    SOURCE_CATALOG_TEMPLATE_PATH,
    SOURCE_ENRICHMENT_REPORT,
    SOURCE_CATALOG_VALIDATION_REPORT,
)
from .path_refs import to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl, write_jsonl


CATALOG_FIELDS = (
    "doc_id",
    "sha256",
    "file_name",
    "title",
    "period",
    "source_url",
    "attachment_url",
    "column",
    "publisher",
    "publish_date",
    "doc_no",
    "business_domain",
    "regulatory_topic",
    "source_site",
    "version_status",
    "effective_date",
    "expiry_date",
    "supersedes_doc_id",
    "superseded_by_doc_id",
    "version_group",
    "source_evidence",
    "version_evidence",
    "version_evidence_url",
    "proof_type",
    "verification_method",
    "verified_at",
    "proof_evidence",
    "reviewed_by",
    "reviewed_at",
)

MERGE_FIELDS = (
    "period",
    "source_url",
    "attachment_url",
    "column",
    "publisher",
    "publish_date",
    "doc_no",
    "business_domain",
    "regulatory_topic",
    "source_site",
    "version_status",
    "effective_date",
    "expiry_date",
    "supersedes_doc_id",
    "superseded_by_doc_id",
    "version_group",
    "source_evidence",
    "version_evidence",
    "version_evidence_url",
    "proof_type",
    "verification_method",
    "verified_at",
    "proof_evidence",
    "reviewed_by",
    "reviewed_at",
)

VERSION_STATUS_VALUES = {"", "current", "superseded", "unknown", "not_applicable"}


def approve_source_catalog(
    source_catalog_path: Path,
    output_path: Path,
    reviewer: str,
    reviewed_at: str,
    doc_ids: list[str],
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    """Stamp explicitly selected rows, then require the resulting catalog to validate."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    if source_catalog_path.resolve() == output_path.resolve():
        raise ValueError("approved output must differ from source catalog")
    try:
        datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("reviewed_at must be ISO-8601") from exc
    selected = {str(doc_id).strip() for doc_id in doc_ids if str(doc_id).strip()}
    if not selected:
        raise ValueError("at least one doc_id is required")
    rows = _read_catalog(source_catalog_path)
    matched = {str(row.get("doc_id")) for row in rows if str(row.get("doc_id")) in selected}
    missing = sorted(selected - matched)
    if missing:
        raise ValueError(f"doc_id not found in catalog: {', '.join(missing)}")
    for row in rows:
        if str(row.get("doc_id")) in selected:
            row["reviewed_by"] = reviewer
            row["reviewed_at"] = reviewed_at
    _write_catalog(output_path, rows)
    validation = validate_source_catalog(
        output_path,
        manifest_path=manifest_path,
        report_path=output_path.with_name(f"{output_path.stem}.validation.json"),
    )
    if not validation["valid"]:
        raise ValueError(f"approved catalog remains invalid: {validation['blocking_issue_count']} blocking issue(s)")
    return {
        "source_catalog_path": to_project_ref(source_catalog_path),
        "output_path": to_project_ref(output_path),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "approved_doc_ids": sorted(selected),
        "validation": validation,
    }


def export_source_catalog_template(
    manifest_path: Path = MANIFEST_PATH,
    output_path: Path = SOURCE_CATALOG_TEMPLATE_PATH,
) -> dict[str, Any]:
    rows = read_jsonl(manifest_path)
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") or "" for field in CATALOG_FIELDS})
    return {"output_path": to_project_ref(output_path), "documents": len(rows), "fields": list(CATALOG_FIELDS)}


def enrich_manifest_from_source_catalog(
    source_catalog_path: Path,
    manifest_path: Path = MANIFEST_PATH,
    output_path: Path = MANIFEST_ENRICHED_PATH,
    report_path: Path = SOURCE_ENRICHMENT_REPORT,
) -> dict[str, Any]:
    validation = validate_source_catalog(
        source_catalog_path,
        manifest_path=manifest_path,
        report_path=report_path.with_name("source_catalog_validation_report.json"),
    )
    if not validation["valid"]:
        raise ValueError(f"source catalog has {validation['blocking_issue_count']} blocking issue(s)")
    manifest = read_jsonl(manifest_path)
    catalog_rows = _read_catalog(source_catalog_path)
    indexes = _build_catalog_indexes(catalog_rows)

    enriched: list[dict[str, Any]] = []
    matched = 0
    field_updates = {field: 0 for field in MERGE_FIELDS}
    unmatched_manifest: list[dict[str, str]] = []
    used_catalog_ids: set[int] = set()

    for record in manifest:
        catalog_row, match_by = _match_catalog_row(record, indexes)
        merged = dict(record)
        if catalog_row:
            matched += 1
            used_catalog_ids.add(id(catalog_row))
            merged["source_catalog_match_by"] = match_by
            for field in MERGE_FIELDS:
                value = _clean_value(catalog_row.get(field))
                if value and value != merged.get(field):
                    merged[field] = value
                    field_updates[field] += 1
        else:
            unmatched_manifest.append({"doc_id": record.get("doc_id", ""), "file_name": record.get("file_name", "")})
        enriched.append(merged)

    write_jsonl(output_path, enriched)

    unmatched_catalog = [
        _catalog_identity(row)
        for row in catalog_rows
        if id(row) not in used_catalog_ids and any(_clean_value(row.get(field)) for field in MERGE_FIELDS)
    ]
    report = {
        "source_catalog_path": to_project_ref(source_catalog_path),
        "output_path": to_project_ref(output_path),
        "documents": len(manifest),
        "catalog_rows": len(catalog_rows),
        "matched_documents": matched,
        "unmatched_documents": len(unmatched_manifest),
        "unmatched_catalog_rows": len(unmatched_catalog),
        "field_updates": field_updates,
        "source_url_filled": sum(1 for row in enriched if row.get("source_url")),
        "attachment_url_filled": sum(1 for row in enriched if row.get("attachment_url")),
        "column_filled": sum(1 for row in enriched if row.get("column")),
        "unmatched_manifest_sample": unmatched_manifest[:20],
        "unmatched_catalog_sample": unmatched_catalog[:20],
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def validate_source_catalog(
    source_catalog_path: Path,
    manifest_path: Path = MANIFEST_PATH,
    report_path: Path = SOURCE_CATALOG_VALIDATION_REPORT,
) -> dict[str, Any]:
    manifest = read_jsonl(manifest_path)
    catalog_rows = _read_catalog(source_catalog_path)
    indexes = _build_catalog_indexes(catalog_rows)
    manifest_by_doc = {row.get("doc_id"): row for row in manifest if row.get("doc_id")}
    matched = 0
    match_by_counts: dict[str, int] = {}
    missing_required_identity = 0
    url_warnings: list[dict[str, Any]] = []
    review_issues: list[dict[str, Any]] = []
    duplicates = _duplicate_report(catalog_rows)
    conflicts: list[dict[str, Any]] = []
    used_catalog_ids: set[int] = set()

    for row_index, row in enumerate(catalog_rows, start=1):
        if not any(_clean_value(row.get(field)) for field in ("doc_id", "sha256", "file_name", "title")):
            missing_required_identity += 1
        for field in ("source_url", "attachment_url", "version_evidence_url"):
            value = _clean_value(row.get(field))
            if value and not _looks_like_url(value):
                url_warnings.append({"row_index": row_index, "field": field, "value": value})
        version_status = _clean_value(row.get("version_status"))
        if version_status and version_status not in VERSION_STATUS_VALUES:
            url_warnings.append({"row_index": row_index, "field": "version_status", "value": version_status})
        for field in ("publish_date", "effective_date", "expiry_date"):
            value = _clean_value(row.get(field))
            if value and not _looks_like_date(value):
                url_warnings.append({"row_index": row_index, "field": field, "value": value})
        review_issues.extend(_review_issues(row, row_index))

    for record in manifest:
        catalog_row, match_by = _match_catalog_row(record, indexes)
        if catalog_row:
            matched += 1
            used_catalog_ids.add(id(catalog_row))
            match_by_counts[match_by or "unknown"] = match_by_counts.get(match_by or "unknown", 0) + 1
            changed_fields = [
                field
                for field in MERGE_FIELDS
                if _clean_value(catalog_row.get(field))
                and _clean_value(record.get(field))
                and _clean_value(catalog_row.get(field)) != _clean_value(record.get(field))
            ]
            if changed_fields:
                conflicts.append(
                    {
                        "doc_id": record.get("doc_id"),
                        "file_name": record.get("file_name"),
                        "match_by": match_by,
                        "fields": changed_fields,
                    }
                )

    unmatched_catalog = [
        _catalog_identity(row)
        for row in catalog_rows
        if id(row) not in used_catalog_ids and any(_clean_value(row.get(field)) for field in MERGE_FIELDS)
    ]
    blocking_issue_count = missing_required_identity + len(url_warnings) + len(review_issues) + sum(
        len(duplicates.get(key, [])) for key in ("doc_id", "sha256", "file_name")
    )
    report = {
        "source_catalog_path": to_project_ref(source_catalog_path),
        "manifest_path": to_project_ref(manifest_path),
        "documents": len(manifest),
        "catalog_rows": len(catalog_rows),
        "matched_documents": matched,
        "match_rate": matched / len(manifest) if manifest else 0,
        "match_by": match_by_counts,
        "missing_identity_rows": missing_required_identity,
        "duplicate_keys": duplicates,
        "url_warning_count": len(url_warnings),
        "url_warning_sample": url_warnings[:20],
        "review_issue_count": len(review_issues),
        "review_issue_sample": review_issues[:20],
        "conflict_count": len(conflicts),
        "conflict_sample": conflicts[:20],
        "unmatched_catalog_rows": len(unmatched_catalog),
        "unmatched_catalog_sample": unmatched_catalog[:20],
        "source_url_candidates": sum(1 for row in catalog_rows if _clean_value(row.get("source_url"))),
        "attachment_url_candidates": sum(1 for row in catalog_rows if _clean_value(row.get("attachment_url"))),
        "column_candidates": sum(1 for row in catalog_rows if _clean_value(row.get("column"))),
        "version_status_candidates": sum(1 for row in catalog_rows if _clean_value(row.get("version_status"))),
        "effective_date_candidates": sum(1 for row in catalog_rows if _clean_value(row.get("effective_date"))),
        "version_relation_candidates": sum(
            1 for row in catalog_rows if _clean_value(row.get("supersedes_doc_id")) or _clean_value(row.get("superseded_by_doc_id"))
        ),
        "known_manifest_doc_ids": len(manifest_by_doc),
        "blocking_issue_count": blocking_issue_count,
        "valid": blocking_issue_count == 0,
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _read_catalog(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return read_jsonl(path)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("documents"), list):
            return [row for row in payload["documents"] if isinstance(row, dict)]
        raise ValueError("JSON source catalog must be a list or contain a documents list")
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    raise ValueError("source catalog must be .csv, .jsonl, or .json")


def _write_catalog(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if path.suffix.lower() == ".jsonl":
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
        return
    if path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
            writer.writeheader()
            writer.writerows({field: row.get(field, "") or "" for field in CATALOG_FIELDS} for row in rows)
        return
    raise ValueError("approved catalog output must be .csv or .jsonl")


def _build_catalog_indexes(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexes: dict[str, dict[str, dict[str, Any]]] = {"doc_id": {}, "sha256": {}, "file_name": {}, "title": {}}
    for row in rows:
        for key in ("doc_id", "sha256", "file_name"):
            value = _clean_value(row.get(key))
            if value and value not in indexes[key]:
                indexes[key][value] = row
        title = norm_text(row.get("title"))
        if title and title not in indexes["title"]:
            indexes["title"][title] = row
    return indexes


def _match_catalog_row(record: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> tuple[dict[str, Any] | None, str | None]:
    for key in ("doc_id", "sha256", "file_name"):
        value = _clean_value(record.get(key))
        if value and value in indexes[key]:
            return indexes[key][value], key
    title = norm_text(record.get("title"))
    if title:
        if title in indexes["title"]:
            return indexes["title"][title], "title"
        for candidate_title, row in indexes["title"].items():
            if title in candidate_title or candidate_title in title:
                return row, "title_loose"
    return None, None


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "null", "none", "nan"} else text


def _catalog_identity(row: dict[str, Any]) -> dict[str, str]:
    return {key: _clean_value(row.get(key)) for key in ("doc_id", "sha256", "file_name", "title")}


def _duplicate_report(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    report: dict[str, list[dict[str, Any]]] = {}
    for key in ("doc_id", "sha256", "file_name", "title"):
        seen: dict[str, int] = {}
        duplicates: list[dict[str, Any]] = []
        for row_index, row in enumerate(rows, start=1):
            value = norm_text(row.get(key)) if key == "title" else _clean_value(row.get(key))
            if not value:
                continue
            if value in seen:
                duplicates.append({"value": value, "first_row": seen[value], "duplicate_row": row_index})
            else:
                seen[value] = row_index
        if duplicates:
            report[key] = duplicates[:20]
    return report


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    return host not in {"example.com", "example.org", "example.net", "localhost"} and not host.endswith(".invalid")


def _looks_like_date(value: str) -> bool:
    return bool(__import__("re").match(r"^\d{4}-\d{2}-\d{2}$", value))


def _review_issues(row: dict[str, Any], row_index: int) -> list[dict[str, Any]]:
    has_source = bool(_clean_value(row.get("source_url")) or _clean_value(row.get("attachment_url")))
    status = _clean_value(row.get("version_status"))
    claims_authority = has_source or status in {"current", "superseded", "not_applicable"}
    if not claims_authority:
        return []
    proof_type = _clean_value(row.get("proof_type"))
    manual_proof = proof_type == "manual_review" or not proof_type
    required = ["reviewed_by", "reviewed_at"] if manual_proof else ["proof_type", "verification_method", "verified_at", "proof_evidence"]
    if has_source:
        required.append("source_evidence")
    if status in {"current", "superseded", "not_applicable"}:
        required.append("version_evidence")
    if status == "not_applicable":
        required.append("period")
    return [
        {"row_index": row_index, "field": field, "issue": "required_for_authority_claim"}
        for field in required
        if not _clean_value(row.get(field))
    ]
