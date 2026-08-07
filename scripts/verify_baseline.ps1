param(
    [switch]$SkipFrontend,
    [switch]$SkipPathAudit
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:JINRONG_PARSER_PROFILE = "portable"
if (-not $env:JINRONG_BASELINE_GIT_SHA) {
    $env:JINRONG_BASELINE_GIT_SHA = (git -C $projectRoot rev-parse HEAD).Trim()
}
if (-not $env:JINRONG_BASELINE_INITIAL_DIRTY) {
    $env:JINRONG_BASELINE_INITIAL_DIRTY = if (git -C $projectRoot status --porcelain) { "true" } else { "false" }
}
$checks = [System.Collections.Generic.List[string]]::new()
$failed = $false

function Invoke-BaselineCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    try {
        & $Action *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
        $checks.Add("$Name=passed")
    }
    catch {
        $script:failed = $true
        $checks.Add("$Name=failed")
        Write-Warning "$Name failed: $($_.Exception.Message)"
    }
}

Push-Location $projectRoot
try {
    Invoke-BaselineCheck "compileall" { & $venvPython -m compileall -q src tests }
    Invoke-BaselineCheck "pytest" { & $venvPython -m pytest -q }
    if (-not $SkipPathAudit) {
        Invoke-BaselineCheck "path_audit" { & $venvPython -m jinrong.cli path-audit `
            --root data/processed `
            --root data/index `
            --root reports `
            --output reports/path_audit.json }
    }
    if (-not $SkipFrontend) {
        Invoke-BaselineCheck "frontend_ci" { npm --prefix frontend ci }
        Invoke-BaselineCheck "frontend_build" { npm --prefix frontend run build }
    }
}
finally {
    $reportArgs = @("baseline-report")
    foreach ($check in $checks) { $reportArgs += @("--check", $check) }
    & $venvPython -m jinrong.cli @reportArgs
    if ($LASTEXITCODE -ne 0) { $script:failed = $true }
    Pop-Location
}

if ($failed) { exit 1 }
