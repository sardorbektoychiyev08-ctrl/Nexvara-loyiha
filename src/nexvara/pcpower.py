"""Starting NEXVARA with Windows, and what the phone needs to wake this PC (Wake-on-LAN).

Autostart is the per-user Run key (HKCU, no admin): NEXVARA opens at sign-in and, if phone
access was on, it is on again. Wake-on-LAN needs this PC's network card MAC address and the
local broadcast address; the network card / BIOS option «Wake on LAN» must be on in Windows.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "NEXVARA"


def _command() -> str:
    # --background: with phone access on, NEXVARA starts hidden and only serves the phone
    if getattr(sys, "frozen", False):  # the installed NEXVARA.exe
        return f'"{sys.executable}" --background'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" -m nexvara.app.main --background'


def refresh_autostart() -> None:
    """An older version wrote the Run key without --background: rewrite it once."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value = winreg.QueryValueEx(k, NAME)[0]
    except OSError:
        return  # autostart is off
    if value != _command():
        set_autostart(True)


def autostart_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> bool:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
    return autostart_enabled()


_MAC = re.compile(r"\b([0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5})\b")
_IP = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")


def wake_info(lan_ip: str, ipconfig: str | None = None) -> dict[str, str] | None:
    """{"mac", "broadcast"} of the adapter that owns `lan_ip` (from `ipconfig /all`, any
    Windows language: matched by value shapes, not by the localized labels)."""
    if ipconfig is None:
        try:
            ipconfig = subprocess.run(
                ["ipconfig", "/all"], capture_output=True, timeout=10, creationflags=0x08000000
            ).stdout.decode("cp866", "replace")
        except (OSError, subprocess.SubprocessError):
            return None
    blocks = re.split(r"\r?\n(?=\S)", ipconfig)
    for b in blocks:
        ips = _IP.findall(b)
        if lan_ip not in ips:
            continue
        mac = _MAC.search(b)
        if not mac:
            return None
        mask = next((x for x in ips if x.startswith("255.")), "255.255.255.0")
        try:
            net = ipaddress.ip_network(f"{lan_ip}/{mask}", strict=False)
            bcast = str(net.broadcast_address)
        except ValueError:
            bcast = "255.255.255.255"
        return {"mac": mac.group(1).replace("-", ":").upper(), "broadcast": bcast}
    return None
