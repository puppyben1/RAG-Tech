"""Small, deterministic source/version governance rules."""

from __future__ import annotations

from collections import Counter
from typing import Any


VERSION_STATUSES = frozenset({"current", "superseded", "unknown", "not_applicable"})
TRUST_POLICY_VERSION = "P0-C-20260807"


def normalize_version_status(value: Any) -> str:
    status = str(value or "unknown").strip().lower()
    return status if status in VERSION_STATUSES else "unknown"


def evidence_authority(item: dict[str, Any]) -> dict[str, Any]:
    status = normalize_version_status(item.get("version_status"))
    has_source = bool(item.get("source_url") or item.get("attachment_url"))
    eligible = has_source and status in {"current", "not_applicable"}
    return {
        "version_status": status,
        "has_official_source": has_source,
        "authoritative": eligible,
        "reason": "eligible" if eligible else "missing_source_or_confirmed_version",
    }


def assess_evidence_authority(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = [evidence_authority(item) for item in evidence]
    authoritative_count = sum(1 for item in decisions if item["authoritative"])
    return {
        "authoritative": bool(decisions) and authoritative_count == len(decisions),
        "authoritative_count": authoritative_count,
        "evidence_count": len(decisions),
        "status_counts": dict(Counter(item["version_status"] for item in decisions)),
        "decisions": decisions,
    }


def audit_version_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    doc_ids = {str(row.get("doc_id")) for row in rows if row.get("doc_id")}
    invalid_statuses = []
    dangling = []
    self_relations = []
    for row in rows:
        doc_id = str(row.get("doc_id") or "")
        raw_status = str(row.get("version_status") or "unknown").strip().lower()
        if raw_status not in VERSION_STATUSES:
            invalid_statuses.append({"doc_id": doc_id, "value": raw_status})
        for field in ("supersedes_doc_id", "superseded_by_doc_id"):
            target = row.get(field)
            if not target:
                continue
            if str(target) == doc_id:
                self_relations.append({"doc_id": doc_id, "field": field})
            elif str(target) not in doc_ids:
                dangling.append({"doc_id": doc_id, "field": field, "target_doc_id": target})
    return {
        "documents": len(rows),
        "invalid_status_count": len(invalid_statuses),
        "invalid_statuses": invalid_statuses,
        "dangling_relation_count": len(dangling),
        "dangling_relations": dangling,
        "self_relation_count": len(self_relations),
        "self_relations": self_relations,
        "status_counts": dict(Counter(normalize_version_status(row.get("version_status")) for row in rows)),
    }
