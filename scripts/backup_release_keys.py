"""Back up / restore the release signing keys (D:\\NEXVARA\\release) as one encrypted file.

    python scripts\\backup_release_keys.py backup <out.nxkeys>       # asks for a password
    python scripts\\backup_release_keys.py restore <file.nxkeys> [folder]

The file is sealed like the sync files (scrypt -> AES-256-GCM, nexvara.sync.seal): without the
password it is unreadable, so it may be kept in OneDrive or on a phone. The Android keystore's
own password (Windows Credential Manager, NEXVARA/release/android) is put inside too, so a new
PC can build signed releases after `restore`. Restore never overwrites an existing file.
"""

from __future__ import annotations

import base64
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nexvara.ai.keys import KeyStore  # noqa: E402
from nexvara.sync import seal, unseal  # noqa: E402

SOURCE = Path(r"D:\NEXVARA\release")


def backup(out: Path, password: str) -> int:
    files = {p.name: base64.b64encode(p.read_bytes()).decode() for p in SOURCE.iterdir()
             if p.is_file()}  # fmt: skip
    if not files:
        raise SystemExit(f"{SOURCE} bo‘sh")
    blob = seal({"files": files, "android_password": KeyStore("NEXVARA/release/").load("android")
                 or ""}, password)  # fmt: skip
    out.write_bytes(blob)
    if sorted(unseal(out.read_bytes(), password)["files"]) != sorted(files):
        raise SystemExit("Tekshiruv o‘tmadi")
    return len(files)


def restore(src: Path, folder: Path, password: str) -> list[str]:
    data = unseal(src.read_bytes(), password)
    folder.mkdir(parents=True, exist_ok=True)
    done = []
    for name, b64 in data["files"].items():
        target = folder / name
        if target.exists():
            print(f"bor, tegilmadi: {target}")
            continue
        target.write_bytes(base64.b64decode(b64))
        done.append(name)
    if data.get("android_password") and not KeyStore("NEXVARA/release/").load("android"):
        KeyStore("NEXVARA/release/").save("android", data["android_password"])
    return done


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("backup", "restore"):
        raise SystemExit(__doc__)
    password = getpass.getpass("Parol: ")
    if sys.argv[1] == "backup":
        if len(password) < 12 or getpass.getpass("Parol (yana): ") != password:
            raise SystemExit("Parol kamida 12 belgi va ikki marta bir xil bo‘lsin")
        print(f"Tayyor: {backup(Path(sys.argv[2]), password)} ta fayl -> {sys.argv[2]}")
    else:
        folder = Path(sys.argv[3]) if len(sys.argv) > 3 else SOURCE
        print("Tiklandi:", restore(Path(sys.argv[2]), folder, password) or "hech narsa")


if __name__ == "__main__":
    main()
