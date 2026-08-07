param(
    [Parameter(Mandatory = $true)][string]$DestinationRoot,
    [string]$RawInputRoot,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$sourceRoot = (Split-Path -Parent $PSScriptRoot)
$targetRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
$sourceFull = [System.IO.Path]::GetFullPath($sourceRoot)
$rawInputFull = if ($RawInputRoot) {
    [System.IO.Path]::GetFullPath($RawInputRoot)
}
else {
    Join-Path $sourceFull "wendang"
}
function Test-SameOrChildPath {
    param([Parameter(Mandatory = $true)][string]$Candidate, [Parameter(Mandatory = $true)][string]$Root)
    return $Candidate.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or
        $Candidate.StartsWith($Root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}
if (Test-SameOrChildPath -Candidate $targetRoot -Root $sourceFull) {
    throw "DestinationRoot must be outside the source repository: $targetRoot"
}
if (Test-SameOrChildPath -Candidate $targetRoot -Root $rawInputFull) {
    throw "DestinationRoot must be outside the raw input directory: $targetRoot"
}
if (Test-Path -LiteralPath $targetRoot) {
    throw "DestinationRoot already exists: $targetRoot"
}
$rawDataFull = Join-Path $rawInputFull "data"
if (-not (Test-Path -LiteralPath $rawDataFull -PathType Container)) {
    throw "RawInputRoot must contain a data directory: $rawInputFull"
}

function Test-GitLfsPointer {
    param([Parameter(Mandatory = $true)][string]$Path)
    $signature = [System.Text.Encoding]::ASCII.GetBytes("version https://git-lfs.github.com/spec/v1")
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt $signature.Length) { return $false }
        $header = New-Object byte[] $signature.Length
        if ($stream.Read($header, 0, $header.Length) -ne $header.Length) { return $false }
        return [System.Text.Encoding]::ASCII.GetString($header) -eq "version https://git-lfs.github.com/spec/v1"
    }
    finally {
        $stream.Dispose()
    }
}

$lfsPointers = Get-ChildItem -LiteralPath $rawInputFull -Recurse -File | Where-Object {
    Test-GitLfsPointer -Path $_.FullName
}
if ($lfsPointers) {
    throw "RawInputRoot contains Git LFS pointer files; materialize the original inputs first: $($lfsPointers[0].FullName)"
}

$initialGitSha = (git -C $sourceFull rev-parse HEAD).Trim()
$initialDirty = if (git -C $sourceFull status --porcelain) { "true" } else { "false" }
$excluded = @(
    (Join-Path $sourceFull ".venv"),
    (Join-Path $sourceFull ".pytest_cache"),
    (Join-Path $sourceFull "frontend\node_modules"),
    (Join-Path $sourceFull "frontend\dist"),
    (Join-Path $sourceFull "data\processed"),
    (Join-Path $sourceFull "data\index"),
    (Join-Path $sourceFull "data\db"),
    (Join-Path $sourceFull "reports")
)
$sourceWendangFull = [System.IO.Path]::GetFullPath((Join-Path $sourceFull "wendang"))
if (-not $rawInputFull.Equals($sourceWendangFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    $excluded += (Join-Path $sourceFull "wendang")
}

New-Item -ItemType Directory -Path $targetRoot | Out-Null
& robocopy $sourceFull $targetRoot /E /NFL /NDL /NJH /NJS /NP /XD $excluded /XF (Join-Path $sourceFull ".git") | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
if (-not $rawInputFull.Equals($sourceWendangFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    & robocopy $rawInputFull (Join-Path $targetRoot "wendang") /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "raw input copy failed with exit code $LASTEXITCODE" }
}

$python = Join-Path $targetRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $targetRoot "src"
$env:JINRONG_PARSER_PROFILE = "portable"
$env:JINRONG_BASELINE_GIT_SHA = $initialGitSha
$env:JINRONG_BASELINE_INITIAL_DIRTY = $initialDirty
$env:JINRONG_BASELINE_ALLOW_DIAGNOSTIC_DIRTY = "true"

Push-Location $targetRoot
try {
    $bootstrapArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts/bootstrap.ps1")
    if ($SkipFrontend) { $bootstrapArgs += "-SkipFrontend" }
    & powershell @bootstrapArgs
    if ($LASTEXITCODE -ne 0) { throw "bootstrap failed" }

    $manifest = & $python -m jinrong.cli build-manifest | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $manifest.count -ne 500) {
        throw "manifest validation failed: expected 500 documents, got $($manifest.count)"
    }
    $kb = & $python -m jinrong.cli build-kb | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $kb.documents -ne 500 -or $kb.processed_documents -ne 500 -or $kb.error_count -ne 0) {
        throw "knowledge-base validation failed: documents=$($kb.documents), processed=$($kb.processed_documents), errors=$($kb.error_count)"
    }

    & $python -m jinrong.cli build-metadata | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "metadata build failed" }
    & $python -m jinrong.cli build-text-units | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "text-unit build failed" }
    & $python -m jinrong.cli enhance-table-rows | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "table-row enhancement failed" }
    & $python -m jinrong.cli build-vector-index | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "vector-index build failed" }
    & $python -m jinrong.cli import-db --reset | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "database import failed" }

    $verifyArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts/verify_baseline.ps1")
    if ($SkipFrontend) { $verifyArgs += "-SkipFrontend" }
    & powershell @verifyArgs
    if ($LASTEXITCODE -ne 0) { throw "baseline verification failed; inspect reports/acceptance in $targetRoot" }
}
finally {
    Pop-Location
}

Write-Output "Isolated rebuild passed: $targetRoot"
