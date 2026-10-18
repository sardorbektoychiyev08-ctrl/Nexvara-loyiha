# PyInstaller build of NEXVARA.exe (one folder, no console). Run via scripts\build.ps1.
# ruff: noqa
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = SPECPATH + "\\.."
datas = collect_data_files("nexvara", includes=["app/ui/*"])
binaries = []
hiddenimports = collect_submodules("nexvara") + ["win32timezone"]
for pkg in ("webview", "pymupdf", "segno", "winrt", "telethon", "anthropic", "openpyxl",
            "ezdxf", "PIL"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [SPECPATH + "\\launch.py"],
    pathex=[ROOT + "\\src"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["pytest", "ruff", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NEXVARA",
    console=False,
    icon=ROOT + "\\build\\nexvara.ico",
    version=ROOT + "\\build\\version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, name="NEXVARA")
