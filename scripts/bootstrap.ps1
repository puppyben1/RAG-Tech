param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

Push-Location $projectRoot
try {
    if (-not (Test-Path $venvPython)) {
        py -3.12 -m venv .venv
    }
    & $venvPython -m pip install --require-hashes -r requirements-dev.lock.txt
    if (-not $SkipFrontend) {
        npm --prefix frontend ci
    }
}
finally {
    Pop-Location
}
