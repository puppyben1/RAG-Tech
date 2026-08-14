import json
from pathlib import Path

from openpyxl import Workbook

from jinrong.qa_data_audit import audit_qa_data


def test_qa_data_audit_flags_legacy_evidence_contract(tmp_path: Path) -> None:
    qa_path = tmp_path / "QA数据.xlsx"
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps({"doc_id": "d1", "file_name": "001_示例.xlsx", "title": "示例"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "source_type", "difficulty", "difficulty_cn", "qa_type", "question", "option_a", "option_b", "option_c", "option_d", "answer", "answer_text", "evidence", "source_title", "file_label"])
    sheet.append(["Q001", "excel", "easy", "简单", "表格取数", "问题", "1", "2", "3", "4", "A", "1", "data/raw/nfra_page_attachments_500/001_示例.xlsx；单元格：A1", "示例", "示例.xlsx"])
    workbook.save(qa_path)

    report = audit_qa_data(qa_path, manifest_path)

    assert report["status"] == "blocked"
    assert report["resolved_unique"] == 1
    assert report["old_path_prefix"] == 1
    assert report["body_text_evidence"] == 0
