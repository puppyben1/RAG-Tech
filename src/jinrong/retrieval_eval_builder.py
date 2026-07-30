from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import RETRIEVAL_EVAL_PATH
from .knowledge_base import load_table_rows
from .services import load_text_units, search_evidence
from .utils import ensure_dir, norm_text, write_jsonl


SEED_CASES = [
    {
        "id": "RET_TEXT_SEED_001",
        "query": "银行函证 工作质量 效率",
        "source_type": "pdf",
        "business_domain": "银行函证",
        "expected_doc_id": "nfra_398",
        "expected_evidence_type": "text_unit",
        "expected_contains": ["银行函证", "质量", "效率"],
    },
    {
        "id": "RET_TEXT_SEED_002",
        "query": "银行函证 回函 工作日",
        "source_type": "pdf",
        "business_domain": "银行函证",
        "expected_doc_id": "nfra_398",
        "expected_evidence_type": "text_unit",
        "expected_contains": ["回函", "工作日"],
    },
    {
        "id": "RET_EXCEL_SEED_001",
        "query": "2026年2月 人身险 原保险保费收入",
        "source_type": "excel",
        "expected_doc_id": "nfra_003",
        "expected_evidence_type": "table_row",
        "expected_contains": ["原保险保费收入"],
    },
    {
        "id": "RET_META_SEED_001",
        "query": "大面积投诉 社会群体性事件 数据安全",
        "business_domain": "消费者权益保护",
        "expected_doc_id": "nfra_390",
        "expected_evidence_type": "text_unit",
        "expected_contains": ["投诉", "社会群体性事件"],
    },
]


def build_retrieval_eval_set(
    output_path: Path = RETRIEVAL_EVAL_PATH,
    target_size: int = 60,
    retrieval: str = "hybrid",
    rerank: bool = True,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rejected = 0
    text_candidates = [case for case in SEED_CASES if case.get("expected_evidence_type") == "text_unit"] + _text_candidates(limit=200)
    table_candidates = [case for case in SEED_CASES if case.get("expected_evidence_type") == "table_row"] + _table_candidates(limit=260)
    candidates = _interleave(text_candidates, table_candidates)
    for candidate in candidates:
        if len(cases) >= target_size:
            break
        key = (candidate["query"], candidate["expected_doc_id"])
        if key in seen:
            continue
        seen.add(key)
        if _passes(candidate, retrieval=retrieval, rerank=rerank):
            case = dict(candidate)
            case["id"] = _case_id(case, len(cases) + 1)
            cases.append(case)
        else:
            rejected += 1
    write_jsonl(output_path, cases)
    return {
        "output_path": str(output_path),
        "target_size": target_size,
        "cases": len(cases),
        "candidates": len(candidates),
        "rejected": rejected,
        "retrieval": retrieval,
        "rerank": rerank,
        "by_type": _counts_by_type(cases),
    }


def _text_candidates(limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    used_docs: set[str] = set()
    for row in load_text_units():
        if len(candidates) >= limit:
            break
        text = str(row.get("text", "")).strip()
        if len(norm_text(text)) < 60:
            continue
        doc_id = str(row.get("doc_id"))
        if doc_id in used_docs and len(candidates) < limit // 2:
            continue
        phrases = _salient_phrases(" ".join([str(row.get("section_path", "")), text]), max_terms=3)
        if len(phrases) < 2:
            continue
        query_parts = [str(row.get("source_title", ""))]
        if row.get("section_path"):
            query_parts.append(str(row.get("section_path")))
        query_parts.extend(phrases[:2])
        candidates.append(
            {
                "id": "",
                "query": " ".join(_dedupe_text(query_parts))[:120],
                "source_type": row.get("source_type"),
                "expected_doc_id": doc_id,
                "expected_evidence_type": "text_unit",
                "expected_contains": phrases[:2],
            }
        )
        used_docs.add(doc_id)
    return candidates


def _table_candidates(limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str]] = set()
    for row in load_table_rows():
        if len(candidates) >= limit:
            break
        row_header = str(row.get("row_header", "")).strip()
        title = str(row.get("source_title", "")).strip()
        if not row_header or len(norm_text(row_header)) < 2:
            continue
        if row_header.startswith("注") or "合计" == row_header:
            continue
        key = (str(row.get("doc_id")), norm_text(row_header))
        if key in used_keys:
            continue
        used_keys.add(key)
        query = " ".join(_dedupe_text([title, str(row.get("sheet_name", "")), row_header]))[:120]
        candidates.append(
            {
                "id": "",
                "query": query,
                "source_type": "excel",
                "expected_doc_id": row.get("doc_id"),
                "expected_evidence_type": "table_row",
                "expected_contains": [row_header],
            }
        )
    return candidates


def _passes(case: dict[str, Any], retrieval: str, rerank: bool) -> bool:
    result = search_evidence(
        query=case["query"],
        source_type=case.get("source_type"),
        business_domain=case.get("business_domain"),
        doc_no=case.get("doc_no"),
        retrieval=retrieval,
        rerank=rerank,
        top_k=5,
    )
    top = result.get("results", [])[:1]
    if not top:
        return False
    first = top[0]
    if first.get("doc_id") != case.get("expected_doc_id"):
        return False
    if case.get("expected_evidence_type") and first.get("evidence_type") != case.get("expected_evidence_type"):
        return False
    text = norm_text(" ".join([str(first.get("source_title", "")), str(first.get("text", "")), str(first.get("position", ""))]))
    return all(norm_text(term) in text for term in case.get("expected_contains", []))


def _salient_phrases(text: str, max_terms: int) -> list[str]:
    phrases = []
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,12}", text):
        if phrase in {"以下简称", "有关规定", "工作要求", "具体情况"}:
            continue
        if len(phrase) >= 2 and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= max_terms:
            break
    return phrases


def _case_id(case: dict[str, Any], index: int) -> str:
    prefix = "RET_EXCEL" if case.get("expected_evidence_type") == "table_row" else "RET_TEXT"
    return f"{prefix}_{index:03d}"


def _counts_by_type(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        key = str(case.get("expected_evidence_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _interleave(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    max_len = max(len(left), len(right))
    for index in range(max_len):
        if index < len(left):
            output.append(left[index])
        if index < len(right):
            output.append(right[index])
    return output


def _dedupe_text(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = norm_text(text)
        if text and key and key not in seen:
            seen.add(key)
            output.append(text)
    return output
