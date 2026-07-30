from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .ask import ask
from .config import REPORTS_DIR, TRUSTED_EVAL_PATH, TRUSTED_EVAL_REPORT, TRUSTED_EVAL_SUMMARY_REPORT
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
    payload = {"summary": summary, "details": details}
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
    return write_trusted_summary_report(summaries=summaries)


def write_trusted_summary_report(
    summaries: dict[str, dict[str, Any]] | None = None,
    report_path: Path = TRUSTED_EVAL_SUMMARY_REPORT,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    if summaries is None:
        summaries = _load_type_summaries(reports_dir)
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
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0,
        "by_type": by_type,
        "report_path": str(report_path),
    }
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_trusted_report(case_type: str = "summary", reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    if case_type == "summary":
        path = TRUSTED_EVAL_SUMMARY_REPORT
    else:
        path = _trusted_report_path(reports_dir, case_type)
    if not path.exists():
        return {"available": False, "case_type": case_type, "report_path": str(path), "message": "trusted eval report not found"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"available": True, "case_type": case_type, **payload}


def _load_type_summaries(reports_dir: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for case_type in TRUSTED_CASE_TYPES:
        path = _trusted_report_path(reports_dir, case_type)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        summaries[case_type] = payload.get("summary", {})
    return summaries


def _trusted_report_path(reports_dir: Path, case_type: str) -> Path:
    return reports_dir / TRUSTED_REPORT_NAMES.get(case_type, f"trusted_eval_{case_type}.json")


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
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
    if expected_doc_ids and not any(item.get("doc_id") in expected_doc_ids for item in evidence):
        failure_reasons.append("evidence_doc_mismatch")

    expected_evidence_types = _expected_evidence_types(case)
    if expected_evidence_types and not any(item.get("evidence_type") in expected_evidence_types for item in evidence):
        failure_reasons.append("evidence_type_mismatch")

    if not _contains_all(case.get("must_contain") or [], response_dict):
        failure_reasons.append("must_contain_missing")

    missing_fields = _missing_required_fields(case, response_dict)
    if missing_fields:
        failure_reasons.append("missing_required_fields")

    unsupported_types = {"compliance_judgement", "text_then_table", "multi_hop"}
    if case.get("type") in unsupported_types and response.route not in expected_routes:
        failure_reasons.append("unsupported_task_type")

    return {
        "id": case.get("id"),
        "type": case.get("type"),
        "question": case.get("question"),
        "passed": not failure_reasons,
        "failure_reasons": sorted(set(failure_reasons)),
        "expected_routes": expected_routes,
        "actual_route": response.route,
        "confidence": response.confidence,
        "answer_text": str(response.answer_text or "")[:500],
        "expected_doc_ids": expected_doc_ids,
        "evidence_doc_ids": [item.get("doc_id") for item in evidence],
        "expected_evidence_types": expected_evidence_types,
        "evidence_types": [item.get("evidence_type") for item in evidence],
        "required_fields": case.get("required_fields") or [],
        "missing_required_fields": missing_fields,
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

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0,
        "by_type": by_type,
        "by_failure_reason": dict(sorted(failure_counter.items())),
        "report_path": str(report_path),
    }


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


def _contains_all(terms: list[str], response: dict[str, Any]) -> bool:
    blob = norm_text(
        " ".join(
            [
                _answer_blob(response),
                json.dumps(response.get("evidence") or [], ensure_ascii=False),
            ]
        )
    )
    return all(norm_text(term) in blob for term in terms)


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
