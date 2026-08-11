from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .ask import ask
from .config import REPORTS_DIR, TRUSTED_EVAL_PATH, TRUSTED_EVAL_REPORT, TRUSTED_EVAL_SUMMARY_REPORT
from .eval_provenance import assess_freshness, build_provenance
from .path_refs import ProjectPathError, to_project_ref
from .utils import ensure_dir, norm_text, read_jsonl


REFUSAL_TEXT = "无法根据当前资料确定"
TRUSTED_CASE_TYPES = ("open_fact", "table_lookup", "refusal", "compliance_judgement", "text_then_table", "multi_hop")
TRUSTED_REPORT_NAMES = {
    "open_fact": "trusted_eval_open_fact.json",
    "table_lookup": "trusted_eval_table.json",
    "refusal": "trusted_eval_refusal.json",
    "compliance_judgement": "trusted_eval_compliance.json",
    "text_then_table": "trusted_eval_text_then_table.json",
    "multi_hop": "trusted_eval_multi_hop.json",
}


def evaluate_trusted(
    eval_path: Path = TRUSTED_EVAL_PATH,
    report_path: Path = TRUSTED_EVAL_REPORT,
    limit: int | None = None,
    case_type: str | None = None,
) -> dict[str, Any]:
    cases = read_jsonl(eval_path)
    if case_type:
        cases = [case for case in cases if case.get("type") == case_type]
    if limit is not None:
        cases = cases[:limit]
    details = [_evaluate_case(case) for case in cases]
    summary = _summarize(details, report_path)
    payload = {"schema_version": "2.0", "provenance": build_provenance(eval_path), "summary": summary, "details": details}
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def evaluate_trusted_by_type(
    eval_path: Path = TRUSTED_EVAL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    summaries: dict[str, dict[str, Any]] = {}
    for case_type in TRUSTED_CASE_TYPES:
        report_path = _trusted_report_path(reports_dir, case_type)
        summaries[case_type] = evaluate_trusted(eval_path=eval_path, report_path=report_path, case_type=case_type)
    return write_trusted_summary_report(summaries=summaries, eval_path=eval_path)


def write_trusted_summary_report(
    summaries: dict[str, dict[str, Any]] | None = None,
    report_path: Path = TRUSTED_EVAL_SUMMARY_REPORT,
    reports_dir: Path = REPORTS_DIR,
    eval_path: Path = TRUSTED_EVAL_PATH,
) -> dict[str, Any]:
    stale_sources: list[str] = []
    if summaries is None:
        summaries, stale_sources = _load_type_summaries(reports_dir)
    total = sum(int(summary.get("total", 0)) for summary in summaries.values())
    passed = sum(int(summary.get("passed", 0)) for summary in summaries.values())
    by_type = {
        case_type: {
            "total": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "accuracy": summary.get("accuracy", 0),
            "report_path": summary.get("report_path"),
        }
        for case_type, summary in summaries.items()
    }
    payload = {
        "schema_version": "2.0",
        "provenance": build_provenance(eval_path),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0,
        "by_type": by_type,
        "report_path": to_project_ref(report_path),
    }
    if stale_sources:
        payload["stale"] = True
        payload["stale_reasons"] = [f"source_report_stale:{case_type}" for case_type in stale_sources]
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_trusted_report(case_type: str = "summary", reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    if case_type == "summary":
        path = reports_dir / TRUSTED_EVAL_SUMMARY_REPORT.name
    else:
        path = _trusted_report_path(reports_dir, case_type)
    if not path.exists():
        return {"available": False, "case_type": case_type, "report_path": to_project_ref(path), "message": "trusted eval report not found"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"available": False, "case_type": case_type, "report_path": to_project_ref(path), "message": "trusted eval report is invalid"}
    payload = _sanitize_report_paths(payload, reports_dir)
    freshness = assess_freshness(payload, TRUSTED_EVAL_PATH)
    return {"available": True, "case_type": case_type, **payload, **freshness}


def _sanitize_report_paths(value: Any, reports_dir: Path) -> Any:
    if isinstance(value, list):
        return [_sanitize_report_paths(item, reports_dir) for item in value]
    if not isinstance(value, dict):
        return value
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key == "report_path" and isinstance(item, str):
            candidate = reports_dir / Path(item.replace("\\", "/")).name
            try:
                cleaned[key] = to_project_ref(candidate)
            except ProjectPathError:
                cleaned[key] = None
        else:
            cleaned[key] = _sanitize_report_paths(item, reports_dir)
    return cleaned


def _load_type_summaries(reports_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    summaries: dict[str, dict[str, Any]] = {}
    stale_sources: list[str] = []
    for case_type in TRUSTED_CASE_TYPES:
        path = _trusted_report_path(reports_dir, case_type)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        summaries[case_type] = payload.get("summary", {})
        if assess_freshness(payload, TRUSTED_EVAL_PATH)["stale"]:
            stale_sources.append(case_type)
    return summaries, stale_sources


def _trusted_report_path(reports_dir: Path, case_type: str) -> Path:
    return reports_dir / TRUSTED_REPORT_NAMES.get(case_type, f"trusted_eval_{case_type}.json")


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = ask(question=case["question"])
    response_dict = asdict(response)
    evidence = response.evidence or []
    failure_reasons: list[str] = []

    expected_routes = _expected_routes(case)
    if expected_routes and response.route not in expected_routes:
        failure_reasons.append("route_mismatch")

    if case.get("answerable") is False:
        if response.route != "rag_refusal":
            failure_reasons.append("expected_refusal")
        if REFUSAL_TEXT not in _answer_blob(response_dict):
            failure_reasons.append("refusal_text_missing")
    elif response.route == "rag_refusal":
        failure_reasons.append("unexpected_refusal")

    expected_doc_ids = _expected_doc_ids(case)
    evidence_doc_ids = [str(item.get("doc_id")) for item in evidence if item.get("doc_id")]
    citation_doc_hit = not expected_doc_ids or set(expected_doc_ids).issubset(evidence_doc_ids)
    if not citation_doc_hit:
        failure_reasons.append("evidence_doc_mismatch")

    expected_evidence_types = _expected_evidence_types(case)
    evidence_types = [str(item.get("evidence_type")) for item in evidence if item.get("evidence_type")]
    citation_type_hit = not expected_evidence_types or set(expected_evidence_types).issubset(evidence_types)
    if not citation_type_hit:
        failure_reasons.append("evidence_type_mismatch")

    answer_blob = _answer_blob(response_dict)
    must_contain_missing = _missing_terms(case.get("must_contain") or [], answer_blob)
    if must_contain_missing:
        failure_reasons.append("must_contain_missing")

    critical_entity_errors = _missing_terms(case.get("critical_entities") or [], answer_blob)
    if critical_entity_errors:
        failure_reasons.append("critical_entity_error")

    locator_hit = _gold_evidence_hit(case.get("gold_evidence") or [], evidence)
    if not locator_hit:
        failure_reasons.append("evidence_locator_mismatch")

    missing_fields = _missing_required_fields(case, response_dict)
    if missing_fields:
        failure_reasons.append("missing_required_fields")

    unsupported_types = {"compliance_judgement", "text_then_table", "multi_hop"}
    if case.get("type") in unsupported_types and response.route not in expected_routes:
        failure_reasons.append("unsupported_task_type")

    answer_failure_reasons = {
        "route_mismatch",
        "unexpected_refusal",
        "must_contain_missing",
        "critical_entity_error",
        "missing_required_fields",
        "unsupported_task_type",
    }
    refusal_failure_reasons = {"route_mismatch", "expected_refusal", "refusal_text_missing"}

    return {
        "id": case.get("id"),
        "type": case.get("type"),
        "category": case.get("category"),
        "answerable": case.get("answerable") is not False,
        "question": case.get("question"),
        "passed": not failure_reasons,
        "answer_correct": not bool(set(failure_reasons) & answer_failure_reasons),
        "refusal_correct": case.get("answerable") is False
        and not bool(set(failure_reasons) & refusal_failure_reasons),
        "failure_reasons": sorted(set(failure_reasons)),
        "expected_routes": expected_routes,
        "actual_route": response.route,
        "confidence": response.confidence,
        "answer_text": str(response.answer_text or "")[:500],
        "must_contain_missing": must_contain_missing,
        "critical_entities": list(case.get("critical_entities") or []),
        "critical_entity_errors": critical_entity_errors,
        "expected_doc_ids": expected_doc_ids,
        "evidence_doc_ids": evidence_doc_ids,
        "expected_evidence_types": expected_evidence_types,
        "evidence_types": evidence_types,
        "citation_hit": citation_doc_hit and citation_type_hit and locator_hit,
        "evidence_locator_hit": locator_hit,
        "required_fields": case.get("required_fields") or [],
        "missing_required_fields": missing_fields,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _summarize(details: list[dict[str, Any]], report_path: Path) -> dict[str, Any]:
    total = len(details)
    passed = sum(1 for item in details if item["passed"])
    by_type: dict[str, dict[str, Any]] = {}
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in details:
        buckets[str(item.get("type") or "unknown")].append(item)
    for case_type, rows in sorted(buckets.items()):
        type_total = len(rows)
        type_passed = sum(1 for row in rows if row["passed"])
        by_type[case_type] = {
            "total": type_total,
            "passed": type_passed,
            "failed": type_total - type_passed,
            "accuracy": type_passed / type_total if type_total else 0,
        }

    failure_counter: Counter[str] = Counter()
    for item in details:
        failure_counter.update(item["failure_reasons"])
    latencies = sorted(float(item.get("latency_ms", 0)) for item in details)

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0,
        "by_type": by_type,
        "by_failure_reason": dict(sorted(failure_counter.items())),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else 0,
        },
        "report_path": to_project_ref(report_path),
    }


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, int((len(values) - 1) * quantile)))
    return round(values[index], 2)


def _expected_routes(case: dict[str, Any]) -> list[str]:
    if case.get("expected_routes"):
        return list(case["expected_routes"])
    if case.get("expected_route"):
        return [str(case["expected_route"])]
    return []


def _expected_doc_ids(case: dict[str, Any]) -> list[str]:
    if case.get("expected_doc_ids"):
        return list(case["expected_doc_ids"])
    if case.get("expected_doc_id"):
        return [str(case["expected_doc_id"])]
    return []


def _expected_evidence_types(case: dict[str, Any]) -> list[str]:
    if case.get("expected_evidence_types"):
        return list(case["expected_evidence_types"])
    if case.get("expected_evidence_type"):
        return [str(case["expected_evidence_type"])]
    return []


def _missing_terms(terms: list[str], text: str) -> list[str]:
    blob = norm_text(text)
    return [str(term) for term in terms if norm_text(term) not in blob]


def _gold_evidence_hit(gold: list[dict[str, Any]], actual: list[dict[str, Any]]) -> bool:
    if not gold:
        return True
    return all(any(_evidence_matches(expected, item) for item in actual) for expected in gold)


def _evidence_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    if str(expected.get("doc_id") or "") != str(actual.get("doc_id") or ""):
        return False
    position = actual.get("position") if isinstance(actual.get("position"), dict) else {}
    if expected.get("page_no") is not None:
        return str(expected["page_no"]) == str(position.get("page_no") or actual.get("page_no") or "")
    if expected.get("article_no"):
        return norm_text(expected["article_no"]) == norm_text(position.get("article_no") or actual.get("article_no"))
    if expected.get("sheet_name") and expected.get("cell_ref"):
        actual_sheet = actual.get("sheet_name") or position.get("sheet_name")
        actual_cells = actual.get("cell_refs") or position.get("cell_refs") or []
        if actual.get("cell_ref"):
            actual_cells = [actual.get("cell_ref"), *actual_cells]
        return norm_text(expected["sheet_name"]) == norm_text(actual_sheet) and str(expected["cell_ref"]) in {
            str(value) for value in actual_cells
        }
    return False


def _answer_blob(response: dict[str, Any]) -> str:
    return " ".join(
        [
            json.dumps(response.get("answer") or "", ensure_ascii=False),
            str(response.get("answer_text") or ""),
        ]
    )


def _missing_required_fields(case: dict[str, Any], response: dict[str, Any]) -> list[str]:
    required_fields = case.get("required_fields") or []
    if not required_fields:
        return []
    debug_payload: dict[str, Any] = {}
    debug = response.get("debug")
    if isinstance(debug, str) and debug:
        try:
            debug_payload = json.loads(debug)
        except json.JSONDecodeError:
            debug_payload = {}
    answer_payload = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    missing: list[str] = []
    for field in required_fields:
        if response.get(field) is None and debug_payload.get(field) is None and answer_payload.get(field) is None:
            missing.append(str(field))
    return missing
