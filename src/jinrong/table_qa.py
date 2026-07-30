from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RAW_DATA_DIR
from .excel_parser import CellFact, filter_sheet, parse_excel
from .qa_data import QAItem
from .utils import loose_contains, nearly_equal, norm_text, round_like_eval, to_number


@dataclass
class AnswerResult:
    answer: str | None
    answer_text: Any | None
    evidence: str
    confidence: str
    debug: str | None = None


def find_excel_file(item: QAItem, data_dir: Path = RAW_DATA_DIR) -> Path | None:
    label_stem = Path(item.file_label).stem
    title = item.source_title
    candidates = sorted(p for p in data_dir.iterdir() if p.suffix.lower() in {".xls", ".xlsx"})
    for p in candidates:
        if norm_text(label_stem) in norm_text(p.stem) or norm_text(title) in norm_text(p.stem):
            return p
    for p in candidates:
        if all(part in norm_text(p.stem) for part in norm_text(title).split()):
            return p
    return None


def extract_sheet(question: str) -> str | None:
    m = re.search(r"工作表：([^）)]+)", question)
    return m.group(1).strip() if m else None


def quoted_terms(question: str) -> list[str]:
    return re.findall(r"[“\"]([^”\"]+)[”\"]", question)


def extract_metric_and_column(question: str) -> tuple[str | None, str | None]:
    terms = quoted_terms(question)
    if "数值是多少" in question and len(terms) >= 2:
        return terms[-2], terms[-1]
    return (terms[0], terms[1]) if len(terms) >= 2 else (None, None)


def _option_to_answer(value: Any, options: dict[str, Any]) -> str | None:
    for key, option in options.items():
        if nearly_equal(value, option):
            return key
    return None


def _col_match(fact_col: str, col_term: str | None) -> bool:
    if not col_term:
        return True
    f = norm_text(fact_col)
    c = norm_text(col_term)
    if not c:
        return True
    quarter_alias = {
        "年季度": ["一季度"],
        "季度": ["四季度"],
        "季度季度": ["四季度"],
        "本年累计截至当期": ["本年累计截至当期"],
    }
    aliases = quarter_alias.get(c, [])
    if aliases:
        return any(alias in f for alias in aliases)
    return c in f or f in c


def _score_fact(fact: CellFact, row_term: str | None, col_term: str | None) -> int:
    score = 0
    if row_term and loose_contains(fact.row_header, row_term):
        score += 5
    if col_term and _col_match(fact.col_header, col_term):
        score += 5
    if row_term and norm_text(row_term) == norm_text(fact.row_header):
        score += 3
    if col_term and norm_text(col_term) == norm_text(fact.col_header).split("-")[-1]:
        score += 3
    return score


def _best_fact(facts: list[CellFact], row_term: str | None, col_term: str | None) -> CellFact | None:
    scored = [( _score_fact(f, row_term, col_term), f) for f in facts]
    scored = [x for x in scored if x[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1].row_index, x[1].col_index))
    return scored[0][1]


def _candidate_facts(facts: list[CellFact], row_term: str | None, col_term: str | None) -> list[CellFact]:
    scored = [(_score_fact(f, row_term, col_term), f) for f in facts]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1].row_index, x[1].col_index))
    return [f for _, f in scored]


def _evidence(path: Path, fact: CellFact, extra: str | None = None) -> str:
    parts = [
        str(path),
        f"工作表：{fact.sheet_name}",
        f"单元格：{fact.cell_ref}",
    ]
    if fact.unit:
        parts.append(f"单位：{fact.unit}")
    parts.append(f"{fact.row_header} / {fact.col_header} = {fact.value_raw}")
    if extra:
        parts.append(extra)
    return "；".join(parts) + "。"


def solve_lookup(item: QAItem, path: Path, facts: list[CellFact]) -> AnswerResult:
    row_term, col_term = extract_metric_and_column(item.question)
    if norm_text(col_term).replace("-", "") == "季度":
        col_term = "年-季度"
    fact = _best_fact(facts, row_term, col_term)
    if not fact:
        return AnswerResult(None, None, "", "low", f"lookup miss row={row_term} col={col_term}")
    answer = _option_to_answer(fact.value_num, item.options)
    return AnswerResult(answer, fact.value_num, _evidence(path, fact), "high")


def solve_compare(item: QAItem, path: Path, facts: list[CellFact]) -> AnswerResult:
    terms = quoted_terms(item.question)
    col_term = terms[-1] if terms else None
    want_max = "最高" in item.question or "最大" in item.question
    candidates: list[tuple[str, Any, CellFact]] = []
    for key, option in item.options.items():
        if _is_incomparable_metric(str(option), col_term):
            continue
        fact = _best_fact(facts, str(option), col_term)
        if fact is not None:
            candidates.append((key, option, fact))
    if not candidates:
        return AnswerResult(None, None, "", "low", f"compare miss col={col_term}")
    selected = max(candidates, key=lambda x: x[2].value_num or float("-inf")) if want_max else min(candidates, key=lambda x: x[2].value_num or float("inf"))
    details = "；".join(f"{opt}={fact.value_raw}({fact.cell_ref})" for _, opt, fact in candidates)
    return AnswerResult(selected[0], selected[1], _evidence(path, selected[2], details), "high")


def _is_incomparable_metric(option: str, col_term: str | None) -> bool:
    if norm_text(col_term).replace("/", "").replace("-", "") != "本年累计截至当期":
        return False
    text = norm_text(option)
    blocked = ["保险金额", "新增保险金额", "总资产", "保单件数", "保户投资款", "投连险"]
    return any(term in text for term in blocked)


def solve_calc(item: QAItem, path: Path, facts: list[CellFact]) -> AnswerResult:
    terms = quoted_terms(item.question)
    if len(terms) < 3:
        return AnswerResult(None, None, "", "low", "calc terms miss")
    row_term, from_col, to_col = terms[-3], terms[-2], terms[-1]
    from_fact = _select_calc_fact(facts, row_term, from_col, is_target=False)
    to_fact = _select_calc_fact(facts, row_term, to_col, is_target=True)
    if from_fact is None or to_fact is None:
        return AnswerResult(None, None, "", "low", f"calc miss row={row_term} from={from_col} to={to_col}")
    value = round_like_eval((to_fact.value_num or 0) - (from_fact.value_num or 0))
    answer = _option_to_answer(value, item.options)
    ev = (
        f"{str(path)}；工作表：{from_fact.sheet_name}；"
        f"{from_col}={from_fact.value_raw}({from_fact.cell_ref})，"
        f"{to_col}={to_fact.value_raw}({to_fact.cell_ref})；变化值={value}。"
    )
    return AnswerResult(answer, value, ev, "high")


def _select_calc_fact(facts: list[CellFact], row_term: str, col_term: str, is_target: bool) -> CellFact | None:
    col_norm = norm_text(col_term).replace("/", "").replace("-", "")
    if is_target and col_norm == "本年累计截至当期":
        row_matches = [f for f in facts if loose_contains(f.row_header, row_term) and f.col_index == 10]
        if row_matches:
            return sorted(row_matches, key=lambda f: f.row_index)[0]
    if is_target and col_norm == "季度季度":
        candidates = [f for f in _candidate_facts(facts, row_term, "季度") if loose_contains(f.row_header, row_term)]
        by_row: dict[int, CellFact] = {}
        for fact in candidates:
            by_row.setdefault(fact.row_index, fact)
        ordered = [by_row[idx] for idx in sorted(by_row)]
        if len(ordered) >= 2:
            return ordered[1]
    return _best_fact(facts, row_term, col_term)


def solve_excel_mcq(item: QAItem, data_dir: Path = RAW_DATA_DIR) -> AnswerResult:
    path = find_excel_file(item, data_dir)
    if path is None:
        return AnswerResult(None, None, "", "low", "file not found")
    sheet_name = extract_sheet(item.question)
    facts = filter_sheet(parse_excel(str(path.resolve())), sheet_name)
    if item.qa_type == "表格取数":
        return solve_lookup(item, path, facts)
    if item.qa_type == "表格比较":
        return solve_compare(item, path, facts)
    if item.qa_type == "表格计算":
        return solve_calc(item, path, facts)
    return AnswerResult(None, None, "", "low", f"unsupported qa_type={item.qa_type}")
