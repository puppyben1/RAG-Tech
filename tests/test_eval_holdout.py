import json
from pathlib import Path

import pytest

from jinrong.eval_holdout import approve_eval_holdout, freeze_eval_sets, question_fingerprint


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _case(case_id: str, question: str, case_type: str = "open_fact", **values: object) -> dict:
    return {"id": case_id, "type": case_type, "question": question, "answerable": True, **values}


def test_freeze_records_fingerprints_and_pending_gate(tmp_path: Path) -> None:
    dev = tmp_path / "dev.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write(dev, [_case("d1", "question one")])
    _write(holdout, [_case("h1", "question two", "table_lookup")])
    manifest = freeze_eval_sets(dev, holdout, tmp_path / "frozen")
    assert manifest["gate"] == "blocked"
    assert "pending_external_review" in manifest["gate_reasons"]
    assert manifest["overlap"]["question_fingerprint_count"] == 0
    assert manifest["holdout"]["case_count"] == 1
    assert question_fingerprint("question two") in manifest["holdout"]["question_fingerprints"]


def test_freeze_rejects_question_overlap(tmp_path: Path) -> None:
    dev = tmp_path / "dev.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write(dev, [_case("d1", "same question")])
    _write(holdout, [_case("h1", " same question ")])
    with pytest.raises(ValueError, match="dev_holdout_question_overlap"):
        freeze_eval_sets(dev, holdout, tmp_path / "frozen")


def test_freeze_rejects_empty_or_duplicate_questions(tmp_path: Path) -> None:
    dev = tmp_path / "dev.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write(dev, [_case("d1", "")])
    _write(holdout, [_case("h1", "holdout")])
    with pytest.raises(ValueError, match="dev_empty_question:d1"):
        freeze_eval_sets(dev, holdout, tmp_path / "empty")
    _write(dev, [_case("d1", "same"), _case("d2", " same ")])
    with pytest.raises(ValueError, match="dev_duplicate_questions:1"):
        freeze_eval_sets(dev, holdout, tmp_path / "duplicate")


def test_approve_holdout_writes_audited_copy_and_opens_gate(tmp_path: Path) -> None:
    dev = tmp_path / "dev.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    approved = tmp_path / "approved.jsonl"
    _write(dev, [_case("d1", "dev question")])
    rows = []
    for index in range(5):
        suffix = index + 1
        rows.extend(
            [
                _answerable_gold(f"fact-{suffix}", f"fact {suffix}", "制度事实", "nfra_1"),
                _answerable_gold(
                    f"threshold-{suffix}",
                    f"threshold {suffix}",
                    "条款阈值",
                    "nfra_2",
                    "compliance_judgement",
                    critical_entities=[str(suffix)],
                ),
                _answerable_gold(f"flow-{suffix}", f"flow {suffix}", "业务流程", "nfra_3"),
                _answerable_gold(
                    f"table-{suffix}",
                    f"number {suffix}",
                    "统计取数",
                    "nfra_4",
                    "table_lookup",
                    table=True,
                    critical_entities=[str(suffix)],
                ),
                _answerable_gold(f"multi-{suffix}", f"multi {suffix}", "跨文件场景判断", "nfra_5", "multi_hop"),
                _case(
                    f"refusal-{suffix}",
                    f"missing {suffix}",
                    "refusal",
                    category="不可回答负例",
                    answerable=False,
                    expected_route="rag_refusal",
                    refusal_reason="The fact is absent from the supplied corpus.",
                ),
            ]
        )
    _write(holdout, rows)
    approval = approve_eval_holdout(
        holdout,
        approved,
        "independent-reviewer",
        "2026-08-07T12:00:00+08:00",
        [row["id"] for row in rows],
    )
    assert approval["pending_case_ids"] == []
    manifest = freeze_eval_sets(dev, approved, tmp_path / "frozen")
    assert manifest["coverage_complete"] is True
    assert manifest["gate"] == "ready_for_evaluation"


def test_reviewed_holdout_without_audit_metadata_stays_blocked(tmp_path: Path) -> None:
    dev = tmp_path / "dev.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write(dev, [_case("d1", "dev question")])
    _write(holdout, [_case("h1", "holdout question", review_status="reviewed")])
    manifest = freeze_eval_sets(dev, holdout, tmp_path / "frozen")
    assert manifest["gate"] == "blocked"
    assert "invalid_review_metadata:h1" in manifest["gate_reasons"]


def test_approve_holdout_rejects_in_place_or_naive_timestamp(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.jsonl"
    output = tmp_path / "approved.jsonl"
    _write(holdout, [_case("h1", "holdout question")])
    with pytest.raises(ValueError, match="must differ"):
        approve_eval_holdout(holdout, holdout, "reviewer", "2026-08-07T12:00:00+08:00", ["h1"])
    with pytest.raises(ValueError, match="include a timezone"):
        approve_eval_holdout(holdout, output, "reviewer", "2026-08-07T12:00:00", ["h1"])


def test_approve_holdout_rejects_incomplete_gold(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.jsonl"
    _write(holdout, [_case("h1", "vague question")])
    with pytest.raises(ValueError, match="gold is incomplete"):
        approve_eval_holdout(
            holdout,
            tmp_path / "approved.jsonl",
            "reviewer",
            "2026-08-07T12:00:00+08:00",
            ["h1"],
        )


def _answerable_gold(
    case_id: str,
    question: str,
    category: str,
    doc_id: str,
    case_type: str = "open_fact",
    *,
    table: bool = False,
    critical_entities: list[str] | None = None,
) -> dict:
    locator = {"doc_id": doc_id, "sheet_name": "Sheet1", "cell_ref": "B2"} if table else {"doc_id": doc_id, "page_no": 1}
    return _case(
        case_id,
        question,
        case_type,
        category=category,
        expected_route="rag_open",
        expected_doc_ids=[doc_id],
        expected_evidence_type="table_row" if table else "text_unit",
        must_contain=["gold term"],
        critical_entities=critical_entities or [],
        gold_evidence=[locator],
    )
