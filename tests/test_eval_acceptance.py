import hashlib
import json
from pathlib import Path

import pytest

from jinrong import eval_acceptance, eval_provenance
from jinrong.eval_acceptance import build_acceptance_metrics, build_latency_gate, load_acceptance_report, run_acceptance, validate_acceptance_inputs
from jinrong.eval_provenance import add_eval_provenance


def test_acceptance_metrics_apply_all_five_thresholds() -> None:
    cases = [
        {"id": "fact", "type": "open_fact", "answerable": True},
        {"id": "table", "type": "table_lookup", "answerable": True},
        {"id": "refusal", "type": "refusal", "answerable": False},
    ]
    details = [
        {"id": "fact", "answer_correct": True, "citation_hit": True, "critical_entities": [], "critical_entity_errors": []},
        {"id": "table", "answer_correct": True, "citation_hit": True, "critical_entities": ["100"], "critical_entity_errors": []},
        {"id": "refusal", "refusal_correct": True},
    ]

    metrics = build_acceptance_metrics(cases, details)

    assert set(metrics) == {
        "institutional_fact_accuracy",
        "table_lookup_accuracy",
        "citation_hit_rate",
        "critical_entity_error_rate",
        "refusal_success_rate",
    }
    assert all(metric["passed"] for metric in metrics.values())


def test_acceptance_rejects_blocked_or_mismatched_manifest(tmp_path: Path) -> None:
    eval_path = tmp_path / "holdout.jsonl"
    manifest_path = tmp_path / "freeze_manifest.json"
    eval_path.write_text('{"id":"one"}\n', encoding="utf-8")
    manifest_path.write_text(json.dumps({"gate": "blocked", "gate_reasons": ["pending_external_review"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="gate is not ready"):
        validate_acceptance_inputs(eval_path, manifest_path)

    manifest_path.write_text(
        json.dumps({"gate": "ready_for_evaluation", "holdout": {"sha256": "wrong"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fingerprint"):
        validate_acceptance_inputs(eval_path, manifest_path)

    expected_sha = hashlib.sha256(eval_path.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps({"gate": "ready_for_evaluation", "holdout": {"sha256": expected_sha}}),
        encoding="utf-8",
    )
    assert validate_acceptance_inputs(eval_path, manifest_path)["gate"] == "ready_for_evaluation"


def test_acceptance_runner_writes_bound_report(tmp_path: Path, monkeypatch) -> None:
    eval_path = tmp_path / "holdout.jsonl"
    manifest_path = tmp_path / "freeze_manifest.json"
    output_path = tmp_path / "acceptance.json"
    cases = [
        {"id": "fact", "type": "open_fact", "answerable": True},
        {"id": "table", "type": "table_lookup", "answerable": True},
        {"id": "refusal", "type": "refusal", "answerable": False},
    ]
    eval_path.write_text("\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "gate": "ready_for_evaluation",
                "holdout": {"sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest()},
            }
        ),
        encoding="utf-8",
    )

    def fake_evaluate(*, eval_path: Path, report_path: Path) -> dict:
        details = [
            {"id": "fact", "answer_correct": True, "citation_hit": True, "critical_entities": [], "critical_entity_errors": []},
            {"id": "table", "answer_correct": True, "citation_hit": True, "critical_entities": ["100"], "critical_entity_errors": []},
            {"id": "refusal", "refusal_correct": True},
        ]
        report_path.write_text(json.dumps({"summary": {"latency_ms": {"p95": 12.5}}, "details": details}), encoding="utf-8")
        return {"total": 3, "passed": 3}

    monkeypatch.setattr(eval_acceptance, "evaluate_trusted", fake_evaluate)
    payload = run_acceptance(eval_path, manifest_path, output_path, max_p95_ms=20)

    assert payload["status"] == "passed"
    assert payload["holdout_gate"] == "ready_for_evaluation"
    assert payload["holdout_manifest_fingerprint"]["sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert payload["latency_ms"]["p95"] == 12.5
    assert payload["latency_gate"]["passed"] is True
    assert output_path.is_file()


def test_acceptance_loader_never_passes_stale_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(eval_acceptance, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(eval_provenance, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("JINRONG_EVAL_GIT_SHA", "abc123")
    eval_path = tmp_path / "data" / "eval" / "accepted" / "holdout.jsonl"
    manifest_path = tmp_path / "data" / "eval" / "accepted" / "freeze_manifest.json"
    report_path = tmp_path / "reports" / "acceptance" / "final" / "trusted_holdout.json"
    eval_path.parent.mkdir(parents=True)
    report_path.parent.mkdir(parents=True)
    eval_path.write_text('{"id":"case-1"}\n', encoding="utf-8")
    manifest_path.write_text('{"gate":"ready_for_evaluation"}', encoding="utf-8")
    payload = add_eval_provenance(
        {
            "status": "passed",
            "holdout_gate": "ready_for_evaluation",
            "holdout_manifest_fingerprint": {
                "path": "data/eval/accepted/freeze_manifest.json",
                "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            },
        },
        eval_path,
    )
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    report = load_acceptance_report(report_path)
    assert report["stale"] is False, report["stale_reasons"]
    assert report["final_passed"] is True, report
    assert report["report_status"] == "passed"

    source_path = tmp_path / "src" / "jinrong" / "new_rule.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("VALUE = 1\n", encoding="utf-8")
    stale = load_acceptance_report(report_path)
    assert stale["final_passed"] is False
    assert stale["report_status"] == "stale"
    assert "source_tree_fingerprint_mismatch" in stale["stale_reasons"]


def test_latency_gate_never_passes_without_platform_threshold() -> None:
    assert build_latency_gate({"p95": 12.5}, None) == {
        "status": "unverified",
        "passed": False,
        "p95_ms": 12.5,
        "max_p95_ms": None,
        "reason": "platform_latency_threshold_not_configured",
    }
    assert build_latency_gate({"p95": 12.5}, 10)["passed"] is False
