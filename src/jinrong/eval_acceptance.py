from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import FINAL_ACCEPTANCE_REPORT, PROJECT_ROOT
from .eval_provenance import add_eval_provenance, assess_eval_freshness
from .eval_trusted import evaluate_trusted
from .path_refs import ProjectPathError, to_project_ref
from .utils import ensure_dir, read_jsonl


THRESHOLDS = {
    "institutional_fact_accuracy": (">=", 0.85),
    "table_lookup_accuracy": (">=", 0.80),
    "citation_hit_rate": (">=", 0.90),
    "critical_entity_error_rate": ("<=", 0.05),
    "refusal_success_rate": (">=", 0.80),
}


def load_acceptance_report(report_path: Path = FINAL_ACCEPTANCE_REPORT) -> dict[str, Any]:
    if not report_path.is_file():
        return {
            "available": False,
            "report_path": _project_ref_or_none(report_path),
            "message": "final acceptance report not found",
            "final_passed": False,
        }
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "report_path": _project_ref_or_none(report_path),
            "message": f"invalid final acceptance report: {exc}",
            "final_passed": False,
        }
    reasons: list[str] = []
    eval_path = _resolve_project_ref((payload.get("evaluation_dataset_fingerprint") or {}).get("path"))
    if eval_path is None:
        reasons.append("evaluation_dataset_not_project_relative")
    else:
        reasons.extend(assess_eval_freshness(payload, eval_path)["stale_reasons"])
    manifest_fingerprint = payload.get("holdout_manifest_fingerprint") or {}
    manifest_path = _resolve_project_ref(manifest_fingerprint.get("path"))
    if manifest_path is None:
        reasons.append("holdout_manifest_not_project_relative")
    elif _sha256(manifest_path) != manifest_fingerprint.get("sha256"):
        reasons.append("holdout_manifest_fingerprint_mismatch")
    if payload.get("holdout_gate") != "ready_for_evaluation":
        reasons.append("holdout_gate_not_ready")
    reasons = sorted(set(reasons))
    stale = bool(reasons)
    final_passed = payload.get("status") == "passed" and not stale
    return {
        "available": True,
        **payload,
        "stale": stale,
        "stale_reasons": reasons,
        "current": not stale,
        "report_status": "stale" if stale else str(payload.get("status") or "unknown"),
        "final_passed": final_passed,
    }


def run_acceptance(
    eval_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    max_p95_ms: float | None = None,
) -> dict[str, Any]:
    if max_p95_ms is not None and max_p95_ms <= 0:
        raise ValueError("max_p95_ms must be positive")
    manifest = validate_acceptance_inputs(eval_path, manifest_path)
    details_path = output_path.with_name(f"{output_path.stem}_details.json")
    evaluate_trusted(eval_path=eval_path, report_path=details_path)
    trusted_payload = json.loads(details_path.read_text(encoding="utf-8"))
    cases = read_jsonl(eval_path)
    details = list(trusted_payload.get("details") or [])
    metrics = build_acceptance_metrics(cases, details)
    quality_passed = all(metric["passed"] for metric in metrics.values())
    latency = trusted_payload.get("summary", {}).get("latency_ms", {})
    latency_gate = build_latency_gate(latency, max_p95_ms)
    checks_passed = quality_passed and latency_gate["passed"]
    payload = add_eval_provenance(
        {
            "acceptance_run_id": str(uuid.uuid4()),
            "status": "passed" if checks_passed else "failed",
            "holdout_gate": manifest["gate"],
            "holdout_manifest_fingerprint": _fingerprint(manifest_path),
            "holdout_case_count": len(cases),
            "quality_status": "passed" if quality_passed else "failed",
            "metrics": metrics,
            "latency_ms": latency,
            "latency_gate": latency_gate,
            "details_report": _project_ref_or_none(details_path),
            "details_report_status": _path_status(details_path),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        eval_path,
    )
    ensure_dir(output_path.parent)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_latency_gate(latency: dict[str, Any], max_p95_ms: float | None) -> dict[str, Any]:
    raw_p95 = latency.get("p95")
    try:
        p95_ms = float(raw_p95)
    except (TypeError, ValueError):
        p95_ms = None
    if max_p95_ms is None:
        return {
            "status": "unverified",
            "passed": False,
            "p95_ms": p95_ms,
            "max_p95_ms": None,
            "reason": "platform_latency_threshold_not_configured",
        }
    passed = p95_ms is not None and p95_ms <= max_p95_ms
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "p95_ms": p95_ms,
        "max_p95_ms": max_p95_ms,
        "reason": None if passed else "p95_latency_exceeds_threshold" if p95_ms is not None else "missing_p95_latency",
    }


def validate_acceptance_inputs(eval_path: Path, manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ValueError("holdout manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("gate") != "ready_for_evaluation":
        reasons = ",".join(str(value) for value in manifest.get("gate_reasons") or [])
        raise ValueError(f"holdout gate is not ready_for_evaluation: {reasons or 'unknown'}")
    expected_sha = str((manifest.get("holdout") or {}).get("sha256") or "")
    actual_sha = _sha256(eval_path)
    if not expected_sha or expected_sha != actual_sha:
        raise ValueError("holdout dataset fingerprint does not match freeze manifest")
    return manifest


def build_acceptance_metrics(cases: list[dict[str, Any]], details: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    detail_by_id = {str(row.get("id")): row for row in details}
    if len(detail_by_id) != len(cases) or any(str(case.get("id")) not in detail_by_id for case in cases):
        raise ValueError("trusted evaluation details do not match holdout cases")
    fact_rows = [detail_by_id[str(case["id"])] for case in cases if case.get("answerable") is not False and case.get("type") != "table_lookup"]
    table_rows = [detail_by_id[str(case["id"])] for case in cases if case.get("answerable") is not False and case.get("type") == "table_lookup"]
    citation_rows = [detail_by_id[str(case["id"])] for case in cases if case.get("answerable") is not False]
    refusal_rows = [detail_by_id[str(case["id"])] for case in cases if case.get("answerable") is False]
    entity_total = sum(len(row.get("critical_entities") or []) for row in citation_rows)
    entity_errors = sum(len(row.get("critical_entity_errors") or []) for row in citation_rows)
    return {
        "institutional_fact_accuracy": _rate_metric(sum(bool(row.get("answer_correct")) for row in fact_rows), len(fact_rows), *THRESHOLDS["institutional_fact_accuracy"]),
        "table_lookup_accuracy": _rate_metric(sum(bool(row.get("answer_correct")) for row in table_rows), len(table_rows), *THRESHOLDS["table_lookup_accuracy"]),
        "citation_hit_rate": _rate_metric(sum(bool(row.get("citation_hit")) for row in citation_rows), len(citation_rows), *THRESHOLDS["citation_hit_rate"]),
        "critical_entity_error_rate": _rate_metric(entity_errors, entity_total, *THRESHOLDS["critical_entity_error_rate"]),
        "refusal_success_rate": _rate_metric(sum(bool(row.get("refusal_correct")) for row in refusal_rows), len(refusal_rows), *THRESHOLDS["refusal_success_rate"]),
    }


def _rate_metric(numerator: int, denominator: int, operator: str, threshold: float) -> dict[str, Any]:
    value = numerator / denominator if denominator else None
    passed = value is not None and (value >= threshold if operator == ">=" else value <= threshold)
    return {
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "operator": operator,
        "threshold": threshold,
        "passed": passed,
    }


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(path: Path) -> dict[str, Any]:
    return {
        "path": _project_ref_or_none(path),
        "path_status": _path_status(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _project_ref_or_none(path: Path) -> str | None:
    try:
        return to_project_ref(path, PROJECT_ROOT)
    except ProjectPathError:
        return None


def _path_status(path: Path) -> str:
    return "project_relative" if _project_ref_or_none(path) else "external_input"


def _resolve_project_ref(value: Any) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    candidate = (PROJECT_ROOT / Path(value)).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    return candidate
