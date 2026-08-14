import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "jinrong.cli", *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_help_smoke() -> None:
    result = _run_cli("--help")

    assert result.returncode == 0
    assert "path-audit" in result.stdout
    assert "eval-acceptance" in result.stdout
    assert "qa-data-audit" in result.stdout
    assert "migrate-qa-data" in result.stdout


def test_cli_path_audit_passes_for_source_tree() -> None:
    result = _run_cli("path-audit", "--root", "tests")

    assert result.returncode == 0
    assert '"status": "passed"' in result.stdout
