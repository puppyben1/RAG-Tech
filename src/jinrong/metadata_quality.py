from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DOCUMENT_METADATA_PATH, METADATA_QUALITY_REPORT, SQLITE_DB_PATH
from .db.schema import connect, init_db
from .utils import ensure_dir, read_jsonl


AUDIT_FIELDS = ("publisher", "publish_date", "doc_no", "source_url", "attachment_url", "column")


def build_metadata_quality_report(
    metadata_path: Path = DOCUMENT_METADATA_PATH,
    report_path: Path = METADATA_QUALITY_REPORT,
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
    total = len(rows)
    by_source_type = _coverage_by_group(rows, "source_type")
    by_business_domain = _coverage_by_group(rows, "business_domain")
    missing_samples = {
        field: [
            {
                "doc_id": row.get("doc_id"),
                "title": row.get("title"),
                "source_type": row.get("source_type"),
                "business_domain": row.get("business_domain"),
            }
            for row in rows
            if not row.get(field)
        ][:20]
        for field in AUDIT_FIELDS
    }
    field_coverage = {
        field: {
            "filled": filled,
            "missing": total - filled,
            "coverage": filled / total if total else 0,
        }
        for field in AUDIT_FIELDS
        for filled in [sum(1 for row in rows if row.get(field))]
    }
    return {
        "report_path": str(report_path),
        "created_at": _now(),
        "documents": total,
        "field_coverage": field_coverage,
        "by_source_type": by_source_type,
        "by_business_domain": by_business_domain,
        "missing_samples": missing_samples,
        "source_type_counts": dict(Counter(row.get("source_type") or "unknown" for row in rows)),
        "business_domain_counts": dict(Counter(row.get("business_domain") or "unknown" for row in rows)),
        "recommendations": _recommendations(field_coverage),
    }


def _coverage_by_group(rows: list[dict[str, Any]], group_field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_field) or "unknown")].append(row)
    result: dict[str, Any] = {}
    for group, group_rows in sorted(groups.items()):
        total = len(group_rows)
        result[group] = {
            "documents": total,
            "fields": {
                field: {
                    "filled": filled,
                    "missing": total - filled,
                    "coverage": filled / total if total else 0,
                }
                for field in AUDIT_FIELDS
                for filled in [sum(1 for row in group_rows if row.get(field))]
            },
        }
    return result


def _recommendations(field_coverage: dict[str, dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    if field_coverage["source_url"]["coverage"] < 0.8:
        recommendations.append("优先补齐 source_url/attachment_url；当前来源追溯字段覆盖不足。")
    if field_coverage["publish_date"]["coverage"] < 0.5:
        recommendations.append("增强发布日期抽取，建议结合来源页面发布日期和正文日期规则。")
    if field_coverage["doc_no"]["coverage"] < 0.5:
        recommendations.append("增强文号抽取，覆盖 金规/银保监规/银监发/财会 等常见格式。")
    if field_coverage["publisher"]["coverage"] < 0.8:
        recommendations.append("增强发文机关抽取，优先处理标题中的联合发文机关。")
    return recommendations


def _store_report(report: dict[str, Any], db_path: Path) -> None:
    report_id = f"metadata_quality_{uuid.uuid4().hex[:12]}"
    fields = report["field_coverage"]
    with connect(db_path) as conn:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO metadata_quality_reports(
              report_id, created_at, report_path, documents,
              publisher_filled, publish_date_filled, doc_no_filled,
              source_url_filled, attachment_url_filled, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report["created_at"],
                report["report_path"],
                report["documents"],
                fields["publisher"]["filled"],
                fields["publish_date"]["filled"],
                fields["doc_no"]["filled"],
                fields["source_url"]["filled"],
                fields["attachment_url"]["filled"],
                json.dumps(report, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
