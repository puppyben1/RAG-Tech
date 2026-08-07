import json
from pathlib import Path

from jinrong.doc_quality_audit import approve_doc_reviews, audit_doc_quality


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_fallback_doc_requires_hash_bound_manual_review(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    state = tmp_path / "state.jsonl"
    report = tmp_path / "report.json"
    worklist = tmp_path / "worklist.jsonl"
    reviewed = tmp_path / "reviewed.jsonl"
    _write_jsonl(manifest, [{"doc_id": "d1", "file_ext": ".doc", "file_name": "one.doc", "sha256": "source"}])
    _write_jsonl(chunks, [{"doc_id": "d1", "text": "有效正文" * 40}])
    _write_jsonl(state, [{"doc_id": "d1", "status": "success", "warning": "used binary .doc fallback extraction"}])

    first = audit_doc_quality(manifest, chunks, state, report, worklist_path=worklist)
    assert first["machine_failed"] == 0
    assert first["gate"] == "blocked"
    assert first["gate_reasons"] == ["manual_review_pending:1"]

    rows = [json.loads(line) for line in worklist.read_text(encoding="utf-8").splitlines()]
    rows[0].update({"readable": True, "content_complete": True, "tables_complete": True})
    _write_jsonl(worklist, rows)
    approve_doc_reviews(worklist, reviewed, "External Reviewer", "2026-08-07T12:00:00+08:00", ["d1"])

    final = audit_doc_quality(manifest, chunks, state, report, reviewed_path=reviewed)
    assert final["gate"] == "passed"
    assert final["manual_review_pending"] == 0


def test_doc_machine_quality_fails_empty_extraction(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    state = tmp_path / "state.jsonl"
    _write_jsonl(manifest, [{"doc_id": "d1", "file_ext": ".doc", "sha256": "source"}])
    _write_jsonl(chunks, [])
    _write_jsonl(state, [{"doc_id": "d1", "status": "failed"}])

    payload = audit_doc_quality(manifest, chunks, state, tmp_path / "report.json")
    assert payload["gate"] == "blocked"
    assert "machine_quality_failed:1" in payload["gate_reasons"]

