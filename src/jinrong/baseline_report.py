from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PROJECT_ROOT, REPORTS_DIR
from .path_refs import ProjectPathError, to_project_ref


ARTIFACT_PATHS = (
    "data/processed/manifest.jsonl",
    "data/processed/text_chunks.jsonl",
    "data/processed/text_units.jsonl",
    "data/processed/table_cells.jsonl",
    "data/processed/table_rows.jsonl",
    "data/index/text_vectors.jsonl",
    "data/index/table_row_vectors.jsonl",
    "data/index/vector_index_manifest.json",
)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_fingerprint(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    count = 0
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix().encode("utf-8")
            file_hash = _sha256(path)
            digest.update(relative + b"\0" + (file_hash or "").encode("ascii") + b"\n")
            count += 1
    return {"path": to_project_ref(root), "file_count": count, "sha256": digest.hexdigest()}


def _command_version(command: str) -> str | None:
    try:
        result = subprocess.run([command, "--version"], capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    value = (result.stdout or result.stderr).strip().splitlines()
    return value[0] if value else None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _git(*args: str) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def build_baseline_report(checks: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    git_sha = os.getenv("JINRONG_BASELINE_GIT_SHA") or _git("rev-parse", "HEAD")
    short_sha = git_sha[:7] or "nogit"
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{short_sha}"
    check_list = [dict(check) for check in checks]
    initial_dirty = os.getenv("JINRONG_BASELINE_INITIAL_DIRTY")
    dirty = initial_dirty.lower() == "true" if initial_dirty is not None else bool(_git("status", "--porcelain"))
    input_dataset = _tree_fingerprint(PROJECT_ROOT / "wendang" / "data")
    lockfiles = {
        "python": _sha256(PROJECT_ROOT / "requirements.lock.txt"),
        "python_dev": _sha256(PROJECT_ROOT / "requirements-dev.lock.txt"),
        "node": _sha256(PROJECT_ROOT / "frontend" / "package-lock.json"),
    }
    artifacts = {}
    for relative in ARTIFACT_PATHS:
        path = PROJECT_ROOT / relative
        digest = _sha256(path)
        if digest:
            artifacts[relative] = {"sha256": digest, "bytes": path.stat().st_size}
    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "git_sha": git_sha,
        "dirty_worktree": dirty,
        "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
        "python_version": platform.python_version(),
        "node_version": _command_version("node"),
        "parser_profile": os.getenv("JINRONG_PARSER_PROFILE", "portable"),
        "external_tools": {
            "libreoffice": _command_version("soffice") if os.getenv("JINRONG_PARSER_PROFILE") == "libreoffice" else None,
        },
        "python_lock_sha256": lockfiles["python"],
        "node_lock_sha256": lockfiles["node"],
        "lockfiles": lockfiles,
        "input_dataset": input_dataset,
        "input_dataset_sha256": input_dataset["sha256"],
        "checks": check_list,
        "path_audit": _read_json(PROJECT_ROOT / "reports" / "path_audit.json")
        or next((check.get("details", {}) for check in check_list if check.get("name") == "path_audit"), {}),
        "artifact_fingerprints": artifacts,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_status": "passed" if check_list and all(check.get("status") == "passed" for check in check_list) and not dirty else "failed",
        "approval_status": "diagnostic_dirty_worktree" if dirty else "candidate",
    }
    return report


def write_baseline_report(output_path: Path | None = None, checks: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    report = build_baseline_report(checks)
    path = output_path or REPORTS_DIR / "acceptance" / report["run_id"] / "baseline.json"
    path = path if path.is_absolute() else PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        report["report_path"] = to_project_ref(path)
    except ProjectPathError:
        report["report_path"] = None
    return report
