"""Tailscale + Windows Firewall offer on the Devices page (fake PowerShell, nothing changed)."""

import subprocess
import sys

import pytest

from nexvara import firewall

LAN = {"ip": "10.23.234.223", "kind": "lan"}
TS = {"ip": "100.65.206.5", "kind": "tailscale"}


class FakePs:
    def __init__(self, has_rule=False):
        self.has_rule, self.calls = has_rule, []

    def __call__(self, command, timeout=20):
        self.calls.append(command)
        if command.startswith("Start-Process"):
            self.has_rule = True  # the owner said «Ha» in the UAC prompt
            return subprocess.CompletedProcess([], 0, "", "")
        return subprocess.CompletedProcess([], 0, "yes" if self.has_rule else "no", "")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Firewall")
def test_offer_only_when_tailscale_is_here_and_the_rule_is_missing():
    ps = FakePs()
    assert firewall.status([LAN], ps) == {"tailscale": "", "needed": False}
    assert ps.calls == []  # no Tailscale: PowerShell is not even asked
    assert firewall.status([LAN, TS], ps) == {"tailscale": "100.65.206.5", "needed": True}
    assert firewall.add_rule(8765, ps) is True
    cmd = ps.calls[-2]
    assert "-Verb RunAs" in cmd and "-LocalPort 8765" in cmd and "100.64.0.0/10" in cmd
    assert "-Program" in cmd and "Inbound" in cmd and "Allow" in cmd
    assert firewall.status([LAN, TS], ps)["needed"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Firewall")
def test_refused_prompt_and_broken_powershell():
    class Refused(FakePs):
        def __call__(self, command, timeout=20):
            if command.startswith("Start-Process"):
                return subprocess.CompletedProcess([], 1, "", "canceled")
            return super().__call__(command, timeout)

    assert firewall.add_rule(8765, Refused()) is False

    def broken(command, timeout=20):
        raise OSError("powershell missing")

    assert firewall.status([TS], broken) == {"tailscale": "100.65.206.5", "needed": False,
                                             "unknown": True}  # fmt: skip


def test_devices_page_api(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    state = {"rule": False}
    api = Api(overrides={
        "firewall_status": lambda addrs: {"tailscale": "100.65.206.5", "needed": not state["rule"]},
        "firewall_add": lambda port: state.update(rule=True) or True,
    })  # fmt: skip
    assert api.devices_tailscale()["needed"] is True
    r = api.devices_allow_tailscale()
    assert r["ok"] and r["needed"] is False
