import json
from pathlib import Path

from jinrong.sensitive_audit import scan_sensitive_information


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_sensitive_scan_redacts_values_and_requires_disposition(tmp_path: Path) -> None:
    units = tmp_path / "units.jsonl"
    cells = tmp_path / "cells.jsonl"
    report_path = tmp_path / "report.json"
    _write_jsonl(
        units,
        [{"unit_id": "u1", "doc_id": "d1", "page_no": 2, "text": "联系电话 13812345678；统计值 1234567890123456"}],
    )
    _write_jsonl(cells, [])

    first = scan_sensitive_information(units, cells, report_path)
    serialized = report_path.read_text(encoding="utf-8")
    assert first["candidate_count"] == 1
    assert first["gate"] == "blocked"
    assert "13812345678" not in serialized
    assert "统计值" not in serialized
    assert first["raw_match_values_persisted"] is False

    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "scan_fingerprint": first["scan_fingerprint"],
                "decisions": [
                    {
                        "candidate_id": first["candidates"][0]["candidate_id"],
                        "disposition": "authorized_public_template",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    second = scan_sensitive_information(units, cells, report_path, decisions_path=decisions)
    assert second["scan_fingerprint"] == first["scan_fingerprint"]
    assert second["gate"] == "passed"


def test_contextual_account_number_is_detected(tmp_path: Path) -> None:
    units = tmp_path / "units.jsonl"
    cells = tmp_path / "cells.jsonl"
    _write_jsonl(units, [])
    _write_jsonl(
        cells,
        [{"cell_id": "c1", "doc_id": "d1", "sheet_name": "S", "cell_ref": "A1", "row_header": "银行账号", "value_raw": "6222021234567890123"}],
    )

    payload = scan_sensitive_information(units, cells, tmp_path / "report.json")
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["rule"] == "account_number"
