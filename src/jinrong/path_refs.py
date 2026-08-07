from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .config import PROJECT_ROOT


class ProjectPathError(ValueError):
    def __init__(self, code: str, value: Any) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value}")


def to_project_ref(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    root = project_root.resolve()
    candidate = path.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ProjectPathError("path_outside_project", path) from exc
    if relative == Path("."):
        raise ProjectPathError("invalid_project_ref", path)
    return relative.as_posix()


def resolve_project_ref(ref: str, project_root: Path = PROJECT_ROOT) -> Path:
    if not isinstance(ref, str) or not ref.strip():
        raise ProjectPathError("invalid_project_ref", ref)
    if PureWindowsPath(ref).is_absolute() or PurePosixPath(ref).is_absolute():
        raise ProjectPathError("legacy_absolute_path", ref)
    if "\\" in ref:
        raise ProjectPathError("invalid_project_ref", ref)

    raw_parts = ref.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ProjectPathError("path_outside_project" if ".." in raw_parts else "invalid_project_ref", ref)
    relative = PurePosixPath(ref)

    root = project_root.resolve()
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ProjectPathError("path_outside_project", ref) from exc
    return candidate
