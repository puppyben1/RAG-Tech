from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .governance import TRUST_POLICY_VERSION
from .path_refs import ProjectPathError, to_project_ref


EVAL_REPORT_SCHEMA_VERSION = "1.1"
CORE_ARTIFACT_REFS = (
    "data/processed/manifest.jsonl",
    "data/processed/text_chunks.jsonl",
    "data/processed/text_units.jsonl",
    "data/processed/table_cells.jsonl",
    "data/processed/table_rows.jsonl",
    "data/index/text_vectors.jsonl",
    "data/index/table_row_vectors.jsonl",
    "data/index/vector_index_manifest.json",
)


def build_eval_provenance(eval_path: Path) -> dict[str, Any]:
    return {
        "report_schema_version": EVAL_REPORT_SCHEMA_VERSION,
        "git_sha": _git_sha(),
        "source_tree_fingerprint": _source_tree_fingerprint(),
        "evaluation_dataset_fingerprint": _file_fingerprint(eval_path),
        "knowledge_base_fingerprint": _knowledge_base_fingerprint(),
        "trust_policy_version": TRUST_POLICY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def add_eval_provenance(payload: dict[str, Any], eval_path: Path) -> dict[str, Any]:
    return {
        **payload,
        **build_eval_provenance(eval_path),
        "stale": False,
        "stale_reasons": [],
    }


def assess_eval_freshness(payload: dict[str, Any], eval_path: Path) -> dict[str, Any]:
    current = build_eval_provenance(eval_path)
    reasons = list(payload.get("stale_reasons") or []) if payload.get("stale") else []
    for field in (
        "report_schema_version",
        "git_sha",
        "source_tree_fingerprint",
        "evaluation_dataset_fingerprint",
        "knowledge_base_fingerprint",
        "trust_policy_version",
    ):
        if field not in payload:
            reasons.append(f"missing_{field}")
        elif payload[field] != current[field]:
            reasons.append(f"{field}_mismatch")
    if not payload.get("generated_at"):
        reasons.append("missing_generated_at")
    reasons = sorted(set(str(reason) for reason in reasons))
    return {
        "stale": bool(reasons),
        "stale_reasons": reasons,
        "current": not reasons,
        "report_status": "stale" if reasons else "current",
    }


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_fingerprint(path: Path) -> dict[str, Any]:
    try:
        ref = to_project_ref(path, PROJECT_ROOT)
    except ProjectPathError:
        ref = None
    return {
        "path": ref,
        "exists": path.is_file(),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size if path.is_file() else None,
    }


def _knowledge_base_fingerprint() -> dict[str, Any]:
    digest = hashlib.sha256()
    files: dict[str, dict[str, Any]] = {}
    for ref in CORE_ARTIFACT_REFS:
        path = PROJECT_ROOT / ref
        file_hash = _sha256(path)
        size = path.stat().st_size if path.is_file() else None
        files[ref] = {"sha256": file_hash, "bytes": size}
        digest.update(ref.encode("utf-8") + b"\0" + (file_hash or "missing").encode("ascii") + b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def _source_tree_fingerprint() -> dict[str, Any]:
    paths = sorted((PROJECT_ROOT / "src").rglob("*.py")) if (PROJECT_ROOT / "src").is_dir() else []
    paths.extend(
        path
        for name in ("pyproject.toml", "requirements.lock.txt", "requirements-dev.lock.txt")
        if (path := PROJECT_ROOT / name).is_file()
    )
    digest = hashlib.sha256()
    files: dict[str, str | None] = {}
    for path in paths:
        ref = path.relative_to(PROJECT_ROOT).as_posix()
        file_hash = _sha256(path)
        files[ref] = file_hash
        digest.update(ref.encode("utf-8") + b"\0" + (file_hash or "missing").encode("ascii") + b"\n")
    return {"sha256": digest.hexdigest(), "file_count": len(files), "files": files}


def _git_sha() -> str:
    override = os.getenv("JINRONG_EVAL_GIT_SHA")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()
