from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .config import EXCEL_EVAL_REPORT, RAW_DATA_DIR, REPORTS_DIR
from .qa_data import load_qa
from .table_qa import solve_excel_mcq
from .utils import ensure_dir


def evaluate_excel(data_dir: Path = RAW_DATA_DIR, report_path: Path = EXCEL_EVAL_REPORT) -> dict:
    items = [item for item in load_qa() if item.source_type == "excel"]
    rows = []
    correct = 0
    by_type: Counter[str] = Counter()
    by_type_correct: Counter[str] = Counter()
    for item in items:
        result = solve_excel_mcq(item, data_dir)
        ok = result.answer == item.answer
        correct += int(ok)
        by_type[item.qa_type] += 1
        by_type_correct[item.qa_type] += int(ok)
        rows.append(
            {
                "id": item.id,
                "qa_type": item.qa_type,
                "gold": item.answer,
                "pred": result.answer,
                "ok": ok,
                "gold_answer_text": item.answer_text,
                "pred_answer_text": result.answer_text,
                "confidence": result.confidence,
                "debug": result.debug,
                "question": item.question,
                "evidence": result.evidence,
            }
        )
    summary = {
        "total": len(items),
        "correct": correct,
        "accuracy": correct / len(items) if items else 0,
        "by_type": {
            qa_type: {
                "total": count,
                "correct": by_type_correct[qa_type],
                "accuracy": by_type_correct[qa_type] / count if count else 0,
            }
            for qa_type, count in sorted(by_type.items())
        },
    }
    payload = {"summary": summary, "rows": rows}
    ensure_dir(REPORTS_DIR)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

