"""Publish a signed release to the public GitHub updates repository (the internet channel).

    python scripts\\publish_github.py <folder> <tag> [notes]

<folder> holds what `build.ps1 -Publish <folder>` wrote (latest.json, latest.json.sig, the
installer) and optionally the Android APK. A GitHub release <tag> is created in
UPDATES_REPO and every file of the folder is attached. The apps then read
https://github.com/<UPDATES_REPO>/releases/latest/download/latest.json — still verified
with the Ed25519 signature and SHA-256 before anything is installed.

The token is the one Git already keeps in Windows Credential Manager (git credential fill);
it is never printed or saved anywhere else. Only installers go to this public repository,
never source code or keys.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

UPDATES_REPO = "sardorbektoychiyev08-ctrl/nexvara-yangilanish"
API = f"https://api.github.com/repos/{UPDATES_REPO}"
UPLOADS = f"https://uploads.github.com/repos/{UPDATES_REPO}"
ALLOWED = (".json", ".sig", ".exe", ".apk")


def _token() -> str:
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("GitHub ruxsati topilmadi (git credential)")


def _call(method: str, url: str, token: str, data: bytes | None = None,
          ctype: str = "application/json") -> dict:  # fmt: skip
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": ctype, "User-Agent": "NEXVARA-publish"})  # fmt: skip
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read() or b"{}")


def publish(folder: Path, tag: str, notes: str = "") -> str:
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED)
    names = {p.name for p in files}
    if not {"latest.json", "latest.json.sig"} <= names:
        raise SystemExit("latest.json va latest.json.sig kerak (build.ps1 -Publish)")
    manifest = json.loads((folder / "latest.json").read_text("utf-8"))
    if manifest["installer"] not in names:
        raise SystemExit(f"{manifest['installer']} papkada yo‘q")
    token = _token()
    text = notes or manifest.get("notes", "")
    body = json.dumps({"tag_name": tag, "name": f"NEXVARA {manifest['version']}", "body": text,
                       "draft": False}).encode()  # fmt: skip
    rel = _call("POST", f"{API}/releases", token, body)
    for p in files:
        _call("POST", f"{UPLOADS}/releases/{rel['id']}/assets?name={p.name}", token,
              p.read_bytes(), "application/octet-stream")  # fmt: skip
        print("yuklandi:", p.name)
    return rel["html_url"]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    print(publish(Path(sys.argv[1]), sys.argv[2], " ".join(sys.argv[3:])))
