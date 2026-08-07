from __future__ import annotations

import json
from pathlib import Path

from jinrong import eval_provenance
from jinrong.eval_provenance import add_eval_provenance, assess_eval_freshness
from jinrong.eval_trusted import load_trusted_report
from jinrong.governance import TRUST_POLICY_VERSION


def test_eval_provenance_detects_dataset_and_kb_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(eval_provenance, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("JINRONG_EVAL_GIT_SHA", "abc123")
    eval_path = tmp_path / "data" / "eval" / "trusted_eval.jsonl"
    artifact_path = tmp_path / "data" / "processed" / "manifest.jsonl"
    source_path = tmp_path / "src" / "jinrong" / "ask.py"
    eval_path.parent.mkdir(parents=True)
    artifact_path.parent.mkdir(parents=True)
    source_path.parent.mkdir(parents=True)
    eval_path.write_text('{"id":"case-1"}\n', encoding="utf-8")
    artifact_path.write_text('{"doc_id":"doc-1"}\n', encoding="utf-8")
    source_path.write_text("VALUE = 1\n", encoding="utf-8")

    payload = add_eval_provenance({"total": 1, "passed": 1}, eval_path)

    assert payload["git_sha"] == "abc123"
    assert payload["evaluation_dataset_fingerprint"]["sha256"]
    assert payload["knowledge_base_fingerprint"]["sha256"]
    assert payload["source_tree_fingerprint"]["sha256"]
    assert payload["trust_policy_version"] == TRUST_POLICY_VERSION
    assert payload["generated_at"].endswith("Z")
    assert assess_eval_freshness(payload, eval_path)["current"] is True

    eval_path.write_text('{"id":"case-2"}\n', encoding="utf-8")
    freshness = assess_eval_freshness(payload, eval_path)
    assert freshness["stale"] is True
    assert "evaluation_dataset_fingerprint_mismatch" in freshness["stale_reasons"]

    eval_path.write_text('{"id":"case-1"}\n', encoding="utf-8")
    artifact_path.write_text('{"doc_id":"doc-2"}\n', encoding="utf-8")
    freshness = assess_eval_freshness(payload, eval_path)
    assert "knowledge_base_fingerprint_mismatch" in freshness["stale_reasons"]

    artifact_path.write_text('{"doc_id":"doc-1"}\n', encoding="utf-8")
    source_path.write_text("VALUE = 2\n", encoding="utf-8")
    freshness = assess_eval_freshness(payload, eval_path)
    assert "source_tree_fingerprint_mismatch" in freshness["stale_reasons"]


def test_legacy_trusted_report_is_stale(tmp_path: Path, monkeypatch) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "trusted_eval_open_fact.json").write_text(
        json.dumps({"summary": {"total": 15, "passed": 15, "accuracy": 1.0}}),
        encoding="utf-8",
    )

    report = load_trusted_report("open_fact", reports_dir)

    assert report["available"] is True
    assert report["stale"] is True
    assert report["current"] is False
    assert report["report_status"] == "stale"
    assert "missing_git_sha" in report["stale_reasons"]
    assert "missing_generated_at" in report["stale_reasons"]
