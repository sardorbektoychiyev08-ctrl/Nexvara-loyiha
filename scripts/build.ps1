# Builds dist\NEXVARA\NEXVARA.exe (PyInstaller) and dist\installer\NEXVARA-Setup-<ver>.exe (Inno Setup).
# Needs: pip install pyinstaller (in .venv) and Inno Setup 6 (winget install JRSoftware.InnoSetup).
# -Publish <folder>: also sign and copy the installer to a private release channel folder
# (needs D:\NEXVARA\release\signing_key.pem, see src\nexvara\updater.py).
param([string]$Publish = "", [string]$Notes = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = ".venv\Scripts\python.exe"
$env:PYTHONPATH = "src"

$version = & $py -c "import nexvara; print(nexvara.__version__)"
New-Item -ItemType Directory -Force build | Out-Null
& $py -c "from pathlib import Path; from nexvara.app.shortcut import write_icon; write_icon(Path('build/nexvara.ico'))"
$v = ($version.Split(".") + @("0", "0", "0"))[0..3] -join ", "
@"
VSVersionInfo(ffi=FixedFileInfo(filevers=($v), prodvers=($v)), kids=[
  StringFileInfo([StringTable('040904B0', [StringStruct('ProductName', 'NEXVARA Personal'),
    StringStruct('FileDescription', 'NEXVARA Personal'), StringStruct('FileVersion', '$version'),
    StringStruct('ProductVersion', '$version')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"@ | Set-Content -Encoding utf8 build\version_info.txt

# PyInstaller and ISCC write progress to stderr: with "Stop" and the output redirected
# (build.ps1 *> log.txt) the first progress line would end the build. Exit codes decide.
$ErrorActionPreference = "Continue"
& $py -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi installer\nexvara.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 topilmadi (winget install JRSoftware.InnoSetup)" }
& $iscc /Q "/DAppVersion=$version" "/DSourceDir=$root\dist\NEXVARA" installer\nexvara.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }
$setup = "dist\installer\NEXVARA-Setup-$version.exe"
Write-Host "Tayyor: $setup"

if ($Publish) {
    & $py -m nexvara.updater publish $setup $version $Publish $Notes
    if ($LASTEXITCODE -ne 0) { throw "publish failed" }
}
