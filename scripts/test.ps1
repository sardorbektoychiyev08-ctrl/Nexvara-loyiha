# Lint + unit tests + desktop smoke test. -Office also drives real Excel on screen.
param([switch]$Office)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venv = Join-Path $root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    $venv = Join-Path $root "..\..\.venv"
}
$py = Join-Path $venv "Scripts\python.exe"
$ruff = Join-Path $venv "Scripts\ruff.exe"
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $root "src"
$failed = $false

& $ruff check src tests;          if ($LASTEXITCODE -ne 0) { $failed = $true }
& $ruff format --check src tests; if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($Office) { $env:NEXVARA_RUN_OFFICE = "1" }
& $py -m pytest -v;                                if ($LASTEXITCODE -ne 0) { $failed = $true }
Remove-Item Env:\NEXVARA_RUN_OFFICE -ErrorAction SilentlyContinue

& $py -m nexvara.app.main --smoke;                 if ($LASTEXITCODE -ne 0) { $failed = $true }
$env:PYTHONPATH = $oldPythonPath

if ($failed) { Write-Host "NATIJA: FAIL" -ForegroundColor Red; exit 1 }
Write-Host "NATIJA: PASS" -ForegroundColor Green
