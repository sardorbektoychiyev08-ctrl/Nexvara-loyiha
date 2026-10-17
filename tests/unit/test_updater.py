"""Updater: signed manifest, verified download, failed-update recovery, rollback.

A throwaway Ed25519 key signs the test channel; no installer is really started.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def channel(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara import updater

    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "k.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                           serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))  # fmt: skip
    pub = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()  # fmt: skip
    ch = tmp_path / "releases"

    def release(version, body=b"MZ installer"):
        exe = tmp_path / f"build-{version}.exe"
        exe.write_bytes(body)
        return updater.publish(exe, version, ch, "Yangi imkoniyatlar", key_path=key_path)

    def make(current="0.1.0"):
        return updater.Updater(str(ch), current=current, folder=tmp_path / "data" / "updates",
                               public_key=pub)  # fmt: skip

    return release, make, ch


def test_check_download_install_success(channel):
    release, make, ch = channel
    release("0.2.0")
    upd = make()
    r = upd.check()
    assert r["available"] and r["version"] == "0.2.0" and r["notes"] == "Yangi imkoniyatlar"
    exe = upd.download(r["manifest"])
    assert exe.read_bytes() == b"MZ installer"
    started = []
    upd.install(exe, "0.2.0", run=started.append)
    assert started[0][0] == str(exe) and "/VERYSILENT" in started[0]
    assert (upd.folder / "pending.json").is_file()
    after = make("0.2.0").after_start()  # the app restarted as the new version
    assert after == {"state": "updated", "from": "0.1.0", "to": "0.2.0"}
    assert make("0.2.0").after_start() == {"state": "none"}
    assert make("0.2.0").check()["available"] is False


def test_tampered_manifest_or_installer_is_refused(channel):
    release, make, ch = channel
    from nexvara.updater import UpdateError

    release("0.2.0")
    m = json.loads((ch / "latest.json").read_text("utf-8"))
    m["sha256"] = "0" * 64
    (ch / "latest.json").write_text(json.dumps(m), "utf-8")  # signature no longer matches
    with pytest.raises(UpdateError, match="imzosi"):
        make().check()
    release("0.2.0")
    (ch / "NEXVARA-Setup-0.2.0.exe").write_bytes(b"MZ virus!!!!")  # same size, other bytes
    upd = make()
    with pytest.raises(UpdateError, match="buzilgan"):
        upd.download(upd.check()["manifest"])
    assert not list((upd.folder / "0.2.0").glob("*.exe"))


def test_failed_update_and_rollback(channel):
    release, make, ch = channel
    release("0.2.0", b"MZ v2")
    upd = make()
    upd.install(upd.download(upd.check()["manifest"]), "0.2.0", run=lambda a: None)
    make("0.2.0").after_start()
    release("0.3.0", b"MZ v3")
    upd = make("0.2.0")
    upd.install(upd.download(upd.check()["manifest"]), "0.3.0", run=lambda a: None)
    # The installer failed: the old version starts again.
    after = make("0.2.0").after_start()
    assert after["state"] == "failed" and after["rollback"] == "0.2.0"
    started = []
    exe = make("0.2.0").rollback("0.2.0", run=started.append)
    assert exe.read_bytes() == b"MZ v2" and started


def test_channel_rules(channel, tmp_path):
    release, make, ch = channel
    from nexvara.updater import UpdateError, Updater, parse_version

    with pytest.raises(UpdateError, match="sozlanmagan"):
        Updater("").check()
    with pytest.raises(UpdateError, match="https"):
        Updater("http://example.com").check()
    assert parse_version("v1.10.0") > parse_version("1.9.9")


def test_settings_reject_plain_http(tmp_path):
    from nexvara.appdata import Settings

    s = Settings(tmp_path / "settings.json")
    with pytest.raises(ValueError):
        s.update({"update": {"channel": "http://x"}})
    assert s.update({"update": {"channel": "D:\\NEXVARA\\releases"}})["update"]["auto_check"]


def test_api_update_flow(channel):
    release, make, ch = channel
    from nexvara.app.api import Api

    started = []
    api = Api(overrides={"updater": make(), "update_run": started.append})
    assert api.update_check()["ok"] is False  # nothing published yet
    release("0.2.0")
    st = api.update_check()
    assert st["ok"] and st["check"]["version"] == "0.2.0"
    r = api.update_install()
    assert r["ok"] and r["installing"] == "0.2.0" and started


def test_installer_copy_is_a_rollback_target(channel, tmp_path):
    """A version installed by hand left its installer copy (installer/nexvara.iss)."""
    release, make, ch = channel
    from nexvara import updater

    kept = tmp_path / "installers"
    (kept / "1.0.0").mkdir(parents=True)
    (kept / "1.0.0" / "NEXVARA-Setup-1.0.0.exe").write_bytes(b"MZ old")
    upd = updater.Updater(str(ch), current="1.0.0", folder=tmp_path / "upd", kept=kept)
    assert upd.installed_versions() == ["1.0.0"]
    started = []
    exe = upd.rollback("1.0.0", run=started.append)
    assert exe.parent == kept / "1.0.0" and started


def test_start_banner_checks_only_when_allowed(channel):
    release, make, ch = channel
    from nexvara.app.api import Api

    started = []
    off = Api(overrides={"updater": make(), "update_run": started.append,
                         "update_settings": {"auto_check": False, "channel": str(ch)}})  # fmt: skip
    release("0.2.0")
    assert off.update_auto()["checked"] is False
    on = Api(overrides={"updater": make(), "update_run": started.append,
                        "update_settings": {"auto_check": True, "channel": str(ch)}})  # fmt: skip
    r = on.update_auto()
    assert r["checked"] and r["available"] and r["version"] == "0.2.0"
    assert not started and not (make().folder / "0.2.0").exists()  # nothing downloaded
