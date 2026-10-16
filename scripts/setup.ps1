# Creates .venv on this drive and installs NEXVARA with dev tools.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "Tayyor. Ishga tushirish: .\scripts\run.ps1"
