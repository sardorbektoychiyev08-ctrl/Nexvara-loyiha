"""Bridge exposed to the web UI as `window.pywebview.api`.

Every public method must return JSON-serialisable data.
"""

from __future__ import annotations

import importlib
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from nexvara import __version__, config
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


def _wants_ai(text: str) -> bool:
    """'AI bilan test tuz', 'sun'iy intellekt yordamida' -> the user asks for the AI version."""
    import re

    from nexvara.knowledge.textnorm import fold

    return bool(re.search(r"\b(ai|sun.?iy intellekt\w*|aqlli)\b", fold(text)))


class Api:
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
        self._context_file: str | None = None  # "shu fayl": the last file worked on
        self._pending: dict[str, tuple[str, Any]] = {}  # AI requests waiting for "Ha"
        self._ai = None
        # The desktop app keeps history and settings in D:\NEXVARA; tests run without.
        self._history = None
        if persist:
            from nexvara.appdata import History

            self._history = History()
            self._runner.on_finish = lambda t: self._history.save(t.snapshot())
        if excel_demo:
            self._overrides["excel_demo"] = excel_demo
        if excel_dashboard:
            self._overrides["excel_dashboard"] = excel_dashboard

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

    def chat(self, text: str, _use_ai: bool = True) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"reply": ""}
        from nexvara.agent.parse import find_file
        from nexvara.knowledge.service import parse_test_request

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
        from nexvara.ai import features
        from nexvara.ai.router import NeedsConfirmation
        from nexvara.core.task import UserError

        router = self._router()
        try:
            intent = features.classify(router, text, approved)
            if intent.kind in ("test", "topic", "presentation", "command") and intent.command:
                out = self.chat(intent.command, _use_ai=False)
                if not out.get("unhandled"):
                    out["reply"] = f"Tushundim: «{intent.command}»\n\n" + out["reply"]
                    return out
            if intent.kind == "question":
                ans = features.answer_question(
                    router, text, approved, intent.grade, intent.subject or None
                )
            else:
                ans = features.chat_reply(router, text, approved)
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
        item = self._pending.pop(token, None)
        if item is None:
            return {"reply": "Bu so‘rov eskirgan; qaytadan yozing."}
        if not yes:
            return {"reply": "Bekor qilindi, hech narsa sarflanmadi."}
        kind, payload = item
        if kind == "chat":
            return self._chat_ai(payload, approved=True)
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

    def ai_delete_key(self, provider: str) -> dict[str, Any]:
        self._router().delete_key(provider)
        return self._router().status()

    def ai_usage(self) -> list[dict[str, Any]]:
        return self._router().ledger.recent()

    # ----- Office commands ("Hisobot.xlsx ni och, ... va saqla") -----
    def _chat_command(self, text: str) -> dict[str, Any] | None:
        from nexvara.agent import files
        from nexvara.agent.parse import parse_command

        plan = parse_command(text, self._context_file)
        if plan is None:
            return None
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
        snap = self.run_command_plan(plan, str(source))
        steps = "\n".join(f"• {d}" for d in plan.describe())
        reply = f"Fayl: {source}\nBajaraman:\n{steps}"
        if plan.unknown:
            reply += "\n\nTushunmadim (bajarilmaydi): " + "; ".join(f"«{u}»" for u in plan.unknown)
        return {"reply": reply, "task": snap, "plan": plan.describe()}

    def run_command_plan(self, plan: Any, source: str) -> dict[str, Any]:
        if "command" in self._overrides:
            fn = self._overrides["command"]
        else:
            from nexvara.agent.excel_exec import run_excel_plan
            from nexvara.agent.ppt_exec import run_ppt_plan
            from nexvara.agent.word_exec import run_word_plan

            runner = {"excel": run_excel_plan, "word": run_word_plan,
                      "powerpoint": run_ppt_plan}[plan.app]  # fmt: skip

            def fn(task: Any) -> dict[str, Any]:
                return runner(task, plan, Path(source), keep_open=self._keep_open())

        return self._runner.start(f"Buyruq: {Path(source).name}", fn).snapshot()

    def pick_file(self) -> dict[str, Any]:
        """Native "open file" dialog; the chosen file becomes "shu fayl" for commands."""
        import webview

        if not webview.windows:
            return {"path": ""}
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=(
                "Office fayllar (*.xlsx;*.xlsm;*.xls;*.csv;*.docx;*.doc;*.pptx;*.ppt)",
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
