from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .services import search_evidence
from .utils import norm_text


@dataclass
class MultiStepAnswer:
    answer: dict[str, Any]
    answer_text: str
    evidence: list[dict[str, Any]]
    confidence: str
    route: str
    debug: str


def is_text_then_table_question(question: str) -> bool:
    q = norm_text(question)
    markers = [
        "先说明",
        "再定位",
        "先解释",
        "再用",
        "制度口径",
        "统计用途",
        "明确口径",
    ]
    if any(norm_text(marker) in q for marker in markers):
        return True
    return "商业银行主要监管指标" in q and ("单位" in q or "期间" in q or "为什么" in q)


def is_multi_hop_question(question: str) -> bool:
    q = norm_text(question)
    markers = ["比较", "跨年度", "跨文件", "1月和2月", "2024年和2025年", "从银行函证制度要求出发"]
    return any(norm_text(marker) in q for marker in markers)


def answer_text_then_table(question: str) -> MultiStepAnswer:
    text_query, table_query = _text_then_table_queries(question)
    text_search = search_evidence(query=text_query, source_type="pdf", top_k=5)
    table_search = search_evidence(query=table_query, source_type="excel", top_k=5)
    text_evidence = text_search.get("results", [])[:2]
    table_evidence = table_search.get("results", [])[:2]
    evidence = (text_evidence + table_evidence)[:4]
    payload = {
        "reasoning_steps": [
            {"step": "先检索制度、说明或口径类文本证据", "query": text_query},
            {"step": "再检索与指标、期间或表格相关的行级证据", "query": table_query},
        ],
        "text_evidence": [_basis_item(item) for item in text_evidence],
        "table_evidence": [_basis_item(item) for item in table_evidence],
        "answer_text": _compose_text_then_table_answer(question, text_evidence, table_evidence),
        "confidence": "medium" if evidence else "low",
    }
    return MultiStepAnswer(
        answer=payload,
        answer_text=payload["answer_text"],
        evidence=evidence,
        confidence=payload["confidence"],
        route="text_then_table",
        debug=json.dumps(
            {
                "text_query": text_query,
                "table_query": table_query,
                "text_count": len(text_evidence),
                "table_count": len(table_evidence),
            },
            ensure_ascii=False,
        ),
    )


def answer_multi_hop(question: str) -> MultiStepAnswer:
    subqueries = _multi_hop_queries(question)
    all_evidence: list[dict[str, Any]] = []
    hop_results: list[dict[str, Any]] = []
    for query, source_type in subqueries:
        search = search_evidence(query=query, source_type=source_type, top_k=3)
        results = search.get("results", [])[:2]
        all_evidence.extend(results)
        hop_results.append({"query": query, "source_type": source_type, "evidence": [_basis_item(item) for item in results]})
    evidence = _dedupe_evidence(all_evidence)[:5]
    payload = {
        "reasoning_steps": [
            {"step": "识别问题中的比较对象或跨文件证据需求"},
            {"step": "为每个对象分别检索最小证据"},
            {"step": "仅依据检索证据生成比较或证据链说明"},
        ],
        "comparison": _compose_comparison(question, hop_results),
        "table_evidence": [item for hop in hop_results for item in hop["evidence"] if item.get("evidence_type") == "table_row"],
        "basis": [item for hop in hop_results for item in hop["evidence"]],
        "source_trace": [item for item in [_basis_item(row) for row in evidence]],
        "answer_text": _compose_multi_hop_answer(question, hop_results),
        "confidence": "medium" if evidence else "low",
    }
    return MultiStepAnswer(
        answer=payload,
        answer_text=payload["answer_text"],
        evidence=evidence,
        confidence=payload["confidence"],
        route="multi_hop",
        debug=json.dumps({"subqueries": subqueries, "hop_count": len(hop_results)}, ensure_ascii=False),
    )


def _text_then_table_queries(question: str) -> tuple[str, str]:
    q = norm_text(question)
    if "绿色信贷" in q:
        return (
            "绿色信贷统计制度 统计用途 统计说明",
            "绿色信贷统计数据汇总表 绿色信贷 统计",
        )
    if "资本充足率" in q or "商业银行主要监管指标" in q:
        return (
            "监管统计 统计口径 指标 单位 期间",
            "2025年商业银行主要监管指标情况表 资本充足率 单位 期间",
        )
    return (
        f"{question} 制度 口径 依据",
        f"{question} 指标 表格 单位 期间",
    )


def _multi_hop_queries(question: str) -> list[tuple[str, str | None]]:
    q = norm_text(question)
    if "2024年" in q and "2025年" in q and "资本充足率" in q:
        return [
            ("2024年商业银行主要监管指标情况表 资本充足率", "excel"),
            ("2025年商业银行主要监管指标情况表 资本充足率", "excel"),
        ]
    if "人身险" in q and "原保险保费收入" in q:
        return [
            ("2026年1月人身险公司经营情况表 原保险保费收入", "excel"),
            ("2026年2月人身险公司经营情况表 原保险保费收入", "excel"),
        ]
    if "财产险" in q and "原保险保费收入" in q:
        return [
            ("2026年1月财产险公司经营情况表 原保险保费收入", "excel"),
            ("2026年2月财产险公司经营情况表 原保险保费收入", "excel"),
        ]
    if "银行函证" in q:
        return [
            ("银行函证 制度要求 结论 依据 来源位置", "pdf"),
            ("银行函证 工作质量 效率 回函 证据", "word"),
        ]
    return [(f"{question} 依据", None), (f"{question} 证据", None)]


def _basis_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": item.get("doc_id"),
        "title": item.get("source_title"),
        "position": item.get("position") or {},
        "evidence_type": item.get("evidence_type"),
        "quote": str(item.get("text") or "").replace("\n", " ")[:300],
    }


def _dedupe_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any, Any]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        position = row.get("position") or {}
        key = (row.get("doc_id"), row.get("evidence_type"), json.dumps(position, ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _compose_text_then_table_answer(
    question: str,
    text_evidence: list[dict[str, Any]],
    table_evidence: list[dict[str, Any]],
) -> str:
    parts = ["该问题需要先确认制度或统计口径，再引用表格或指标证据。"]
    if text_evidence:
        parts.append(f"文本依据来自《{text_evidence[0].get('source_title')}》。")
    if table_evidence:
        row = (table_evidence[0].get("position") or {}).get("row_header") or "相关指标"
        parts.append(f"表格证据定位到《{table_evidence[0].get('source_title')}》中的{row}。")
    if "绿色信贷" in question:
        parts.append("回答应围绕绿色信贷统计用途和统计依据展开。")
    if "资本充足率" in question:
        parts.append("回答资本充足率时应同时保留期间、单位和来源表格位置。")
    return "".join(parts)


def _compose_multi_hop_answer(question: str, hop_results: list[dict[str, Any]]) -> str:
    if "比较" in question:
        return f"该问题需要比较多个对象；已分别检索 {len(hop_results)} 组证据，答案应以各组表格或文本证据为依据，不脱离来源进行推断。"
    return f"该问题需要跨证据链回答；已分别检索 {len(hop_results)} 组依据，并保留来源位置用于追溯。"


def _compose_comparison(question: str, hop_results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for hop in hop_results:
        rows.append(
            {
                "query": hop["query"],
                "top_doc_ids": [item.get("doc_id") for item in hop["evidence"]],
                "top_titles": [item.get("title") for item in hop["evidence"]],
            }
        )
    return {"summary": "第一版仅做证据级比较框架，数值差异解释需后续增强。", "items": rows}
