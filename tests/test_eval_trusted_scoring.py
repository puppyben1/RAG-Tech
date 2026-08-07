from jinrong.ask import AskResponse
from jinrong import eval_trusted


def test_trusted_scoring_requires_answer_terms_and_all_citations(monkeypatch) -> None:
    response = AskResponse(
        question="question",
        answer="unrelated answer",
        answer_text="unrelated answer",
        evidence=[
            {
                "doc_id": "doc-1",
                "evidence_type": "text_unit",
                "position": {"page_no": 1},
                "text": "gold term 100",
            }
        ],
        confidence="high",
        route="rag_open",
    )
    monkeypatch.setattr(eval_trusted, "ask", lambda **_: response)
    detail = eval_trusted._evaluate_case(
        {
            "id": "case-1",
            "type": "multi_hop",
            "category": "跨文件场景判断",
            "question": "question",
            "answerable": True,
            "expected_route": "rag_open",
            "expected_doc_ids": ["doc-1", "doc-2"],
            "expected_evidence_types": ["text_unit", "table_row"],
            "must_contain": ["gold term"],
            "critical_entities": ["100"],
            "gold_evidence": [{"doc_id": "doc-1", "page_no": 1}, {"doc_id": "doc-2", "page_no": 2}],
        }
    )

    assert detail["answer_correct"] is False
    assert detail["citation_hit"] is False
    assert "must_contain_missing" in detail["failure_reasons"]
    assert "critical_entity_error" in detail["failure_reasons"]
    assert "evidence_doc_mismatch" in detail["failure_reasons"]
    assert "evidence_type_mismatch" in detail["failure_reasons"]
    assert "evidence_locator_mismatch" in detail["failure_reasons"]


def test_trusted_scoring_accepts_matching_answer_and_location(monkeypatch) -> None:
    response = AskResponse(
        question="question",
        answer="gold term 100",
        answer_text="gold term 100",
        evidence=[
            {
                "doc_id": "doc-1",
                "evidence_type": "table_row",
                "sheet_name": "Data",
                "cell_refs": ["B2"],
                "text": "gold term 100",
            }
        ],
        confidence="high",
        route="rag_open",
    )
    monkeypatch.setattr(eval_trusted, "ask", lambda **_: response)
    detail = eval_trusted._evaluate_case(
        {
            "id": "case-1",
            "type": "table_lookup",
            "category": "统计取数",
            "question": "question",
            "answerable": True,
            "expected_route": "rag_open",
            "expected_doc_ids": ["doc-1"],
            "expected_evidence_type": "table_row",
            "must_contain": ["gold term"],
            "critical_entities": ["100"],
            "gold_evidence": [{"doc_id": "doc-1", "sheet_name": "Data", "cell_ref": "B2"}],
        }
    )

    assert detail["passed"] is True
    assert detail["answer_correct"] is True
    assert detail["citation_hit"] is True
