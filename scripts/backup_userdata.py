"""Back up and restore NEXVARA user data (D:\\NEXVARA) before an install or update.

    python scripts\\backup_userdata.py backup                 # -> D:\\NEXVARA-zaxira\\<time>\\
    python scripts\\backup_userdata.py verify <backup-folder>  # every file vs its SHA-256
    python scripts\\backup_userdata.py restore <backup-folder> --to <empty folder>
    python scripts\\backup_userdata.py restore <backup-folder> --to D:\\NEXVARA --i-approve

What is copied: the whole data folder (textbooks, settings, app.db, the textbook index,
Google profile and client file, release signing key, phone certificate, BI dashboards,
Telegram session...), SQLite files through SQLite's own backup (safe while the app runs),
plus the desktop shortcut. Windows Credential Manager secrets (Google session, sync
passphrase, AI keys) are NOT exported — they are never written to a file; only their names
are listed so a check can confirm they are still there. An install or update never touches
the data folder or Credential Manager.
Restore never overwrites silently: into a non-empty folder only with --i-approve, and the
current files are first moved to <folder>.before-restore-<time>.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DATA = Path("D:/NEXVARA")
ROOT = Path("D:/NEXVARA-zaxira")
SKIP_DIRS = {"tmp"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def credential_names() -> list[str]:
    cmd = ["cmdkey", "/list"]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout
    return sorted({line.split("target=", 1)[1].strip() for line in out.splitlines()
                   if "target=NEXVARA" in line})  # fmt: skip


def desktop_shortcuts() -> list[Path]:
    home = Path.home()
    places = (home / "OneDrive" / "Desktop", home / "Desktop")
    return [p / "NEXVARA.lnk" for p in places if (p / "NEXVARA.lnk").is_file()]


def backup(data: Path = DATA, root: Path = ROOT) -> Path:
    dest = root / time.strftime("%Y%m%d-%H%M%S")
    files: dict[str, dict] = {}
    for src in sorted(data.rglob("*")):
        rel = src.relative_to(data)
        if not src.is_file() or rel.parts[0] in SKIP_DIRS:
            continue
        target = dest / "data" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".db":
            ro = f"file:{src}?mode=ro"
            with sqlite3.connect(ro, uri=True) as db, sqlite3.connect(target) as t:
                db.backup(t)  # consistent even while the app has the database open
        else:
            shutil.copy2(src, target)
        files[rel.as_posix()] = {"size": target.stat().st_size, "sha256": sha256(target)}
    for lnk in desktop_shortcuts():
        (dest / "shortcuts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(lnk, dest / "shortcuts" / lnk.name)
    manifest = {"created": time.time(), "source": str(data), "files": files,
                "credentials_present": credential_names(),
                "note": "Credential Manager secrets are not exported (by design)."}  # fmt: skip
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), "utf-8")
    return dest


def verify(dest: Path) -> list[str]:
    m = json.loads((dest / "manifest.json").read_text("utf-8"))
    bad = []
    for rel, info in m["files"].items():
        p = dest / "data" / rel
        if not p.is_file() or p.stat().st_size != info["size"] or sha256(p) != info["sha256"]:
            bad.append(rel)
    return bad


def restore(dest: Path, to: Path, approve: bool) -> dict:
    if to.exists() and any(to.iterdir()):
        if not approve:
            raise SystemExit(f"{to} bo‘sh emas: tiklash uchun --i-approve kerak (avval eski "
                             "fayllar alohida papkaga ko‘chiriladi)")  # fmt: skip
        keep = to.with_name(f"{to.name}.before-restore-{time.strftime('%Y%m%d-%H%M%S')}")
        to.rename(keep)
    shutil.copytree(dest / "data", to)
    m = json.loads((dest / "manifest.json").read_text("utf-8"))
    wrong = [r for r, i in m["files"].items() if sha256(to / r) != i["sha256"]]
    return {"restored": len(m["files"]), "mismatch": wrong, "to": str(to)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backup", "verify", "restore"])
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--to")
    ap.add_argument("--i-approve", action="store_true")
    a = ap.parse_args()
    if a.cmd == "backup":
        dest = backup()
        bad = verify(dest)
        m = json.loads((dest / "manifest.json").read_text("utf-8"))
        size = sum(f["size"] for f in m["files"].values())
        print(json.dumps({"backup": str(dest), "files": len(m["files"]),
                          "gb": round(size / 1e9, 2), "verify_errors": bad,
                          "credentials_present": m["credentials_present"]}, indent=1))  # fmt: skip
        return 1 if bad else 0
    if a.cmd == "verify":
        bad = verify(Path(a.folder))
        print(json.dumps({"verify_errors": bad}))
        return 1 if bad else 0
    print(json.dumps(restore(Path(a.folder), Path(a.to), a.i_approve), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
