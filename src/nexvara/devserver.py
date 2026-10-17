"""Demo phone server for building the Android app without Office or real data.

    .venv\\Scripts\\python.exe -m nexvara.devserver [--port 8765]

Runs the real /api/v1 server (HTTPS, pairing, tokens, long-poll) in a throwaway data folder,
with a fake agent: every chat message starts a 3-step task that produces a small text file.
Prints the pairing link (the same content as the QR code) with the certificate fingerprint.
"""

from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nexvara.devserver")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    folder = Path(tempfile.mkdtemp(prefix="nexvara-dev-"))
    os.environ["NEXVARA_DATA"] = str(folder)

    from nexvara.ai.keys import MemoryKeyStore
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore
    from nexvara.remote import DeviceStore
    from nexvara.workflows import WorkflowStore

    runner = TaskRunner()

    def fake_task(text: str):
        def fn(task: Any) -> dict[str, Any]:
            for name in ("Buyruqni tushunish", "Bajarish", "Tekshirish"):
                with task.step(name) as s:
                    time.sleep(1.5)
                    s.detail = "demo"
            out = folder / f"natija-{task.id}.txt"
            out.write_text(f"NEXVARA demo natijasi: {text}\n", encoding="utf-8")
            return {"path": str(out)}

        return fn

    class DemoApi(Api):
        def chat(self, text: str) -> dict[str, Any]:
            task = runner.start(f"Demo: {text[:40]}", fake_task(text))
            return {"reply": f"Demo: «{text}» bajarilyapti", "task": task.snapshot()}

    mem = MemoryStore(folder / "app.db")
    mem.add_fact("Demo: maktabim 21-maktab")
    # No real key, no paid call: the AI panel shows zero spend with the real limits layout.
    router = AiRouter(Settings(folder / "settings.json"), MemoryKeyStore({}),
                      Ledger(folder / "app.db"))  # fmt: skip
    api = DemoApi(runner, overrides={
        "device_store": DeviceStore(folder / "app.db"), "remote_port": args.port,
        "memory": mem, "workflow_store": WorkflowStore(folder / "app.db"),
        "ai_router": router, "sync_keys": MemoryKeyStore({}),
        "make_test": fake_task("darslikdan test"),
        **{k: fake_task(k) for k in ("excel_demo", "excel_dashboard", "word_report",
                                     "presentation")},
    })  # fmt: skip
    demo_csv = folder / "savdo.csv"
    rows = ["Sana,Hudud,Summa", "2026-01-05,Toshkent,1200", "2026-02-07,Samarqand,2500",
            "2026-03-09,Toshkent,1800", "2026-03-20,Buxoro,900"]  # fmt: skip
    demo_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    auto = api.bi_auto(str(demo_csv))
    if auto.get("ok"):
        api.bi_save({**auto["config"], "name": "Demo savdo"})
    r = api.devices_start()
    if not r.get("ok"):
        print(r.get("error"))
        return 1
    srv = api._server()
    print("NEXVARA demo server:", srv.url())
    print("Pairing link (QR content):", srv.pair_link())
    print("Certificate SHA-256:", srv.fingerprint)
    print("Data folder:", folder, "\nCtrl+C to stop. New code: press Enter.")
    try:
        while True:
            input()
            srv.new_code()
            print("Pairing link:", srv.pair_link())
    except (KeyboardInterrupt, EOFError):
        api.devices_stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
