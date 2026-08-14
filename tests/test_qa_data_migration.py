import csv
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from jinrong.qa_data_migration import migrate_qa_data
from jinrong.utils import read_jsonl


HEADERS = ["id", "source_type", "difficulty", "difficulty_cn", "qa_type", "question", "option_a", "option_b", "option_c", "option_d", "answer", "answer_text", "evidence", "source_title", "file_label"]


def test_migration_separates_ready_candidates_from_review_rows(tmp_path: Path) -> None:
    qa_path = tmp_path / "QA数据.xlsx"
    manifest_path = tmp_path / "manifest.jsonl"
    raw_dir = tmp_path / "wendang" / "data"
    raw_dir.mkdir(parents=True)
    source_workbook = Workbook()
    source_sheet = source_workbook.active
    source_sheet.title = "数据  "
    source_sheet["C5"] = 1
    source_sheet["D5"] = 2
    source_workbook.save(raw_dir / "001_统计表.xlsx")
    (raw_dir / "002_制度.docx").write_bytes(b"docx")
    manifest = [
        {"doc_id": "d1", "file_name": "001_统计表.xlsx", "title": "统计表", "source_url": None},
        {"doc_id": "d2", "file_name": "002_制度.docx", "title": "制度", "source_url": None},
    ]
    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest), encoding="utf-8")
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append(["Q001", "excel", "easy", "简单", "表格取数", "问题1", "1", "2", "3", "4", "A", "1", "data/raw/nfra_page_attachments_500/001_统计表.xlsx；工作表：数据；单元格：C5", "统计表", "统计表.xlsx"])
    sheet.append(["Q004", "excel", "easy", "简单", "表格计算", "问题4", "1", "2", "3", "4", "A", "1", "data/raw/nfra_page_attachments_500/001_统计表.xlsx；工作表：数据；甲=1(C5)，乙=2(D5)；变化值=1", "统计表", "统计表.xlsx"])
    sheet.append(["Q002", "word", "easy", "简单", "单事实检索", "问题2", "1", "2", "3", "4", "A", "答案", "正文证据", "制度", "制度.docx"])
    sheet.append(["Q003", "pdf", "easy", "简单", "单事实检索", "问题3", "1", "2", "3", "4", "A", "答案", "正文证据", "不存在", "不存在.pdf"])
    workbook.save(qa_path)
    output = tmp_path / "candidate.jsonl"
    review = tmp_path / "review.csv"

    report = migrate_qa_data(qa_path, output, review, manifest_path, project_root=tmp_path)

    assert report["ready_candidates"] == 2
    assert report["document_matched_locator_missing"] == 1
    assert report["unresolved_document"] == 1
    rows = read_jsonl(output)
    assert rows[0]["doc_id"] == "d1"
    assert rows[0]["local_path"] == "wendang/data/001_统计表.xlsx"
    assert rows[0]["gold_evidence"] == [{"doc_id": "d1", "sheet_name": "数据  ", "cell_ref": "C5"}]
    assert rows[1]["gold_evidence"] == [
        {"doc_id": "d1", "sheet_name": "数据  ", "cell_ref": "C5"},
        {"doc_id": "d1", "sheet_name": "数据  ", "cell_ref": "D5"},
    ]
    with review.open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert [row["id"] for row in review_rows] == ["Q002", "Q003"]


def test_migration_refuses_to_overwrite_source_workbook(tmp_path: Path) -> None:
    qa_path = tmp_path / "QA数据.xlsx"
    qa_path.write_bytes(b"source")

    with pytest.raises(ValueError, match="must not overwrite"):
        migrate_qa_data(qa_path, qa_path, tmp_path / "review.csv", tmp_path / "manifest.jsonl")
