from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .compliance_qa import answer_compliance_question, is_compliance_question
from .config import RAW_DATA_DIR
from .excel_parser import filter_sheet, parse_excel
from .qa_data import QAItem, load_qa
from .path_refs import to_project_ref
from .table_qa import (
    _best_fact,
    _evidence,
    extract_metric_and_column,
    extract_sheet,
    find_excel_file,
    quoted_terms,
    solve_calc,
    solve_compare,
    solve_excel_mcq,
    solve_lookup,
)
from .text_parser import extract_text, split_sentences
from .text_qa import find_source_file, nearest_evidence, score_option
from .trusted_qa import REFUSAL_TEXT, answer_open_question
from .multi_step_qa import answer_multi_hop, answer_text_then_table, is_multi_hop_question, is_text_then_table_question
from .utils import norm_text, round_like_eval


@dataclass
class AskResponse:
    question: str
    answer: Any | None
    answer_text: Any | None
    evidence: list[dict[str, Any]]
    confidence: str
    route: str
    debug: str | None = None
    refusal_reason: str | None = None

    def __post_init__(self) -> None:
        if self.refusal_reason is None and self.answer_text == REFUSAL_TEXT:
            self.refusal_reason = _classify_refusal(self.debug)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _classify_refusal(debug: str | None) -> str:
    try:
        payload = json.loads(debug or "{}")
    except json.JSONDecodeError:
        payload = {}
    reason = str(payload.get("reason") or "")
    if reason == "out_of_scope_or_sensitive_query":
        return "out_of_scope_or_sensitive"
    if reason == "non_authoritative_evidence":
        return "non_authoritative_evidence"
    if reason == "no evidence retrieved":
        return "no_evidence"
    return "insufficient_evidence"


def ask(
    question: str | None = None,
    options: dict[str, Any] | None = None,
    qa_id: str | None = None,
    data_dir: Path = RAW_DATA_DIR,
) -> AskResponse:
    if qa_id:
        item = _qa_by_id(qa_id)
        if item.source_type == "excel":
            result = solve_excel_mcq(item, data_dir)
            return _from_mcq_result(item.question, result.answer, result.answer_text, result.evidence, "excel_mcq", result.confidence, result.debug)
        result = __import__("jinrong.text_qa", fromlist=["solve_text_mcq"]).solve_text_mcq(item, data_dir)
        return _from_mcq_result(item.question, result.answer, result.answer_text, result.evidence, "text_mcq", result.confidence, result.debug)

    if not question:
        raise ValueError("question or qa_id is required")

    if options:
        item = _item_from_question(question, options)
        if _looks_like_excel(question):
            result = solve_excel_mcq(item, data_dir)
            return _from_mcq_result(question, result.answer, result.answer_text, result.evidence, "excel_mcq", result.confidence, result.debug)
        result = __import__("jinrong.text_qa", fromlist=["solve_text_mcq"]).solve_text_mcq(item, data_dir)
        return _from_mcq_result(question, result.answer, result.answer_text, result.evidence, "text_mcq", result.confidence, result.debug)

    if is_compliance_question(question):
        return _ask_compliance(question)
    if is_text_then_table_question(question):
        return _ask_text_then_table(question)
    if is_multi_hop_question(question):
        return _ask_multi_hop(question)
    if _looks_like_excel(question) and "《" in question:
        return _ask_excel_open(question, data_dir)
    return _ask_rag_open(question)


def _qa_by_id(qa_id: str) -> QAItem:
    for item in load_qa():
        if item.id == qa_id:
            return item
    raise KeyError(f"QA id not found: {qa_id}")


def _from_mcq_result(
    question: str,
    answer: Any | None,
    answer_text: Any | None,
    evidence: str,
    route: str,
    confidence: str,
    debug: str | None,
) -> AskResponse:
    return AskResponse(
        question=question,
        answer=answer,
        answer_text=answer_text,
        evidence=[{"text": evidence}] if evidence else [],
        confidence=confidence,
        route=route,
        debug=debug,
    )


def _item_from_question(question: str, options: dict[str, Any]) -> QAItem:
    title = _extract_title(question) or ""
    qa_type = _infer_qa_type(question, bool(options))
    source_type = "excel" if _looks_like_excel(question) else "word"
    ext = ".xlsx" if source_type == "excel" else ""
    return QAItem(
        id="ASK",
        source_type=source_type,
        difficulty="unknown",
        difficulty_cn="unknown",
        qa_type=qa_type,
        question=question,
        options=options,
        answer="",
        answer_text=None,
        evidence="",
        source_title=title,
        file_label=f"{title}{ext}",
    )


def _looks_like_excel(question: str) -> bool:
    markers = ["Excel", "工作表", "单元格", "口径", "数值", "最高", "变化"]
    return any(m in question for m in markers)


def _infer_qa_type(question: str, has_options: bool = False) -> str:
    if "变化" in question or "计算" in question or "从" in question and "到" in question:
        return "表格计算"
    if "最高" in question or "最低" in question or "最大" in question or "最小" in question:
        return "表格比较"
    if _looks_like_excel(question):
        return "表格取数"
    if "两项" in question or "组选项" in question:
        return "多事实检索"
    return "单事实检索"


def _extract_title(question: str) -> str | None:
    m = re.search(r"《([^》]+)》", question)
    return m.group(1).strip() if m else None


def _ask_excel_open(question: str, data_dir: Path) -> AskResponse:
    item = _item_from_question(question, {})
    path = find_excel_file(item, data_dir)
    if path is None:
        return AskResponse(question, None, None, [], "low", "excel_open", "file not found")
    facts = filter_sheet(parse_excel(str(path.resolve())), extract_sheet(question))
    qa_type = _infer_qa_type(question)
    if qa_type == "表格取数":
        row_term, col_term = extract_metric_and_column(question)
        fact = _best_fact(facts, row_term, col_term)
        if not fact:
            return AskResponse(question, None, None, [], "low", "excel_lookup", f"cell not found: {row_term}/{col_term}")
        return AskResponse(
            question,
            fact.value_num,
            fact.value_num,
            [_fact_evidence(path, fact)],
            "high",
            "excel_lookup",
        )
    if qa_type == "表格比较":
        terms = quoted_terms(question)
        col_term = terms[-1] if terms else None
        row_candidates = [f for f in facts if not col_term or norm_text(col_term) in norm_text(f.col_header)]
        if not row_candidates:
            return AskResponse(question, None, None, [], "low", "excel_compare", f"column not found: {col_term}")
        selected = max(row_candidates, key=lambda f: f.value_num or float("-inf"))
        return AskResponse(
            question,
            selected.row_header,
            selected.row_header,
            [_fact_evidence(path, selected)],
            "medium",
            "excel_compare",
        )
    if qa_type == "表格计算":
        # Open calculation without options reuses the deterministic solver by giving dummy options.
        dummy = _item_from_question(question, {"A": 0})
        result = solve_calc(dummy, path, facts)
        return AskResponse(question, result.answer_text, result.answer_text, [{"text": result.evidence}], result.confidence, "excel_calc", result.debug)
    return AskResponse(question, None, None, [], "low", "excel_open", "unsupported excel question")


def _fact_evidence(path: Path, fact) -> dict[str, Any]:
    return {
        "source": to_project_ref(path),
        "sheet_name": fact.sheet_name,
        "cell_ref": fact.cell_ref,
        "row_header": fact.row_header,
        "col_header": fact.col_header,
        "unit": fact.unit,
        "value_raw": fact.value_raw,
        "text": _evidence(path, fact),
    }


def _ask_text_open(question: str, data_dir: Path) -> AskResponse:
    item = _item_from_question(question, {})
    path = find_source_file(item, data_dir)
    if path is None:
        return AskResponse(question, None, None, [], "low", "text_open", "file not found")
    text = extract_text(str(path.resolve()))
    query_terms = [t for t in quoted_terms(question)] or [_extract_title(question) or question]
    best_sentence = ""
    best_score = -1
    for sent in split_sentences(text):
        sent_norm = norm_text(sent)
        score = sum(score_option(term, sent_norm)[0] for term in query_terms)
        if score > best_score:
            best_score = score
            best_sentence = sent
    if not best_sentence:
        return AskResponse(question, None, None, [], "low", "text_open", "no evidence found")
    return AskResponse(
        question=question,
        answer=best_sentence,
        answer_text=best_sentence,
        evidence=[{"source": to_project_ref(path), "text": best_sentence}],
        confidence="medium",
        route="text_open",
    )


def _ask_rag_open(question: str) -> AskResponse:
    result = answer_open_question(question)
    return AskResponse(
        question=question,
        answer=result.answer,
        answer_text=result.answer_text,
        evidence=result.evidence,
        confidence=result.confidence,
        route=result.route,
        debug=result.debug,
    )


def _ask_compliance(question: str) -> AskResponse:
    result = answer_compliance_question(question)
    return AskResponse(
        question=question,
        answer=result.answer,
        answer_text=result.answer_text,
        evidence=result.evidence,
        confidence=result.confidence,
        route=result.route,
        debug=result.debug,
    )


def _ask_text_then_table(question: str) -> AskResponse:
    result = answer_text_then_table(question)
    return AskResponse(
        question=question,
        answer=result.answer,
        answer_text=result.answer_text,
        evidence=result.evidence,
        confidence=result.confidence,
        route=result.route,
        debug=result.debug,
    )


def _ask_multi_hop(question: str) -> AskResponse:
    result = answer_multi_hop(question)
    return AskResponse(
        question=question,
        answer=result.answer,
        answer_text=result.answer_text,
        evidence=result.evidence,
        confidence=result.confidence,
        route=result.route,
        debug=result.debug,
    )
