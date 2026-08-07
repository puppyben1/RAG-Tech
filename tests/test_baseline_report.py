import json
from pathlib import Path

from jinrong.baseline_report import write_baseline_report


def test_baseline_report_has_fingerprints_and_marks_dirty_worktree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JINRONG_BASELINE_INITIAL_DIRTY", "true")
    monkeypatch.setenv("JINRONG_BASELINE_GIT_SHA", "abc123456789")
    report = write_baseline_report(tmp_path / "baseline.json", [{"name": "tests", "status": "passed"}])
    saved = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "1.0"
    assert saved["run_id"]
    assert saved["git_sha"] == "abc123456789"
    assert saved["input_dataset"]["sha256"]
    assert saved["input_dataset_sha256"] == saved["input_dataset"]["sha256"]
    assert saved["checks"] == [{"name": "tests", "status": "passed"}]
    assert saved["dirty_worktree"] is True
    assert saved["overall_status"] == "failed"
    assert report["report_path"] is None
