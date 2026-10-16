# Opens the NEXVARA desktop window.
$root = Split-Path -Parent $PSScriptRoot
& "$root\.venv\Scripts\python.exe" -m nexvara.app.main @args
exit $LASTEXITCODE
