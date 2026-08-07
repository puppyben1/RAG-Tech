import json
from pathlib import Path

from jinrong import competition_readiness


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_readiness_reports_each_blocking_gate(tmp_path: Path, monkeypatch) -> None:
    kb = tmp_path / "kb.json"
    errors = tmp_path / "errors.json"
    paths = tmp_path / "paths.json"
    metadata = tmp_path / "metadata.jsonl"
    doc = tmp_path / "doc.json"
    sensitive = tmp_path / "sensitive.json"
    holdout = tmp_path / "holdout.json"
    acceptance = tmp_path / "acceptance.json"
    _write(kb, {"documents": 500, "processed_documents": 500, "error_count": 0})
    _write(errors, [])
    _write(paths, {"status": "passed", "issue_count": 0})
    _write_jsonl(metadata, [{"doc_id": f"d{i}", "version_status": "unknown"} for i in range(500)])
    _write(doc, {"gate": "blocked", "gate_reasons": ["manual_review_pending:32"]})
    _write(sensitive, {"gate": "passed", "gate_reasons": [], "candidate_count": 0})
    _write(holdout, {"gate": "blocked", "gate_reasons": ["pending_external_review"], "holdout": {"case_count": 6}})
    monkeypatch.setattr(competition_readiness, "load_acceptance_report", lambda path: {"available": False, "final_passed": False})

    payload = competition_readiness.build_competition_readiness(
        kb_stats_path=kb,
        kb_errors_path=errors,
        path_audit_path=paths,
        metadata_path=metadata,
        doc_quality_path=doc,
        sensitive_audit_path=sensitive,
        holdout_manifest_path=holdout,
        acceptance_report_path=acceptance,
        output_path=tmp_path / "ready.json",
    )

    assert payload["status"] == "blocked"
    assert payload["gates"]["reproducibility"]["status"] == "passed"
    assert payload["gates"]["sensitive_information"]["status"] == "passed"
    assert payload["gates"]["source_and_version"]["incomplete_documents"] == 500
    assert set(payload["blocked_gates"]) == {
        "source_and_version",
        "legacy_doc_quality",
        "independent_holdout",
        "final_acceptance",
    }


def test_source_gate_accepts_current_and_snapshot_metadata() -> None:
    rows = [
        {"doc_id": "law", "source_url": "https://official/page", "attachment_url": "https://official/a", "version_status": "current", "effective_date": "2026-01-01"},
        {"doc_id": "stats", "source_url": "https://official/page2", "attachment_url": "https://official/b", "version_status": "not_applicable", "period": "2026-01"},
    ]
    gate = competition_readiness._source_gate(rows)
    assert gate["complete_documents"] == 2
    assert gate["incomplete_documents"] == 0
    assert "source_or_version_incomplete" not in " ".join(gate["reasons"])

