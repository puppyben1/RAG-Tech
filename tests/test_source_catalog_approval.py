import json

import pytest

import jinrong.source_catalog as source_catalog
from jinrong.source_catalog import approve_source_catalog


def test_approval_stamps_selected_rows_and_validates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(source_catalog, "to_project_ref", lambda path: path.name)
    source = tmp_path / "candidate.jsonl"
    output = tmp_path / "approved.jsonl"
    source.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "sha256": "abc",
                "file_name": "one.pdf",
                "title": "One",
                "source_url": "https://www.gov.cn/source",
                "attachment_url": "https://www.gov.cn/source.pdf",
                "version_status": "current",
                "source_evidence": "official page",
                "version_evidence": "effective clause",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = approve_source_catalog(source, output, "reviewer-1", "2026-08-06T14:00:00+08:00", ["doc-1"], manifest_path=source)

    assert result["validation"]["valid"] is True
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["reviewed_by"] == "reviewer-1"


def test_approval_requires_explicit_identity(tmp_path) -> None:
    with pytest.raises(ValueError, match="reviewer is required"):
        approve_source_catalog(tmp_path / "missing.jsonl", tmp_path / "out.jsonl", "", "2026-08-06T14:00:00+08:00", ["x"])

