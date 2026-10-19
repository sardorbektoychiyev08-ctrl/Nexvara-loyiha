"""Windows Firewall and Tailscale: let the paired phone reach NEXVARA from any network.

Windows usually lets NEXVARA in only on the network type the owner clicked «Ruxsat berish» for
(often «Public» Wi‑Fi), while the Tailscale adapter is a «Private» network — so the phone sees
«Aloqa yo‘q» over Tailscale. When this PC has a Tailscale address and the NEXVARA rule is
missing, the Devices page offers one button: it adds a single inbound rule (TCP on the phone
port, only from Tailscale addresses 100.64.0.0/10, only for this program). Adding it needs
administrator rights, so Windows shows its own «Ruxsat berasizmi?» prompt; nothing else is
changed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

RULE = "NEXVARA (Tailscale)"
TAILNET = "100.64.0.0/10"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def _ps(command: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, timeout=timeout,
                          creationflags=_NO_WINDOW if sys.platform == "win32" else 0)  # fmt: skip


def program() -> str:
    """The program the rule is for: NEXVARA.exe when installed, else this Python."""
    return str(Path(sys.executable).resolve())


def rule_exists(run: Any = _ps) -> bool:
    out = run(f"if (Get-NetFirewallRule -DisplayName '{RULE}' -ErrorAction SilentlyContinue) "
              "{ 'yes' } else { 'no' }")  # fmt: skip
    return out.stdout.strip().endswith("yes")


def status(addresses: list[dict[str, str]], run: Any = _ps) -> dict[str, Any]:
    """For the Devices page: is Tailscale on this PC, and does the phone need the rule?"""
    tail = next((a["ip"] for a in addresses if a.get("kind") == "tailscale"), "")
    if not tail or sys.platform != "win32":
        return {"tailscale": tail, "needed": False}
    try:
        ok = rule_exists(run)
    except (OSError, subprocess.SubprocessError):
        return {"tailscale": tail, "needed": False, "unknown": True}
    return {"tailscale": tail, "needed": not ok}


def add_rule(port: int, run: Any = _ps) -> bool:
    """Ask Windows (UAC) to add the rule; True when it exists afterwards."""
    exe = program().replace("'", "''")
    inner = (f"New-NetFirewallRule -DisplayName '{RULE}' -Direction Inbound -Action Allow "
             f"-Protocol TCP -LocalPort {int(port)} -RemoteAddress {TAILNET} -Program '{exe}' "
             "-Profile Private,Public | Out-Null")  # fmt: skip
    outer = ("Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "
             "'-NoProfile','-Command',\"" + inner.replace('"', '`"') + "\"")  # fmt: skip
    try:
        run(outer, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return False
    return rule_exists(run)
