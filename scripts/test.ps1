# Lint + unit tests + desktop smoke test. -Office also drives real Excel on screen.
param([switch]$Office)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = ".venv\Scripts\python.exe"
$failed = $false

& .venv\Scripts\ruff.exe check src tests;          if ($LASTEXITCODE -ne 0) { $failed = $true }
& .venv\Scripts\ruff.exe format --check src tests; if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($Office) { $env:NEXVARA_RUN_OFFICE = "1" }
& $py -m pytest -v;                                if ($LASTEXITCODE -ne 0) { $failed = $true }
Remove-Item Env:\NEXVARA_RUN_OFFICE -ErrorAction SilentlyContinue

& $py -m nexvara.app.main --smoke;                 if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($failed) { Write-Host "NATIJA: FAIL" -ForegroundColor Red; exit 1 }
Write-Host "NATIJA: PASS" -ForegroundColor Green
