from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .config import RAW_DATA_DIR, REPORTS_DIR
from .qa_data import load_qa
from .text_qa import solve_text_mcq
from .utils import ensure_dir


TEXT_EVAL_REPORT = REPORTS_DIR / "text_eval.json"


def evaluate_text(data_dir: Path = RAW_DATA_DIR, report_path: Path = TEXT_EVAL_REPORT) -> dict:
    items = [item for item in load_qa() if item.source_type in {"word", "pdf"}]
    rows = []
    correct = 0
    by_source: Counter[str] = Counter()
    by_source_correct: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    by_type_correct: Counter[str] = Counter()
    by_ext: Counter[str] = Counter()
    by_ext_correct: Counter[str] = Counter()
    for item in items:
        result = solve_text_mcq(item, data_dir)
        ok = result.answer == item.answer
        ext = Path(item.file_label).suffix.lower()
        correct += int(ok)
        by_source[item.source_type] += 1
        by_source_correct[item.source_type] += int(ok)
        by_type[item.qa_type] += 1
        by_type_correct[item.qa_type] += int(ok)
        by_ext[ext] += 1
        by_ext_correct[ext] += int(ok)
        rows.append(
            {
                "id": item.id,
                "source_type": item.source_type,
                "qa_type": item.qa_type,
                "file_label": item.file_label,
                "gold": item.answer,
                "pred": result.answer,
                "ok": ok,
                "confidence": result.confidence,
                "debug": result.debug,
                "question": item.question,
                "pred_answer_text": result.answer_text,
                "evidence": result.evidence[:1000],
            }
        )
    summary = {
        "total": len(items),
        "correct": correct,
        "accuracy": correct / len(items) if items else 0,
        "by_source": _summary(by_source, by_source_correct),
        "by_type": _summary(by_type, by_type_correct),
        "by_ext": _summary(by_ext, by_ext_correct),
    }
    payload = {"summary": summary, "rows": rows}
    ensure_dir(REPORTS_DIR)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _summary(total: Counter[str], correct: Counter[str]) -> dict:
    return {
        key: {
            "total": count,
            "correct": correct[key],
            "accuracy": correct[key] / count if count else 0,
        }
        for key, count in sorted(total.items())
    }

