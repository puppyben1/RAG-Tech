from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .eval_acceptance import load_acceptance_report
from .utils import ensure_dir, read_jsonl


def build_competition_readiness(
    *,
    kb_stats_path: Path,
    kb_errors_path: Path,
    path_audit_path: Path,
    metadata_path: Path,
    doc_quality_path: Path,
    sensitive_audit_path: Path,
    holdout_manifest_path: Path,
    acceptance_report_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    kb_stats = _read_json(kb_stats_path, {})
    kb_errors = _read_json(kb_errors_path, None)
    path_audit = _read_json(path_audit_path, {})
    metadata = read_jsonl(metadata_path) if metadata_path.is_file() else []
    doc_quality = _read_json(doc_quality_path, {})
    sensitive = _read_json(sensitive_audit_path, {})
    holdout = _read_json(holdout_manifest_path, {})
    acceptance = load_acceptance_report(acceptance_report_path)

    gates = {
        "reproducibility": _reproducibility_gate(kb_stats, kb_errors, path_audit),
        "source_and_version": _source_gate(metadata),
        "legacy_doc_quality": _artifact_gate(doc_quality, "doc_quality_report_missing"),
        "sensitive_information": _artifact_gate(sensitive, "sensitive_audit_report_missing"),
        "independent_holdout": _holdout_gate(holdout),
        "final_acceptance": _acceptance_gate(acceptance),
    }
    blocked = [name for name, gate in gates.items() if gate["status"] != "passed"]
    payload = {
        "schema_version": "competition_readiness_v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "passed" if not blocked else "blocked",
        "ready_for_competition_claim": not blocked,
        "blocked_gates": blocked,
        "gates": gates,
    }
    ensure_dir(output_path.parent)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _reproducibility_gate(kb: dict[str, Any], errors: Any, paths: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    documents = int(kb.get("documents") or 0)
    processed = int(kb.get("processed_documents") or 0)
    error_count = int(kb.get("error_count") or 0)
    if documents < 500:
        reasons.append("knowledge_base_below_500_documents")
    if processed != documents:
        reasons.append("not_all_documents_processed")
    if error_count or not isinstance(errors, list) or errors:
        reasons.append("knowledge_base_build_errors")
    if paths.get("status") != "passed" or int(paths.get("issue_count") or 0):
        reasons.append("path_audit_not_passed")
    return _gate(reasons, documents=documents, processed_documents=processed, error_count=error_count)


def _source_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    complete = []
    for row in rows:
        status = str(row.get("version_status") or "unknown").lower()
        version_complete = (status == "current" and bool(row.get("effective_date"))) or (
            status == "not_applicable" and bool(row.get("period"))
        )
        if row.get("source_url") and row.get("attachment_url") and version_complete:
            complete.append(str(row.get("doc_id") or ""))
    total = len(rows)
    missing = total - len(complete)
    reasons = []
    if total < 500:
        reasons.append("metadata_below_500_documents")
    if missing:
        reasons.append(f"source_or_version_incomplete:{missing}")
    return _gate(
        reasons,
        documents=total,
        complete_documents=len(complete),
        incomplete_documents=missing,
        coverage=len(complete) / total if total else 0,
    )


def _artifact_gate(payload: dict[str, Any], missing_reason: str) -> dict[str, Any]:
    if not payload:
        return _gate([missing_reason])
    reasons = list(payload.get("gate_reasons") or [])
    if payload.get("gate") != "passed" and not reasons:
        reasons.append("artifact_gate_not_passed")
    return _gate(reasons, artifact_gate=payload.get("gate"), summary=_summary(payload))


def _holdout_gate(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return _gate(["holdout_manifest_missing"])
    reasons = list(payload.get("gate_reasons") or [])
    if payload.get("gate") != "ready_for_evaluation" and not reasons:
        reasons.append("holdout_not_ready")
    return _gate(reasons, artifact_gate=payload.get("gate"), holdout_cases=(payload.get("holdout") or {}).get("case_count"))


def _acceptance_gate(payload: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if not payload.get("available"):
        reasons.append("final_acceptance_report_missing")
    elif not payload.get("final_passed"):
        reasons.extend(payload.get("stale_reasons") or ["final_acceptance_not_passed"])
    latency_gate = payload.get("latency_gate") or {}
    if payload.get("available") and latency_gate.get("status") != "passed":
        reasons.append(str(latency_gate.get("reason") or "latency_not_passed"))
    return _gate(reasons, report_status=payload.get("report_status"), final_passed=bool(payload.get("final_passed")), latency_gate=latency_gate)


def _gate(reasons: list[str], **details: Any) -> dict[str, Any]:
    unique = sorted(set(str(reason) for reason in reasons if reason))
    return {"status": "passed" if not unique else "blocked", "reasons": unique, **details}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "documents",
        "machine_passed",
        "machine_failed",
        "manual_review_pending",
        "records_scanned",
        "candidate_count",
        "confirmed_sensitive_count",
        "unresolved_count",
    )
    return {key: payload[key] for key in keys if key in payload}


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

