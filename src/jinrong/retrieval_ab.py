from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .eval_retrieval import evaluate_retrieval
from .path_refs import ProjectPathError, to_project_ref
from .utils import ensure_dir


def run_retrieval_ab(
    eval_path: Path,
    output_path: Path,
    *,
    top_k: int = 5,
    rerank: bool = True,
    holdout_manifest: Path | None = None,
) -> dict[str, Any]:
    gate = "not_checked"
    gate_reasons: list[str] = []
    if holdout_manifest and holdout_manifest.exists():
        freeze = json.loads(holdout_manifest.read_text(encoding="utf-8"))
        gate = freeze.get("gate", "unknown")
        gate_reasons = list(freeze.get("gate_reasons", []))
    runs: dict[str, Any] = {}
    for retrieval in ("bm25", "hybrid"):
        report_path = output_path.with_name(f"{output_path.stem}_{retrieval}.json")
        runs[retrieval] = evaluate_retrieval(eval_path=eval_path, report_path=report_path, retrieval=retrieval, rerank=rerank, top_k=top_k)
    baseline = runs["bm25"]
    candidate = runs["hybrid"]
    payload = {
        "status": "diagnostic_only" if gate != "ready_for_evaluation" else "completed",
        "holdout_gate": gate,
        "holdout_gate_reasons": gate_reasons,
        "eval_path": _project_ref_or_none(eval_path),
        "eval_path_status": _path_status(eval_path),
        "top_k": top_k,
        "rerank": rerank,
        "baseline": baseline,
        "candidate": candidate,
        "delta": {
            "top1_accuracy": candidate.get("top1_accuracy", 0) - baseline.get("top1_accuracy", 0),
            "top3_accuracy": candidate.get("top3_accuracy", 0) - baseline.get("top3_accuracy", 0),
            "topk_accuracy": candidate.get("topk_accuracy", 0) - baseline.get("topk_accuracy", 0),
            "latency_p95_ms": candidate.get("latency_ms", {}).get("p95", 0) - baseline.get("latency_ms", {}).get("p95", 0),
        },
        "decision": "do_not_change_default_until_holdout_gate_passes",
        "report_path": to_project_ref(output_path),
    }
    ensure_dir(output_path.parent)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _project_ref_or_none(path: Path) -> str | None:
    try:
        return to_project_ref(path)
    except ProjectPathError:
        return None


def _path_status(path: Path) -> str:
    return "project_relative" if _project_ref_or_none(path) else "external_input"
