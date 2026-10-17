"""Chat commands for the sections that had only buttons (mixed into app.api.Api):

- Tasks / History: "oxirgi vazifalarni ko‘rsat";
- Memory: "nimalarni eslab qolgansan?", "xotiradan maktab haqida top";
- Devices: "telefon ulanishini yoq / o‘chir", "telefon ulanganmi?";
- Settings: "yorug‘ mavzuga o‘t", "qorong‘i mavzu".
Workflows, Files, BI and the other settings are in agent/nlu.py.
Patterns are strict on purpose: anything else falls through to the other handlers.
"""

from __future__ import annotations

import re
from typing import Any

_STATUS_UZ = {"succeeded": "✓", "failed": "✗ xato", "cancelled": "bekor", "running": "…",
              "pending": "navbatda"}  # fmt: skip


class SectionsChatApi:
    _history: Any

    def _chat_sections(self, text: str) -> dict[str, Any] | None:
        from nexvara.knowledge.textnorm import fold

        f = fold(text).strip(" ?!.")
        for fn in (self._chat_memory_recall, self._chat_history,
                   self._chat_devices, self._chat_theme):  # fmt: skip
            out = fn(f, text)
            if out is not None:
                return out
        return None

    # ----- Memory -----
    def _chat_memory_recall(self, f: str, text: str) -> dict[str, Any] | None:
        asks = re.search(
            r"\b(nima\w*|qanday)\b.*\b(eslab qol|esla|yodda tut)\w*(san|ding|siz)\b", f
        )
        lists = re.fullmatch(r"(eslatmalarim\w*|xotira\w*) ?(ni )?(korsat\w*|ochib ber)?", f)
        if asks or lists:
            mem = self._mem()
            if mem is None:
                return {"reply": "Xotira bu rejimda o‘chirilgan."}
            facts = mem.facts()
            if not facts:
                return {"reply": "Hozircha hech narsa eslab qolmaganman. «Eslab qol: ...» deb "
                        "yozing."}  # fmt: skip
            lines = [f"• {x['text']}" for x in facts[:20]]
            return {"reply": f"Eslab qolganlarim ({len(facts)}):\n" + "\n".join(lines)}
        m = re.match(r"^xotira(dan|da)\s+(.+?)\s*(haqida\w*)?\s*(ni\s+)?(top|qidir|izla)\w*$", f)
        if m:
            mem = self._mem()
            if mem is None:
                return {"reply": "Xotira bu rejimda o‘chirilgan."}
            hits = mem.search(m.group(2), limit=10)
            if not hits:
                return {"reply": f"Xotirada «{m.group(2)}» bo‘yicha hech narsa topilmadi."}
            return {"reply": f"Xotiradan «{m.group(2)}»:\n" +
                    "\n".join(f"• {h['text'][:200]}" for h in hits)}  # fmt: skip
        return None

    # ----- Tasks / History -----
    def _chat_history(self, f: str, text: str) -> dict[str, Any] | None:
        if re.search(r"\b(workflow|ish jarayon|dashboard)\w*", f):
            return None  # "workflow tarixini ko‘rsat" is the workflow's own history
        if not re.search(r"\b(oxirgi|songgi|bugungi)\s+(vazifa\w*|natija\w*|ishlar\w*)|"
                         r"\b(vazifalar|tarix)\w*\s+(ni\s+)?korsat", f):  # fmt: skip
            return None
        tasks = self.list_tasks()[:10]
        if not tasks:
            return {"reply": "Hali vazifa bajarilmagan."}
        lines = []
        for t in tasks:
            res = t.get("result") or {}
            path = res.get("path") or res.get("pdf") or ""
            lines.append(f"• {t['title']} — {_STATUS_UZ.get(t['status'], t['status'])}"
                         + (f"\n  {path}" if isinstance(path, str) and path else ""))  # fmt: skip
        return {"reply": "Oxirgi vazifalar:\n" + "\n".join(lines)}

    # ----- Devices -----
    def _chat_devices(self, f: str, text: str) -> dict[str, Any] | None:
        if not re.search(r"\btelefon\w*", f) or not re.search(
            r"\b(ula\w*|ulanish\w*|boglan\w*|uz\b|uzib|ochir\w*|yoq\b|yoqib)", f
        ):
            return None
        if re.search(r"\b(ochir\w*|uz\b|uzib|toxtat\w*)", f):
            st = self.devices_stop()
            return {"reply": "Telefon ulanishi o‘chirildi." if not st["running"]
                    else "O‘chirib bo‘lmadi."}  # fmt: skip
        if re.search(r"\b(yoq\b|yoqib|ula\b|ulash|boshla\w*)", f):
            r = self.devices_start()
            if not r.get("ok"):
                return {"reply": r.get("error", "Yoqib bo‘lmadi")}
            return {
                "reply": f"Telefon ulanishi yoqildi. Telefonda {r['url']} ni oching yoki "
                f"Devices bo‘limidagi QR kodni skanerlang. Kod: {r['code']} (10 daqiqa)."
            }
        st = self.devices_status()
        n = len(st.get("devices") or [])
        state = "yoqilgan" if st.get("running") else "o‘chiq"
        return {"reply": f"Telefon ulanishi {state}, bog‘langan qurilmalar: {n}."}

    # ----- Settings -----
    def _chat_theme(self, f: str, text: str) -> dict[str, Any] | None:
        m = re.search(r"\b(yorug|oq|qorongi|qora|tungi)\w*\s+(mavzu|rejim|fon)\w*", f)
        if not m:
            return None
        theme = "light" if m.group(1) in ("yorug", "oq") else "dark"
        r = self.save_settings({"theme": theme})
        if not r.get("ok", True):
            return {"reply": r.get("error", "Saqlanmadi")}
        return {"reply": "Yorug‘ mavzu yoqildi." if theme == "light" else "Qorong‘i mavzu yoqildi.",
                "theme": theme}  # fmt: skip
