import json
from pathlib import Path

from jinrong.eval_provenance import assess_freshness, build_provenance
from jinrong.eval_trusted import load_trusted_report


def test_provenance_detects_git_dataset_and_policy_changes(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text('{"id":"one"}\n', encoding="utf-8")
    provenance = build_provenance(eval_path)
    assert provenance["git_sha"]
    assert provenance["evaluation_dataset_fingerprint"]
    assert provenance["knowledge_base_artifact_fingerprint"]
    assert provenance["trust_policy_version"]
    assert assess_freshness({"provenance": provenance}, eval_path)["current"] is True

    changed = {"provenance": {**provenance, "git_sha": "different"}}
    result = assess_freshness(changed, eval_path)
    assert result["stale"] is True
    assert result["current"] is False
    assert "git_sha" in result["stale_reasons"]


def test_legacy_trusted_report_is_available_but_stale(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "trusted_eval_summary.json"
    report_path.write_text(json.dumps({"total": 1, "passed": 1}), encoding="utf-8")
    monkeypatch.setattr("jinrong.eval_trusted.TRUSTED_EVAL_PATH", tmp_path / "eval.jsonl")
    (tmp_path / "eval.jsonl").write_text('{"id":"one"}\n', encoding="utf-8")
    loaded = load_trusted_report("summary", reports_dir=tmp_path)
    assert loaded["available"] is True
    assert loaded["stale"] is True
    assert loaded["current"] is False
    assert loaded["stale_reasons"]


def test_report_paths_are_normalized_on_read(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "trusted_eval_summary.json"
    report_path.write_text(json.dumps({"report_path": r"E:\\work\\code\\JINRONG\\reports\\trusted_eval_summary.json"}), encoding="utf-8")
    monkeypatch.setattr("jinrong.eval_trusted.TRUSTED_EVAL_PATH", tmp_path / "eval.jsonl")
    (tmp_path / "eval.jsonl").write_text('{"id":"one"}\n', encoding="utf-8")
    loaded = load_trusted_report("summary", reports_dir=tmp_path)
    assert loaded["report_path"] is None
