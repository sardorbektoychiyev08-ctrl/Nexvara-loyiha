"""NEXVARA keeps serving the phone when its window is closed.

With phone access on, closing the window only hides it; NEXVARA started with Windows
(`--background`) opens hidden. Starting NEXVARA again does not open a second copy: it asks the
running one to show its window. «NEXVARA’ni to‘liq yopish» (Devices page) really quits.
"""

from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Callable

PORT = 8764  # localhost only: «show your window» from a second start
_MSG = b"NEXVARA-SHOW"

log = logging.getLogger(__name__)


def claim_single_instance(on_show: Callable[[], None], port: int = PORT) -> socket.socket | None:
    """The first copy listens and returns its socket; a second copy asks it to show the window
    and gets None (it should exit)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", port))
    except OSError:
        srv.close()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
                c.sendall(_MSG)
        except OSError:
            log.warning("another NEXVARA holds port %s but did not answer", port)
        return None
    srv.listen(4)

    def serve() -> None:
        while True:
            try:
                conn, _addr = srv.accept()
            except OSError:
                return  # closed on exit
            with conn:
                conn.settimeout(3)
                try:
                    if conn.recv(64) == _MSG:
                        on_show()
                except OSError:
                    pass

    threading.Thread(target=serve, name="single-instance", daemon=True).start()
    return srv


def keep_running(settings: dict) -> bool:
    """Phone access on: the window may close, NEXVARA must stay."""
    return bool((settings.get("remote") or {}).get("enabled"))
