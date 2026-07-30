from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import RETRIEVAL_EVAL_PATH, RETRIEVAL_EVAL_REPORT
from .services import search_evidence
from .utils import ensure_dir, norm_text, read_jsonl


def evaluate_retrieval(
    eval_path: Path = RETRIEVAL_EVAL_PATH,
    report_path: Path = RETRIEVAL_EVAL_REPORT,
    retrieval: str = "hybrid",
    rerank: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    cases = read_jsonl(eval_path)
    details = [_evaluate_case(case, retrieval=retrieval, rerank=rerank, top_k=top_k) for case in cases]
    total = len(details)
    top1 = sum(1 for row in details if row["top1_hit"])
    top3 = sum(1 for row in details if row["top3_hit"])
    topk = sum(1 for row in details if row["topk_hit"])
    summary = {
        "total": total,
        "retrieval": retrieval,
        "rerank": rerank,
        "top_k": top_k,
        "top1": top1,
        "top3": top3,
        "topk": topk,
        "top1_accuracy": top1 / total if total else 0,
        "top3_accuracy": top3 / total if total else 0,
        "topk_accuracy": topk / total if total else 0,
        "report_path": str(report_path),
    }
    payload = {"summary": summary, "details": details}
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _evaluate_case(case: dict[str, Any], retrieval: str, rerank: bool, top_k: int) -> dict[str, Any]:
    search = search_evidence(
        query=case["query"],
        source_type=case.get("source_type"),
        doc_id=case.get("doc_id_filter"),
        publisher=case.get("publisher"),
        business_domain=case.get("business_domain"),
        regulatory_topic=case.get("regulatory_topic"),
        doc_no=case.get("doc_no"),
        article_no=case.get("article_no"),
        retrieval=retrieval,
        rerank=rerank,
        top_k=top_k,
    )
    results = search.get("results", [])
    hits = [_is_hit(case, result) for result in results]
    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "expected_doc_ids": _expected_doc_ids(case),
        "top_doc_ids": [result.get("doc_id") for result in results],
        "top1_hit": bool(hits[:1] and hits[0]),
        "top3_hit": any(hits[:3]),
        "topk_hit": any(hits),
        "result_count": search.get("total", 0),
        "index": search.get("index"),
        "top_evidence_type": results[0].get("evidence_type") if results else None,
        "top_text": str(results[0].get("text", ""))[:300] if results else "",
    }


def _is_hit(case: dict[str, Any], result: dict[str, Any]) -> bool:
    expected_doc_ids = _expected_doc_ids(case)
    if expected_doc_ids and result.get("doc_id") not in expected_doc_ids:
        return False
    expected_type = case.get("expected_evidence_type")
    if expected_type and result.get("evidence_type") != expected_type:
        return False
    expected_contains = case.get("expected_contains") or []
    text = norm_text(
        " ".join(
            [
                str(result.get("source_title", "")),
                str(result.get("text", "")),
                str(result.get("position", "")),
                str(result.get("doc_no", "")),
                str(result.get("business_domain", "")),
            ]
        )
    )
    return all(norm_text(term) in text for term in expected_contains)


def _expected_doc_ids(case: dict[str, Any]) -> list[str]:
    if case.get("expected_doc_ids"):
        return list(case["expected_doc_ids"])
    if case.get("expected_doc_id"):
        return [case["expected_doc_id"]]
    return []
