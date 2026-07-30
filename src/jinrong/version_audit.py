from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DOCUMENT_METADATA_PATH, SQLITE_DB_PATH, VERSION_AUDIT_REPORT
from .db.schema import connect, init_db
from .utils import ensure_dir, read_jsonl


VERSION_FIELDS = (
    "version_status",
    "effective_date",
    "expiry_date",
    "version_group",
    "supersedes_doc_id",
    "superseded_by_doc_id",
)


def build_version_audit_report(
    metadata_path: Path = DOCUMENT_METADATA_PATH,
    report_path: Path = VERSION_AUDIT_REPORT,
    db_path: Path = SQLITE_DB_PATH,
    store_db: bool = True,
) -> dict[str, Any]:
    rows = read_jsonl(metadata_path)
    report = _build_report(rows, report_path)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if store_db:
        _store_report(report, db_path)
    return report


def _build_report(rows: list[dict[str, Any]], report_path: Path) -> dict[str, Any]:
    doc_ids = {str(row.get("doc_id")) for row in rows if row.get("doc_id")}
    status_counts = Counter(_version_status(row) for row in rows)
    field_coverage = _field_coverage(rows)
    dangling_relations = _dangling_relations(rows, doc_ids)
    self_relations = _self_relations(rows)
    group_issues = _version_group_issues(rows)
    relation_pairs = _relation_pairs(rows)

    return {
        "report_path": str(report_path),
        "created_at": _now(),
        "documents": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "current_count": status_counts.get("current", 0),
        "superseded_count": status_counts.get("superseded", 0),
        "unknown_count": status_counts.get("unknown", 0),
        "field_coverage": field_coverage,
        "dangling_relation_count": len(dangling_relations),
        "dangling_relations": dangling_relations[:50],
        "self_relation_count": len(self_relations),
        "self_relations": self_relations[:50],
        "group_issue_count": len(group_issues),
        "group_issues": group_issues[:50],
        "relation_pair_count": len(relation_pairs),
        "relation_pairs": relation_pairs[:50],
        "source_type_counts": dict(Counter(row.get("source_type") or "unknown" for row in rows)),
        "recommendations": _recommendations(status_counts, field_coverage, dangling_relations, group_issues),
    }


def _version_status(row: dict[str, Any]) -> str:
    status = str(row.get("version_status") or "").strip().lower()
    return status or "unknown"


def _field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    fields = ("source_url", "attachment_url", *VERSION_FIELDS)
    return {
        field: {
            "filled": filled,
            "missing": total - filled,
            "coverage": filled / total if total else 0,
        }
        for field in fields
        for filled in [sum(1 for row in rows if row.get(field))]
    }


def _dangling_relations(rows: list[dict[str, Any]], doc_ids: set[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        doc_id = row.get("doc_id")
        for field in ("supersedes_doc_id", "superseded_by_doc_id"):
            target = row.get(field)
            if target and str(target) not in doc_ids:
                issues.append(
                    {
                        "doc_id": doc_id,
                        "title": row.get("title"),
                        "field": field,
                        "target_doc_id": target,
                    }
                )
    return issues


def _self_relations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        doc_id = row.get("doc_id")
        if not doc_id:
            continue
        for field in ("supersedes_doc_id", "superseded_by_doc_id"):
            if row.get(field) == doc_id:
                issues.append({"doc_id": doc_id, "title": row.get("title"), "field": field})
    return issues


def _version_group_issues(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        group = str(row.get("version_group") or "").strip()
        if group:
            groups[group].append(row)

    issues: list[dict[str, Any]] = []
    for group, group_rows in sorted(groups.items()):
        if len(group_rows) <= 1:
            continue
        current_docs = [row.get("doc_id") for row in group_rows if _version_status(row) == "current"]
        if len(current_docs) > 1:
            issues.append({"version_group": group, "issue": "multiple_current", "current_doc_ids": current_docs})
        elif not current_docs:
            issues.append(
                {
                    "version_group": group,
                    "issue": "no_current",
                    "doc_ids": [row.get("doc_id") for row in group_rows],
                }
            )
    return issues


def _relation_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        doc_id = row.get("doc_id")
        if row.get("supersedes_doc_id"):
            pairs.append({"from_doc_id": doc_id, "relation": "supersedes", "to_doc_id": row["supersedes_doc_id"]})
        if row.get("superseded_by_doc_id"):
            pairs.append(
                {"from_doc_id": doc_id, "relation": "superseded_by", "to_doc_id": row["superseded_by_doc_id"]}
            )
    return pairs


def _recommendations(
    status_counts: Counter[str],
    field_coverage: dict[str, dict[str, Any]],
    dangling_relations: list[dict[str, Any]],
    group_issues: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    total = sum(status_counts.values())
    unknown = status_counts.get("unknown", 0)
    if total and unknown / total > 0.2:
        recommendations.append("优先补齐 version_status，至少区分 current、superseded、unknown，避免问答误用旧规。")
    if field_coverage["source_url"]["coverage"] < 0.8:
        recommendations.append("优先补齐 source_url 和 attachment_url，保证答案证据能回到来源页面与附件。")
    if field_coverage["version_group"]["coverage"] < 0.5:
        recommendations.append("为同一制度、同一统计报表序列补 version_group，支持新旧版本归并与 current 优先。")
    if dangling_relations:
        recommendations.append("修复 supersedes_doc_id/superseded_by_doc_id 中不存在的 doc_id。")
    if group_issues:
        recommendations.append("检查 version_group 内 current 标注，保证每个多版本组最多一个 current。")
    if not recommendations:
        recommendations.append("版本与来源标注未发现阻断问题，可进入 current 优先检索与旧规抑制验证。")
    return recommendations


def _store_report(report: dict[str, Any], db_path: Path) -> None:
    report_id = f"version_audit_{uuid.uuid4().hex[:12]}"
    with connect(db_path) as conn:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO version_audit_reports(
              report_id, created_at, report_path, documents,
              current_count, superseded_count, unknown_count,
              dangling_relation_count, group_issue_count, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report["created_at"],
                report["report_path"],
                report["documents"],
                report["current_count"],
                report["superseded_count"],
                report["unknown_count"],
                report["dangling_relation_count"],
                report["group_issue_count"],
                json.dumps(report, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
