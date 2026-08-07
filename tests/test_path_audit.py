import json
from pathlib import Path

import jinrong.path_audit as path_audit


def test_path_audit_reports_only_declared_path_fields(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "artifact.json"
    existing = tmp_path / "data" / "present.txt"
    existing.parent.mkdir()
    existing.write_text("ok", encoding="utf-8")
    artifact.write_text(
        json.dumps(
            {
                "local_path": "data/present.txt",
                "report_path": r"E:\\old\\report.json",
                "text": r"example E:\\not-a-path-field.txt",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(path_audit, "resolve_project_ref", lambda ref: _resolve(ref, tmp_path))
    monkeypatch.setattr(path_audit, "to_project_ref", lambda path: path.resolve().relative_to(tmp_path).as_posix())

    report = path_audit.audit_project_paths([artifact])

    assert report["fields_checked"] == 2
    assert report["issues_by_code"] == {"legacy_absolute_path": 1}


def _resolve(ref: str, root: Path) -> Path:
    from jinrong.path_refs import resolve_project_ref

    return resolve_project_ref(ref, root)
