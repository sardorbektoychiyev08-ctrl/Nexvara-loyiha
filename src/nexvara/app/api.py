"""Bridge exposed to the web UI as `window.pywebview.api`.

Every public method must return JSON-serialisable data.
"""

from __future__ import annotations

import importlib
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

from nexvara import __version__, config
from nexvara.app.api_account import AccountApi
from nexvara.app.api_agent import AgentApi, looks_like_secret
from nexvara.app.api_bi import BiApi
from nexvara.app.api_cad import CadApi
from nexvara.app.api_devices import DevicesApi
from nexvara.app.api_drawing import DrawingApi
from nexvara.app.api_files import FilesApi
from nexvara.app.api_memory import MemoryApi
from nexvara.app.api_reading import ReadingApi
from nexvara.app.api_sections import SectionsChatApi
from nexvara.app.api_sync import SyncApi
from nexvara.app.api_update import UpdateApi
from nexvara.app.api_workflows import WorkflowsApi
from nexvara.core.task import TaskFn, TaskRunner

# kind -> (task title, module, runner function). Every runner takes (task, out, keep_open=...)
# and its module has default_output_path().
OFFICE_TASKS: dict[str, tuple[str, str, str]] = {
    "excel_demo": ("Excel: 10 qatorli jadval", "nexvara.skills.excel.demo", "run_demo"),
    "excel_dashboard": (
        "Excel: savdo dashboardi",
        "nexvara.skills.excel.dashboard",
        "run_dashboard",
    ),
    "word_report": ("Word: rasmiy hisobot", "nexvara.skills.word.demo", "run_word_report"),
    "presentation": ("PowerPoint: taqdimot", "nexvara.skills.powerpoint.demo", "run_presentation"),
}


_BACKGROUND = re.compile(
    r",?\s*\b(?:orqa\s+)?fonda(?:\s+(?:bajar|ishla|qil)\w*)?\b|,?\s*\bko[‘’']?rinmas\s+holda\b",
    re.IGNORECASE,
)


def _wants_ai(text: str) -> bool:
    """'AI bilan test tuz', 'sun'iy intellekt yordamida' -> the user asks for the AI version."""
    import re

    from nexvara.knowledge.textnorm import fold

    return bool(re.search(r"\b(ai|sun.?iy intellekt\w*|aqlli)\b", fold(text)))


class Api(
    AgentApi,
    MemoryApi,
    FilesApi,
    WorkflowsApi,
    BiApi,
    DevicesApi,
    AccountApi,
    UpdateApi,
    SectionsChatApi,
    SyncApi,
    DrawingApi,
    CadApi,
    ReadingApi,
):
    """`output_dir`/`keep_office_open` exist so the UI self-test can run the real
    button flow without leaving files in Documents or Office windows open."""

    def __init__(
        self,
        runner: TaskRunner | None = None,
        excel_demo: TaskFn | None = None,
        excel_dashboard: TaskFn | None = None,
        output_dir: Path | None = None,
        keep_office_open: bool = True,
        overrides: dict[str, TaskFn] | None = None,
        persist: bool = False,
    ) -> None:
        self._runner = runner or TaskRunner()
        self._output_dir = output_dir
        self._keep_office_open = keep_office_open
        self._overrides = dict(overrides or {})
        from nexvara.agent.context import Context

        self._ctx = Context()  # conversation state: "shu fayl", "uni", last folder/dashboard...
        self._pending: dict[str, tuple[str, Any]] = {}  # AI requests waiting for "Ha"
        self._ai = None
        # The desktop app keeps history and settings in D:\NEXVARA; tests run without.
        self._history = None
        if persist:
            from nexvara.appdata import History

            self._history = History()
        prev_hook = self._runner.on_finish

        def on_finish(t: Any) -> None:
            snap = t.snapshot()
            if self._history is not None:
                self._history.save(snap)
            elif prev_hook is not None:
                prev_hook(t)
            self._ctx.task_done(snap)  # its output becomes "uni" / "natija"

        self._runner.on_finish = on_finish
        if excel_demo:
            self._overrides["excel_demo"] = excel_demo
        if excel_dashboard:
            self._overrides["excel_dashboard"] = excel_dashboard

    @property
    def _context_file(self) -> str | None:
        """ "shu fayl": the file the conversation is about."""
        return self._ctx.file or None

    @_context_file.setter
    def _context_file(self, value: str | None) -> None:
        self._ctx.file = value or ""
        if value:
            self._ctx.remember_dir(value)

    def _keep_open(self) -> bool:
        """Leave Office open after a task? The desktop app follows the user's setting."""
        if self._history is None:
            return self._keep_office_open
        from nexvara.appdata import Settings

        return bool(Settings().load()["keep_office_open"])

    def _task_fn(self, kind: str) -> TaskFn:
        if kind in self._overrides:
            return self._overrides[kind]
        _title, module_name, fn_name = OFFICE_TASKS[kind]

        def run(task: Any) -> dict[str, Any]:
            module = importlib.import_module(module_name)
            out = module.default_output_path()
            if self._output_dir is not None:
                out = self._output_dir / out.name
            return getattr(module, fn_name)(task, out, keep_open=self._keep_open())

        return run

    def _start(self, kind: str) -> dict[str, Any]:
        task = self._runner.start(OFFICE_TASKS[kind][0], self._task_fn(kind))
        return task.snapshot()

    def get_info(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "ai_connected": self._ai_ready(),
            "data_dir": str(config.data_dir()),
        }

    def chat(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"reply": ""}
        if looks_like_secret(text):  # never store or forward a pasted API key
            return {"reply": "Bu API kalitga o‘xshaydi. Kalitni chatga yozmang: u Sozlamalar → AI "
                    "bo‘limida kiritiladi va Windows Credential Manager’da saqlanadi. Bu xabar "
                    "saqlanmadi."}  # fmt: skip
        mem = self._mem()
        if mem is not None:
            mem.log_chat("user", text)
        self._ctx.add_turn("user", text)
        out = self._chat_inner(self._expand_aliases(text))
        if mem is not None:
            mem.log_chat("nexvara", out.get("reply", ""))
        self._ctx.add_turn("nexvara", out.get("reply", ""))
        return out

    def _chat_inner(self, text: str, _use_ai: bool = True) -> dict[str, Any]:
        from nexvara.agent.parse import find_file
        from nexvara.knowledge.service import parse_test_request

        section = self._chat_sections(text)  # workflows, history, memory, devices, theme
        if section is not None:
            return section
        teach = self._chat_teach(text)
        if teach is not None:
            return teach
        read = self._chat_read(text)  # "shu rasmdagi matnni o‘qi" (offline OCR or AI)
        if read is not None:
            return read
        drawn = self._chat_drawing(text)  # "... chizib ber", a photo of a hand-drawn sketch
        if drawn is not None:
            return drawn
        text = self._bind_refs(text)  # "uni PDF qil" -> the file the last step produced
        agent = self._chat_agent(text, _use_ai)  # several tasks; Files/BI/Workflows/Settings
        if agent is not None:
            return agent
        bi = self._chat_bi(text)
        if bi is not None:
            return bi
        if not find_file(text):
            found = self._chat_find_files(text)
            if found is not None:
                return found

        # A named file means an Office command, whatever words its path contains
        # ("D:\Testlar\hisobot.xlsx" is not a request for a test).
        if find_file(text):
            command = self._chat_command(text)
            if command is not None:
                return command
        req = parse_test_request(text)
        if req is not None:
            what = " ".join(
                x for x in (f"{req.grade}-sinf" if req.grade else "", req.subject or "") if x
            )
            if not self.library_info()["books"]:
                return {
                    "reply": (
                        "Test tuzish uchun avval darsliklarni qo‘shing: «Darsliklar» bo‘limida "
                        "papkani oching, PDF darsliklarni tashlang va «Yangilash»ni bosing."
                    )
                }
            params = {
                "grade": req.grade,
                "subject": req.subject,
                "topic": req.topic,
                "count": req.count,
                "variants": req.variants,
                "ai": _wants_ai(text),
            }
            self._apply_test_rules(text, params)
            snap = self.make_test(params)
            if "confirm" in snap:
                return {"reply": snap["confirm"]["text"], "confirm": snap["confirm"]["token"]}
            if "id" not in snap:  # request rejected before a task was started
                return {"reply": snap["error"]}
            topic = f", mavzu: «{req.topic}»" if req.topic else ""
            by = "AI yordamida " if params["ai"] else ""
            return {
                "reply": (
                    f"Tushundim: {what or 'darslik'}{topic}, {req.count} ta savol, "
                    f"{req.variants} ta variant. {by}Word'da tuzyapman — jarayon o‘ng panelda."
                ),
                "task": snap,
            }
        from nexvara.knowledge.service import parse_presentation_request, parse_topic_request

        pres_req = parse_presentation_request(text)
        if pres_req is not None:
            return self._chat_presentation(pres_req)
        topic_req = parse_topic_request(text)
        if topic_req is not None:
            return self._chat_topic(topic_req)
        command = self._chat_command(text)
        if command is not None:
            return command
        if _use_ai and self._ai_ready():
            return self._chat_ai(text)
        if not _use_ai:
            return {"reply": "", "unhandled": True}
        return {
            "reply": (
                "Buni tushunmadim. AI’siz men quyidagilarni bajaraman: «7-sinf fizika Nyuton "
                "qonunlari mavzusini chiqarib ber», «7-sinf fizika Nyuton qonunlari 20 ta test», "
                "«Hisobot.xlsx ni och, B ustun bo‘yicha saralab, PDF qilib saqla». Erkin savollar "
                "uchun Sozlamalar → AI bo‘limida API kalit kiriting."
            )
        }

    # ----- Teach NEXVARA in chat ("eslab qol ...", "har doim ...") -----
    def _chat_teach(self, text: str) -> dict[str, Any] | None:
        from nexvara.knowledge.textnorm import fold
        from nexvara.memory.teach import parse_teach

        f = fold(text)
        if re.search(r"\b(nimalarni|nima) (eslab qolding|eslab qolgansan|bilasan)", f):
            facts = self.memory_facts()
            rules = self.teach_rules()
            if not facts and not rules:
                return {"reply": "Hozircha hech narsa eslab qolmaganman."}
            lines = [f"• {x['text']}" for x in facts[:20]]
            lines += [f"• Qoida ({r['app_label']}): {r['text']}" for r in rules if r["enabled"]]
            return {"reply": "Eslab qolganlarim:\n" + "\n".join(lines)}
        req = parse_teach(text)
        if req is None:
            return None
        if self._mem() is None:
            return {"reply": "Xotira bu rejimda o‘chirilgan."}
        if req.error:
            return {"reply": req.error}
        cur = self._ctx.current_file(req.text)
        if req.kind == "fact" and cur and self._ctx.refers_to_file(req.text):
            # "Shu faylni eslab qol: oylik hisobot" -> the fact keeps the real path, so later
            # "oylik hisobotni och" finds it (memory aliases).
            pat = r"(?i)\b(shu|bu|ushbu|o[‘’']?sha)\s+fayl\w*|\buni\b"
            req.text = re.sub(pat, lambda _m: cur, req.text, count=1)
        import uuid

        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("teach", req)
        return {"reply": req.describe() + "\n\nSaqlaymi?", "confirm": token}

    def _save_teach(self, req: Any) -> dict[str, Any]:
        mem = self._mem()
        if req.kind == "fact":
            mem.add_fact(req.text)
            return {"reply": "Eslab qoldim ✓ (Memory bo‘limida tahrirlash mumkin)"}
        mem.add_rule(req.app, req.text)
        return {"reply": "Qoida saqlandi ✓ Endi har safar qo‘llayman (Teach NEXVARA bo‘limida "
                "o‘chirib qo‘yish yoki tahrirlash mumkin)."}  # fmt: skip

    def _apply_test_rules(self, text: str, params: dict[str, Any]) -> None:
        """Taught test defaults ("testlar doim 2 variant") fill what the request left out."""
        from nexvara.knowledge.service import _COUNT, _VARIANTS
        from nexvara.knowledge.textnorm import fold

        mem = self._mem()
        if mem is None:
            return
        from nexvara.memory.teach import defaults_for_tests

        rules = defaults_for_tests(mem)
        f = fold(text)
        if "count" in rules and not _COUNT.search(f):
            params["count"] = rules["count"]
        if "variants" in rules and not _VARIANTS.search(f):
            params["variants"] = rules["variants"]
        if rules.get("ai") and self._ai_ready():
            params["ai"] = True

    # ----- AI (optional; nothing is sent without a key and the user's budget) -----
    def _router(self):
        if self._ai is None:
            if "ai_router" in self._overrides:
                self._ai = self._overrides["ai_router"]
            else:
                from nexvara.ai.router import AiRouter

                self._ai = AiRouter()
        return self._ai

    def _ai_ready(self) -> bool:
        if self._history is None and "ai_router" not in self._overrides:
            return False  # tests and self-tests never reach a paid API
        try:
            return self._router().ready()
        except Exception:
            return False

    def _ask(self, kind: str, payload: Any, estimate: Any) -> dict[str, Any]:
        import uuid

        token = uuid.uuid4().hex[:12]
        self._pending[token] = (kind, payload)
        text = f"Bu ish pullik AI orqali bajariladi: {estimate.describe()}. Davom etaymi?"
        return {"token": token, "text": text}

    def _chat_ai(self, text: str, approved: bool = False) -> dict[str, Any]:
        """The AI path, plus a note when personal data was kept on this PC."""
        router = self._router()
        before = getattr(router, "masked_total", 0)
        out = self._chat_ai_inner(text, approved)
        hidden = getattr(router, "masked_total", 0) - before
        if hidden and out.get("reply"):
            out["reply"] += (f"\n\n🔒 {hidden} ta shaxsiy ma’lumot AI’ga yuborilmadi: "
                             "kompyuterda yashirildi va javobda qayta tiklandi.")  # fmt: skip
            out["privacy_masked"] = hidden
        return out

    def _chat_ai_inner(self, text: str, approved: bool = False) -> dict[str, Any]:
        from nexvara.agent import tools as agent_tools
        from nexvara.ai import features
        from nexvara.ai.router import NeedsConfirmation
        from nexvara.core.task import UserError

        router = self._router()
        mem = self._mem()
        try:
            facts = mem.relevant_facts(text) if mem is not None else []
            rules = [f"{r.label()}: {r.text}" for r in mem.rules(enabled_only=True)] if mem else []
            p = features.plan(router, text, agent_tools.catalog(), self._ctx.snapshot(),
                              list(self._ctx.turns)[:-1], facts, rules, approved)  # fmt: skip
            if p.kind == "tools":
                calls = [agent_tools.ToolCall(str(c["tool"]), dict(c.get("args") or {}))
                         for c in p.calls]  # fmt: skip
                if not calls:
                    return {"reply": p.say or "Nima qilishni tushunmadim, aniqroq yozing."}
                intro = f"Tushundim: {p.say}\n\n" if p.say else ""
                return self._run_calls(calls, intro=intro, from_ai=True)
            intent = p.intent
            if intent.kind in ("test", "topic", "presentation", "command") and intent.command:
                out = self._chat_inner(intent.command, _use_ai=False)
                if not out.get("unhandled"):
                    out["reply"] = f"Tushundim: «{intent.command}»\n\n" + out["reply"]
                    return out
            if intent.kind == "question":
                ans = features.answer_question(
                    router, text, approved, intent.grade, intent.subject or None, facts=facts
                )
            else:
                ans = features.chat_reply(router, text, approved, facts=facts)
        except NeedsConfirmation as e:
            ask = self._ask("chat", text, e.estimate)
            return {"reply": ask["text"], "confirm": ask["token"]}
        except UserError as e:
            return {"reply": str(e)}
        reply = ans.text
        if ans.sources:
            pages = "; ".join(f"{s['book']}, {s['page']}-bet" for s in ans.sources)
            reply += "\n\nManba: " + pages
        return {"reply": reply, "sources": ans.sources}

    def confirm_ai(self, token: str, yes: bool = True) -> dict[str, Any]:
        """The user's "Ha"/"Yo‘q" on a pending request (paid AI call or a new rule)."""
        out = self._confirm(token, yes)
        mem = self._mem()
        if mem is not None:
            mem.log_chat("user", "Ha" if yes else "Yo‘q")
            mem.log_chat("nexvara", out.get("reply", ""))
        return out

    def _confirm(self, token: str, yes: bool) -> dict[str, Any]:
        item = self._pending.pop(token, None)
        if item is None:
            return {"reply": "Bu so‘rov eskirgan; qaytadan yozing."}
        if not yes:
            return {"reply": "Bekor qilindi, hech narsa sarflanmadi."}
        kind, payload = item
        if kind == "teach":
            return self._save_teach(payload)
        if kind == "tools":
            return self._run_calls(payload, approved=True)
        if kind == "chain":
            return self._start_chain(payload, approved=True)
        if kind == "chat":
            return self._chat_ai(payload, approved=True)
        if kind == "drawing":
            return self._run_drawing(payload)
        if kind == "read":
            return self._run_read(payload)
        snap = self.make_test({**payload, "approved": True})
        if "id" not in snap:
            return {"reply": snap.get("error") or "Test boshlanmadi"}
        return {"reply": "AI test tuzmoqda — jarayon o‘ng panelda.", "task": snap}

    def ai_status(self) -> dict[str, Any]:
        return self._router().status()

    def ai_save_key(self, provider: str, key: str) -> dict[str, Any]:
        from nexvara.core.task import UserError

        try:
            info = self._router().save_key(provider, key)
        except (UserError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Kalitni tekshirib bo‘lmadi: {e}"}
        return {"ok": True, **info, "status": self._router().status()}

    def ai_save_key_from_clipboard(self, provider: str) -> dict[str, Any]:
        """One-time connection without typing: the key copied on the provider's site is read
        from the clipboard here (it never passes through the page), checked with the free
        model list, stored in Credential Manager, and the clipboard is cleared. AI stays off."""
        text = self._overrides["clipboard"]() if "clipboard" in self._overrides else _clipboard()
        if not text or not text.strip():
            return {"ok": False, "error": "Buferda kalit yo‘q: provayder saytida kalitni nusxalang"}
        r = self.ai_save_key(provider, text.strip().splitlines()[0])
        if r.get("ok"):
            if "clipboard_clear" in self._overrides:
                self._overrides["clipboard_clear"]()
            else:
                _clipboard(clear=True)
            r["clipboard_cleared"] = True
        return r

    def ai_delete_key(self, provider: str) -> dict[str, Any]:
        self._router().delete_key(provider)
        return self._router().status()

    def ai_usage(self) -> list[dict[str, Any]]:
        return self._router().ledger.recent()

    def ai_dashboard(self) -> dict[str, Any]:
        """Home page "AI balans va xarajatlar": spend vs limits (estimated) per provider."""
        return self._router().dashboard()

    def ai_balance(self, provider: str) -> dict[str, Any]:
        """The provider's REAL balance, only where an official API exists (DeepSeek). Free:
        no model is called. Others: {"supported": False} — never a made-up number."""
        from nexvara.ai import models

        if provider not in models.PROVIDERS:
            return {"supported": False, "error": "noma’lum provayder"}
        return self._router().balance(provider)

    def ai_save_limits(self, provider: str, daily_usd: Any = None, monthly_usd: Any = None,
                       task_usd: Any = None):  # fmt: skip
        """Own daily/monthly/one-task caps for one provider ("" or None = the overall limit).
        These are NEXVARA's own limits, not the provider's real spending cap."""
        from nexvara.ai import models

        if provider not in models.PROVIDERS:
            return {"ok": False, "error": "noma’lum provayder"}

        def num(v: Any) -> float | None:
            return None if v in (None, "") else float(v)

        router = self._router()
        try:  # the router's own settings (the same file in the app)
            router.settings.update({"ai": {"limits": {provider: {
                "daily_usd": num(daily_usd), "monthly_usd": num(monthly_usd),
                "task_usd": num(task_usd)}}}})  # fmt: skip
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": f"Limit noto‘g‘ri: {e}"}
        return {"ok": True, "status": router.status()}

    # ----- Office commands ("Hisobot.xlsx ni och, ... va saqla") -----
    def _chat_command(self, text: str) -> dict[str, Any] | None:
        from nexvara.agent import files
        from nexvara.agent.parse import parse_command

        # Office works in front of the user; only "fonda bajar" runs it without windows.
        bg = _BACKGROUND.search(text)
        if bg:
            text = (text[: bg.start()] + text[bg.end() :]).strip(" ,.")
        plan = parse_command(text, self._context_file)
        if plan is None:
            return None
        taught = []
        mem = self._mem()
        if mem is not None and plan.file:
            from nexvara.memory.teach import apply_rules

            plan, taught = apply_rules(plan, mem)
        if not plan.file:
            what = {"excel": "Excel", "word": "Word", "powerpoint": "PowerPoint"}.get(
                plan.app or "", "Office"
            )
            return {
                "reply": (
                    f"Qaysi {what} fayli bilan ishlashni yozing (masalan «Hisobot.xlsx») "
                    "yoki 📎 tugmasi bilan faylni tanlang."
                ),
                "plan": plan.describe(),
            }
        try:
            near = Path(self._context_file).parent if self._context_file else None
            source = files.resolve(plan.file, near)
        except LookupError as e:
            return {"reply": str(e)}
        self._context_file = str(source)
        self._ctx.command = text
        snap = self.run_command_plan(plan, str(source), background=bool(bg))
        steps = "\n".join(f"• {d}" for d in plan.describe())
        reply = f"Fayl: {source}\nBajaraman:\n{steps}"
        if taught:
            reply += "\n\nO‘rgatilgan qoidalar qo‘shildi: " + "; ".join(r.text for r in taught)
        if plan.unknown:
            reply += "\n\nTushunmadim (bajarilmaydi): " + "; ".join(f"«{u}»" for u in plan.unknown)
        return {"reply": reply, "task": snap, "plan": plan.describe()}

    def run_command_plan(self, plan: Any, source: str, background: bool = False) -> dict[str, Any]:
        if "command" in self._overrides:
            fn = self._overrides["command"]
        else:
            from nexvara.agent.excel_exec import run_excel_plan
            from nexvara.agent.ppt_exec import run_ppt_plan
            from nexvara.agent.word_exec import run_word_plan

            runner = {"excel": run_excel_plan, "word": run_word_plan,
                      "powerpoint": run_ppt_plan}[plan.app]  # fmt: skip

            def fn(task: Any) -> dict[str, Any]:
                if background:
                    return runner(task, plan, Path(source), keep_open=False, visible=False)
                return runner(task, plan, Path(source), keep_open=self._keep_open())

        title = f"Buyruq: {Path(source).name}" + (" (fonda)" if background else "")
        return self._runner.start(title, fn).snapshot()

    def pick_file(self) -> dict[str, Any]:
        """Native "open file" dialog; the chosen file becomes "shu fayl" for commands."""
        import webview

        if not webview.windows:
            return {"path": ""}
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=(
                "Office fayllar (*.xlsx;*.xlsm;*.xls;*.csv;*.docx;*.doc;*.pptx;*.ppt)",
                "AutoCAD chizmalar (*.dxf;*.dwg)",
                "Barcha fayllar (*.*)",
            ),
        )
        if not result:
            return {"path": ""}
        self._context_file = str(result[0])
        return {"path": self._context_file}

    def set_context_file(self, path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.is_absolute() or not p.is_file():
            return {"path": "", "error": "Fayl topilmadi"}
        self._context_file = str(p)
        return {"path": self._context_file}

    def get_context_file(self) -> str:
        return self._context_file or ""

    # ----- lesson presentation from a textbook topic -----
    def _chat_presentation(self, req: Any) -> dict[str, Any]:
        from nexvara.knowledge.topicdoc import lookup

        if not self.library_info()["books"]:
            return {"reply": "Taqdimot uchun avval darsliklarni «Darsliklar» bo‘limida qo‘shing."}
        try:
            topic = lookup(req)
        except (LookupError, ValueError) as e:
            return {"reply": str(e)}
        if "presentation_topic" in self._overrides:
            fn = self._overrides["presentation_topic"]
        else:
            from nexvara.agent.ppt_exec import default_presentation_path, run_topic_presentation

            def fn(task: Any) -> dict[str, Any]:
                out = None
                if self._output_dir is not None:
                    out = self._output_dir / default_presentation_path(topic).name
                return run_topic_presentation(task, req, out, keep_open=self._keep_open())

        snap = self._runner.start(f"Taqdimot: {topic.title}", fn).snapshot()
        return {
            "reply": (
                f"{topic.book.label()}, {topic.pages_label}: «{topic.title}» bo‘yicha dars "
                "taqdimotini PowerPoint'da tayyorlayapman (mazmun, tushunchalar, sanalar, "
                "savollar, uyga vazifa; ma’ruzachi izohlari bilan)."
            ),
            "task": snap,
        }

    def _chat_topic(self, req: Any) -> dict[str, Any]:
        from nexvara.knowledge.topicdoc import lookup
        from nexvara.knowledge.topics import preview

        if not self.library_info()["books"]:
            return {
                "reply": (
                    "Mavzuni topish uchun avval darsliklarni qo‘shing: «Darsliklar» bo‘limida "
                    "papkani oching, PDF darsliklarni tashlang va «Yangilash»ni bosing."
                )
            }
        try:
            topic = lookup(req)
        except (LookupError, ValueError) as e:
            return {"reply": str(e)}
        snap = self.show_topic(
            {"grade": req.grade, "subject": req.subject, "topic": req.topic}, _found=topic
        )
        return {
            "reply": (
                f"{topic.book.label()}, {topic.pages_label}:\n{topic.title}\n\n{preview(topic)}\n\n"
                "To‘liq matnni Word'da, asl sahifalarni (rasm va formulalar bilan) PDF'da "
                "ochyapman."
            ),
            "task": snap,
        }

    def show_topic(self, params: dict[str, Any], _found: Any = None) -> dict[str, Any]:
        from nexvara.knowledge.topicdoc import TopicRequest

        grade = params.get("grade")
        req = TopicRequest(
            grade=int(grade) if grade not in (None, "") else None,
            subject=params.get("subject") or None,
            topic=str(params.get("topic") or "").strip(),
        )
        if not req.topic:
            return {"error": "Qaysi mavzu kerakligini yozing"}
        if "show_topic" in self._overrides:
            fn = self._overrides["show_topic"]
        else:
            from nexvara.knowledge.topicdoc import default_topic_path, lookup, run_topic

            def fn(task: Any) -> dict[str, Any]:
                out = None
                if self._output_dir is not None:
                    out = self._output_dir / default_topic_path(_found or lookup(req)).name
                return run_topic(task, req, out, keep_open=self._keep_open())

        title = "Mavzu: " + (_found.title if _found is not None else req.topic)
        return self._runner.start(title, fn).snapshot()

    # ----- textbook sources -----
    def _tg(self):
        if getattr(self, "_telegram", None) is None:
            from nexvara import config
            from nexvara.sources.telegram_rtm import TelegramRtm

            self._telegram = TelegramRtm(config.data_dir(), self._overrides.get("tg_factory"))
        return self._telegram

    def sources_status(self) -> dict[str, Any]:
        from nexvara import config

        root = config.textbooks_dir()
        count = {
            name: sum(1 for _ in (root / name).rglob("*.pdf")) if (root / name).is_dir() else 0
            for name in ("eduportal", "rtm")
        }
        tg = self._tg()
        status = {"configured": tg.api() is not None, "authorized": False}
        if status["configured"]:
            status = tg.status()
        return {"eduportal": count["eduportal"], "rtm": count["rtm"], "telegram": status}

    def download_eduportal(self) -> dict[str, Any]:
        from nexvara import config
        from nexvara.knowledge.service import index_library
        from nexvara.sources import eduportal

        def fn(task: Any) -> dict[str, Any]:
            with task.step("Ro‘yxatni olish (eduportal.uz)") as s:
                books = eduportal.list_textbooks()
                s.detail = f"{len(books)} ta o‘zbekcha darslik"
            with task.step("Yuklab olish") as s:

                def progress(i: int, n: int, name: str) -> None:
                    task.check_cancelled()
                    s.detail = f"{i}/{n}: {name}"

                rep = eduportal.download_all(config.textbooks_dir(), books, progress)
                s.detail = rep.summary()
            result = index_library(task)
            return {"report": [rep.summary(), result["summary"]], "failed": rep.failed}

        return self._runner.start("Rasmiy darsliklarni yuklash", fn, timeout=6 * 3600).snapshot()

    def tg_save_api(self, api_id: str, api_hash: str) -> dict[str, Any]:
        try:
            self._tg().save_api(api_id, api_hash)
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": str(e) or "API ID raqam bo‘lishi kerak"}
        return {"ok": True}

    def tg_send_code(self, phone: str) -> dict[str, Any]:
        try:
            self._tg().send_code(phone)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def tg_sign_in(self, code: str, password: str = "") -> dict[str, Any]:
        try:
            self._tg().sign_in(code, password)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def tg_download(self) -> dict[str, Any]:
        from nexvara import config
        from nexvara.knowledge.service import index_library

        tg = self._tg()

        def fn(task: Any) -> dict[str, Any]:
            with task.step("RTM kanalidan yangi darsliklar") as s:

                def progress(seen: int, name: str) -> None:
                    s.detail = f"{seen}-xabar: {name}"

                rep = tg.download(config.textbooks_dir(), progress, lambda: task.cancel_requested)
                s.detail = rep.summary()
            result = index_library(task)
            return {"report": [rep.summary(), result["summary"]], "failed": rep.failed}

        return self._runner.start("Yangi darsliklar (Telegram)", fn, timeout=6 * 3600).snapshot()

    def open_book_page(self, path: str, page: int) -> bool:
        """Open a library PDF at a page (Edge supports #page=N; otherwise the default viewer)."""
        p = Path(path)
        if not p.is_absolute() or not p.is_file() or p.suffix.lower() != ".pdf":
            return False
        if os.name == "nt":
            uri = p.resolve().as_uri() + f"#page={int(page)}"
            try:
                subprocess.Popen(["cmd", "/c", "start", "", "msedge", uri])
            except OSError:
                os.startfile(str(p))  # noqa: S606 - opening the user's own PDF
        return True

    # ----- textbook library -----
    def library_info(self) -> dict[str, Any]:
        from nexvara import config
        from nexvara.knowledge.service import open_library

        lib = open_library()
        try:
            ok = lib.books()
            other = [b for b in lib.books(status=None) if b.status != "ok"]
            return {
                "folder": str(config.textbooks_dir()),
                "books": [
                    {
                        "label": b.label(),
                        "grade": b.grade,
                        "subject": b.subject,
                        "year": b.year,
                        "pages": b.pages,
                        "file": Path(b.path).name,
                    }
                    for b in ok
                ],
                "problems": [{"file": Path(b.path).name, "note": b.note} for b in other],
                "catalog": {str(g): s for g, s in lib.grades_subjects().items()},
            }
        finally:
            lib.close()

    def open_library_folder(self) -> str:
        from nexvara import config

        folder = config.textbooks_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.Popen(["explorer", str(folder)])
        return str(folder)

    def index_library(self) -> dict[str, Any]:
        from nexvara.knowledge.service import index_library

        fn = self._overrides.get("index_library", index_library)
        return self._runner.start("Darsliklarni indekslash", fn).snapshot()

    def make_test(self, params: dict[str, Any]) -> dict[str, Any]:
        from nexvara.knowledge.service import TestRequest

        def as_int(v: Any) -> int | None:
            return int(v) if v not in (None, "") else None

        try:
            req = TestRequest(
                grade=as_int(params.get("grade")),
                subject=params.get("subject") or None,
                topic=str(params.get("topic") or "").strip(),
                count=20 if as_int(params.get("count")) is None else as_int(params.get("count")),
                variants=1
                if as_int(params.get("variants")) is None
                else as_int(params.get("variants")),
            )
            req.validate()
        except (TypeError, ValueError) as e:
            return {"error": f"Noto‘g‘ri so‘rov: {e}"}
        make = None
        if params.get("ai"):
            from nexvara.ai import features
            from nexvara.ai.router import NeedsConfirmation
            from nexvara.core.task import UserError

            if not self._ai_ready():
                return {"error": "AI ulanmagan: Sozlamalar → AI bo‘limida API kalit kiriting."}
            router = self._router()
            if not params.get("approved"):
                try:
                    router.check_budget(features.estimate_test(router, req), approved=False)
                except NeedsConfirmation as e:
                    clean = {k: v for k, v in params.items() if k != "approved"}
                    return {"confirm": self._ask("test", clean, e.estimate)}
                except (UserError, LookupError, ValueError) as e:
                    return {"error": str(e)}

            def make(r: Any):
                book, topic, quizzes, _cost = features.make_ai_quizzes(router, r, approved=True)
                return book, topic, quizzes

        if "make_test" in self._overrides:
            fn = self._overrides["make_test"]
        else:
            from nexvara.knowledge.testdoc import run_make_test

            def fn(task: Any) -> dict[str, Any]:
                out = None
                if self._output_dir is not None:
                    from nexvara.knowledge.service import default_test_path, topic_material

                    book, _pages, topic = topic_material(req)
                    out = self._output_dir / default_test_path(book, topic).name
                return run_make_test(task, req, out, keep_open=self._keep_open(), make=make)

        what = " ".join(
            x for x in (f"{req.grade}-sinf" if req.grade else "", req.subject or "") if x
        )
        title = ("AI test: " if make else "Test: ") + (what or "darslik")
        title += f" · {req.topic}" if req.topic else ""
        return self._runner.start(title, fn).snapshot()

    def run_excel_demo(self) -> dict[str, Any]:
        return self._start("excel_demo")

    def run_excel_dashboard(self) -> dict[str, Any]:
        return self._start("excel_dashboard")

    def run_word_report(self) -> dict[str, Any]:
        return self._start("word_report")

    def run_presentation(self) -> dict[str, Any]:
        return self._start("presentation")

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._runner.get(task_id)
        return task.snapshot() if task else None

    def cancel_task(self, task_id: str) -> bool:
        task = self._runner.get(task_id)
        if task is None or task.done:
            return False
        task.cancel()
        return True

    def pause_task(self, task_id: str) -> bool:
        """Stop at the next step boundary (never inside an Office call)."""
        task = self._runner.get(task_id)
        return bool(task and task.pause())

    def resume_task(self, task_id: str) -> bool:
        task = self._runner.get(task_id)
        return bool(task and task.resume())

    # ----- events for the PC window (a command from the phone shows up on the PC too) -----
    def ui_push(self, event: dict[str, Any]) -> None:
        import collections
        import threading

        if not hasattr(self, "_ui_queue"):
            self._ui_queue = collections.deque(maxlen=50)
            self._ui_lock = threading.Lock()
        with self._ui_lock:
            self._ui_queue.append(event)

    def ui_events(self) -> list[dict[str, Any]]:
        """Polled by the PC window: events since the last call (phone chat, open a dashboard)."""
        if not hasattr(self, "_ui_queue"):
            return []
        with self._ui_lock:
            out = list(self._ui_queue)
            self._ui_queue.clear()
        return out

    def list_tasks(self) -> list[dict[str, Any]]:
        live = [t.snapshot() for t in self._runner.list()]
        if self._history is None:
            return live
        ids = {t["id"] for t in live}
        older = [h for h in self._history.list() if h["id"] not in ids]
        return sorted(live + older, key=lambda t: t["created_at"], reverse=True)

    def clear_history(self) -> bool:
        if self._history is not None:
            self._history.clear()
        return True

    # ----- settings -----
    def get_settings(self) -> dict[str, Any]:
        from nexvara.appdata import Settings

        return Settings().load()

    def save_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        from nexvara.appdata import Settings

        try:
            return {"ok": True, "settings": Settings().update(changes or {})}
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": str(e)}

    def open_data_folder(self) -> str:
        from nexvara import config

        folder = config.data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.Popen(["explorer", str(folder)])
        return str(folder)

    def create_shortcut(self) -> dict[str, Any]:
        from nexvara.app.shortcut import create_desktop_shortcut

        try:
            return {"ok": True, "path": str(create_desktop_shortcut())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_url(self, url: str) -> bool:
        """Open a provider's key page in the browser (only the known https pages)."""
        import webbrowser

        from nexvara.ai.models import PROVIDERS

        if url not in {p["key_url"] for p in PROVIDERS.values()}:
            return False
        webbrowser.open(url)
        return True

    def reveal_file(self, path: str) -> bool:
        """Show a task's output file in Explorer. Only existing files are accepted."""
        p = Path(path)
        if not p.is_absolute() or not p.is_file():
            return False
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(p)])
        return True


def _clipboard(clear: bool = False) -> str:
    """Windows clipboard text (or empty it). Used only for the one-time API key paste."""
    import win32clipboard

    win32clipboard.OpenClipboard()
    try:
        if clear:
            win32clipboard.EmptyClipboard()
            return ""
        if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return ""
        return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
    finally:
        win32clipboard.CloseClipboard()
