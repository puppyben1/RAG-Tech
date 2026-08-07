from pathlib import Path

import pytest

from jinrong.path_refs import ProjectPathError, resolve_project_ref, to_project_ref


def test_to_project_ref_uses_posix_separators(tmp_path: Path) -> None:
    target = tmp_path / "wendang" / "data" / "sample.xlsx"

    assert to_project_ref(target, tmp_path) == "wendang/data/sample.xlsx"


def test_resolve_project_ref_uses_current_root(tmp_path: Path) -> None:
    assert resolve_project_ref("data/processed/manifest.jsonl", tmp_path) == (
        tmp_path / "data" / "processed" / "manifest.jsonl"
    ).resolve()


@pytest.mark.parametrize("ref", ["../outside.txt", "data/../../outside.txt"])
def test_resolve_project_ref_rejects_parent_traversal(tmp_path: Path, ref: str) -> None:
    with pytest.raises(ProjectPathError, match="path_outside_project") as exc_info:
        resolve_project_ref(ref, tmp_path)

    assert exc_info.value.code == "path_outside_project"


def test_resolve_project_ref_rejects_project_root_reference(tmp_path: Path) -> None:
    with pytest.raises(ProjectPathError, match="invalid_project_ref"):
        resolve_project_ref(".", tmp_path)


def test_resolve_project_ref_reports_legacy_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(ProjectPathError, match="legacy_absolute_path") as exc_info:
        resolve_project_ref(r"E:\\work\\code\\JINRONG\\missing.xlsx", tmp_path)

    assert exc_info.value.code == "legacy_absolute_path"


def test_to_project_ref_rejects_path_outside_root(tmp_path: Path) -> None:
    with pytest.raises(ProjectPathError, match="path_outside_project"):
        to_project_ref(tmp_path.parent / "outside.txt", tmp_path)
