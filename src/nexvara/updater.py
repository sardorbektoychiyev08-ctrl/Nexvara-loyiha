"""Updates from a private release channel, verified before anything runs.

Channel = a folder (e.g. D:\\NEXVARA\\releases or a network share) or an https URL that holds:
    latest.json      {"version", "installer", "sha256", "size", "notes", "published"}
    latest.json.sig  base64 Ed25519 signature of latest.json's exact bytes
    NEXVARA-Setup-<version>.exe
Only a manifest signed by the release key (public half below; the private half stays in
D:\\NEXVARA\\release\\signing_key.pem, never in Git) is accepted, and the installer must
match its SHA-256 and size. Before installing, the state is written to updates\\pending.json;
on the next start `after_start()` decides: the new version runs -> success (the installer is
kept for rollback), otherwise -> failed update, the previous installer can be run again.
User data (D:\\NEXVARA: settings, app.db, textbooks) is never touched by the installer.

    python -m nexvara.updater keygen               # once, on the release PC
    python -m nexvara.updater publish <exe> <ver> <channel-folder> ["notes"]
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from nexvara import __version__, config

# Ed25519 public key of NEXVARA releases (raw 32 bytes, base64).
RELEASE_PUBLIC_KEY = "n45jv/0IB459WEs6x/6PZTRoWCZmchm3+uJRg04hcYY="
KEEP_INSTALLERS = 2
SILENT_ARGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]


class UpdateError(Exception):
    """Shown to the user (Uzbek)."""


def parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("v").split("."))
    except ValueError as e:
        raise UpdateError(f"Versiya noto‘g‘ri: {v!r}") from e


def signing_key_path() -> Path:
    return config.data_dir() / "release" / "signing_key.pem"


def verify_manifest(raw: bytes, sig_b64: bytes, public_key_b64: str = RELEASE_PUBLIC_KEY) -> dict:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    try:
        pub.verify(base64.b64decode(sig_b64.strip()), raw)
    except (InvalidSignature, ValueError) as e:
        raise UpdateError("Yangilanish imzosi noto‘g‘ri — o‘rnatilmaydi") from e
    m = json.loads(raw)
    for k in ("version", "installer", "sha256", "size"):
        if k not in m:
            raise UpdateError(f"Yangilanish ma’lumotida «{k}» yo‘q")
    if Path(m["installer"]).name != m["installer"]:
        raise UpdateError("Yangilanish fayl nomi xavfli")
    parse_version(m["version"])
    return m


class Updater:
    def __init__(self, channel: str, current: str = __version__, folder: Path | None = None,
                 public_key: str = RELEASE_PUBLIC_KEY) -> None:  # fmt: skip
        self.channel = channel.strip()
        self.current = current
        self.folder = folder or (config.data_dir() / "updates")
        self.public_key = public_key

    # ----- channel access -----
    def _read(self, name: str, limit: int = 1 << 20) -> bytes:
        if not self.channel:
            raise UpdateError("Yangilanish kanali sozlanmagan (Sozlamalar → Yangilanish)")
        if self.channel.startswith("https://"):
            url = self.channel.rstrip("/") + "/" + name
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    return r.read(limit + 1)[: limit + 1]
            except OSError as e:
                raise UpdateError(f"Yangilanish serveriga ulanib bo‘lmadi: {e}") from e
        if self.channel.startswith("http://"):
            raise UpdateError("Faqat https:// yoki papka kanali qabul qilinadi")
        p = Path(self.channel) / name
        try:
            with p.open("rb") as f:
                return f.read(limit + 1)
        except OSError as e:
            raise UpdateError(f"Yangilanish papkasi o‘qilmadi: {e}") from e

    def check(self) -> dict[str, Any]:
        raw = self._read("latest.json")
        m = verify_manifest(raw, self._read("latest.json.sig"), self.public_key)
        newer = parse_version(m["version"]) > parse_version(self.current)
        return {"available": newer, "current": self.current, "version": m["version"],
                "notes": m.get("notes", ""), "size": m["size"], "manifest": m}  # fmt: skip

    def download(self, manifest: dict[str, Any]) -> Path:
        """Installer into updates\\<version>\\, verified; a bad file is deleted."""
        target_dir = self.folder / manifest["version"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / manifest["installer"]
        part = target.with_suffix(".part")
        size = int(manifest["size"])
        data = self._read(manifest["installer"], limit=size)
        part.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != size or digest != str(manifest["sha256"]).lower():
            part.unlink(missing_ok=True)
            raise UpdateError("Yuklangan fayl buzilgan (SHA-256 mos emas) — o‘rnatilmaydi")
        part.replace(target)
        return target

    # ----- install / recovery -----
    def _pending(self) -> Path:
        return self.folder / "pending.json"

    def installed_versions(self) -> list[str]:
        """Versions whose verified installer is kept (newest first) — rollback targets."""
        out = []
        for d in self.folder.glob("*") if self.folder.is_dir() else []:
            if d.is_dir() and any(d.glob("*.exe")):
                try:
                    out.append((parse_version(d.name), d.name))
                except UpdateError:
                    continue
        return [v for _k, v in sorted(out, reverse=True)]

    def install(self, installer: Path, version: str, run: Any = subprocess.Popen) -> None:
        """Start the installer silently; the caller then closes the app (the installer
        relaunches it)."""
        previous = next((v for v in self.installed_versions()
                         if parse_version(v) < parse_version(version)), "")  # fmt: skip
        self._pending().write_text(json.dumps({
            "from": self.current, "to": version, "installer": str(installer),
            "previous": previous, "started": time.time(),
        }), "utf-8")  # fmt: skip
        log = self.folder / f"install-{version}.log"
        run([str(installer), *SILENT_ARGS, f"/LOG={log}"])

    def after_start(self) -> dict[str, Any]:
        """Call once at app start. Reports the result of an update started last time."""
        p = self._pending()
        if not p.is_file():
            return {"state": "none"}
        try:
            info = json.loads(p.read_text("utf-8"))
        except ValueError:
            p.unlink(missing_ok=True)
            return {"state": "none"}
        if parse_version(self.current) == parse_version(info["to"]):
            p.unlink()
            self._prune()
            return {"state": "updated", "from": info["from"], "to": info["to"]}
        failed = self.folder / "failed.json"
        failed.write_text(json.dumps({**info, "running": self.current}), "utf-8")
        p.unlink()
        return {"state": "failed", "to": info["to"], "running": self.current,
                "rollback": info.get("previous", "")}  # fmt: skip

    def rollback(self, version: str, run: Any = subprocess.Popen) -> Path:
        """Reinstall a kept (already verified) older installer."""
        d = self.folder / version
        exes = sorted(d.glob("*.exe")) if d.is_dir() else []
        if not exes:
            raise UpdateError(f"{version} versiyasining o‘rnatuvchisi saqlanmagan")
        self.install(exes[0], version, run)
        return exes[0]

    def _prune(self) -> None:
        for v in self.installed_versions()[KEEP_INSTALLERS:]:
            shutil.rmtree(self.folder / v, ignore_errors=True)


# ----- release side -----
def keygen(path: Path | None = None) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    path = path or signing_key_path()
    if path.exists():
        raise SystemExit(f"{path} allaqachon bor — ustiga yozilmaydi")
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                       serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))  # fmt: skip
    raw = key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw)  # fmt: skip
    return base64.b64encode(raw).decode()


def publish(installer: Path, version: str, channel: Path, notes: str = "",
            key_path: Path | None = None) -> dict[str, Any]:  # fmt: skip
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key((key_path or signing_key_path()).read_bytes(), None)
    channel.mkdir(parents=True, exist_ok=True)
    data = installer.read_bytes()
    name = f"NEXVARA-Setup-{version}.exe"
    shutil.copyfile(installer, channel / name)
    manifest = {"version": version, "installer": name, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "notes": notes,
                "published": time.strftime("%Y-%m-%dT%H:%M:%S")}  # fmt: skip
    raw = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    (channel / "latest.json").write_bytes(raw)
    (channel / "latest.json.sig").write_bytes(base64.b64encode(key.sign(raw)))
    return manifest


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["keygen"]:
        print("RELEASE_PUBLIC_KEY =", keygen())
    elif args[:1] == ["publish"] and len(args) >= 4:
        print(json.dumps(publish(Path(args[1]), args[2], Path(args[3]),
                                 args[4] if len(args) > 4 else ""), indent=2))  # fmt: skip
    else:
        print(__doc__)
