from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .config import INDEX_DIR, PROCESSED_DIR, REPORTS_DIR
from .path_refs import ProjectPathError, resolve_project_ref, to_project_ref
from .utils import ensure_dir


PATH_FIELDS = {
    "source",
    "manifest",
    "local_path",
    "parsed_path",
    "db_path",
    "state_path",
    "errors_path",
    "chunks_path",
    "cells_path",
    "table_rows_path",
    "table_cells_path",
    "text_source",
    "table_source",
    "manifest_path",
    "metadata_path",
    "text_units_path",
    "source_catalog_path",
    "report_path",
    "output_path",
    "text_index_path",
    "table_index_path",
    "document_metadata_path",
    "text_vector_index_path",
    "table_vector_index_path",
}


def audit_project_paths(
    roots: Iterable[Path] | None = None,
    output_path: Path | None = None,
    max_issue_samples: int = 200,
) -> dict[str, Any]:
    selected_roots = list(roots or (PROCESSED_DIR, INDEX_DIR, REPORTS_DIR))
    issues: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    validation_cache: dict[str, tuple[str, str] | None] = {}
    issue_count = 0
    files_checked = 0
    fields_checked = 0

    def add_issue(issue: dict[str, str]) -> None:
        nonlocal issue_count
        issue_count += 1
        counts[issue["code"]] += 1
        if len(issues) < max_issue_samples:
            issues.append(issue)

    for artifact in _artifact_files(selected_roots):
        if output_path and artifact.resolve() == output_path.resolve():
            continue
        files_checked += 1
        try:
            values = _iter_artifact_values(artifact)
            for row_location, value in values:
                for location, field, path_value in _walk_path_fields(value, row_location):
                    fields_checked += 1
                    if path_value is None:
                        continue
                    if not isinstance(path_value, str):
                        add_issue(_issue(artifact, location, "invalid_path_type", repr(path_value)))
                        continue
                    validation = validation_cache.get(path_value)
                    if path_value not in validation_cache:
                        try:
                            target = resolve_project_ref(path_value)
                            validation = None if target.exists() else ("missing_path", path_value)
                        except ProjectPathError as exc:
                            validation = (exc.code, path_value)
                        validation_cache[path_value] = validation
                        if validation:
                            add_issue(_issue(artifact, location, validation[0], validation[1]))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            add_issue(_issue(artifact, "$", "invalid_artifact", str(exc)))

    report = {
        "schema_version": "1.0",
        "status": "passed" if not issue_count else "failed",
        "roots": [to_project_ref(root) for root in selected_roots],
        "files_checked": files_checked,
        "fields_checked": fields_checked,
        "unique_references_checked": len(validation_cache),
        "issue_count": issue_count,
        "issues_by_code": dict(sorted(counts.items())),
        "issues": issues,
        "issue_samples_truncated": issue_count > len(issues),
    }
    if output_path:
        ensure_dir(output_path.parent)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _artifact_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix.lower() in {".json", ".jsonl"}:
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.suffix.lower() in {".json", ".jsonl"})
    return sorted(set(files))


def _iter_artifact_values(path: Path) -> Iterable[tuple[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    yield f"$[{line_number}]", json.loads(line)
        return
    yield "$", json.loads(path.read_text(encoding="utf-8"))


def _walk_path_fields(value: Any, location: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key in PATH_FIELDS:
                yield child_location, key, child
            elif isinstance(child, (dict, list)):
                yield from _walk_path_fields(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from _walk_path_fields(child, f"{location}[{index}]")


def _issue(artifact: Path, location: str, code: str, value: str) -> dict[str, str]:
    return {
        "artifact": to_project_ref(artifact),
        "location": location,
        "code": code,
        "value": value,
    }
