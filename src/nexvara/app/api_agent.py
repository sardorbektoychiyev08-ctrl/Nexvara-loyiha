"""Core Agent loop of the chat (mixed into app.api.Api).

    message → API-key guard → memory aliases ("hisobot papkam" → «D:\\Ish\\Hisobotlar»)
            → references ("uni" → the last result) → several tasks? → one chain task
            → tool calls (offline rules, or the AI planner) → validate → confirm risky → run

A chain runs its steps one after another in one task; each step sees the previous step's
output as "uni"/"natija", so "A.xlsx ni PDF qil, keyin uni D:\\Arxiv ga ko‘chir" works.
"""

from __future__ import annotations

import re
import threading
import uuid
from pathlib import Path
from typing import Any

from nexvara.knowledge.textnorm import fold

_KEY_LIKE = re.compile(
    r"\b(sk-[A-Za-z0-9_\-]{16,}|sk-ant-[A-Za-z0-9_\-]{10,}|AIza[0-9A-Za-z_\-]{30,}"
    r"|GOCSPX-[A-Za-z0-9_\-]{10,}|ghp_[A-Za-z0-9]{20,})"
)
_PATH_IN = re.compile(r"([A-Za-z]:[\\/][^\s«»\"“”,;]*[^\s«»\"“”,;.])")
_OFFICE_EXT = (".xlsx", ".xlsm", ".xls", ".csv", ".docx", ".doc", ".rtf", ".pptx", ".ppt")
_FAILED = ("Buni tushunmadim", "Qaysi", "Bajara olmadim", "Xato", "Bu rejimda")


_SERVICE = re.compile(
    r"^\s*(ha|yo[‘’']?q|ha, davom et|so[‘’']?rov yuborilmadi|bu ish pullik ai|tasdiq kerak|"
    r"bekor qilindi|eslab qolaman:|✨ rasm yarataman|🖼️ rasmni ai ko[‘’']?radi|"
    # provider errors: the AI must not "remember" an outage and apologise for it later
    r"[\w ()]+ xatosi \(\d+\)|[\w ()]+ serveri hozir band|internetga ulanib bo|"
    r"gemini bepul limiti|hech bir ai provayderi)",
    re.IGNORECASE,
)


def _service_line(text: str) -> bool:
    """«Ha», «Bu ish pullik AI … Davom etaymi?», «So‘rov yuborilmadi…»: NEXVARA's own prompts
    and the user's yes/no carry no meaning for the AI's memory (and once kept a privacy
    warning looping back into every request — live check 2026-10-19)."""
    return bool(_SERVICE.match(text or ""))


def looks_like_secret(text: str) -> bool:
    return bool(_KEY_LIKE.search(text or ""))


class AgentApi:
    _ctx: Any
    _pending: dict
    _runner: Any
    _local = threading.local()  # per-thread: a confirmed chain runs its risky steps

    # ----- memory aliases -----
    def _aliases(self) -> list[tuple[list[str], str]]:
        """Facts like "hisobot papkam — D:\\Ish\\Hisobotlar" -> (["hisobot", "papka"], path)."""
        from nexvara.memory.store import stem

        mem = self._mem()
        if mem is None:
            return []
        out = []
        for fact in mem.facts():
            m = _PATH_IN.search(fact["text"])
            if not m:
                continue
            phrase = fact["text"][: m.start()] + " " + fact["text"][m.end() :]
            words = [stem(w) for w in re.findall(r"\w+", fold(phrase)) if w not in (
                "bu", "manzili", "manzil", "joyi", "joylashgan", "yoli", "u", "papkasi",
                "turadi", "da", "shu", "mening", "menning")]  # fmt: skip
            if words:
                out.append((words, m.group(1)))
        return out

    def _alias_path(self, phrase: str) -> str:
        from nexvara.memory.store import stem

        want = [stem(w) for w in re.findall(r"\w+", fold(phrase))]
        for words, path in self._aliases():
            if want and all(w in want for w in words) and len(want) <= len(words) + 1:
                return path
        return ""

    def _expand_aliases(self, text: str) -> str:
        """Replace a remembered name in the message with its path (longest names first)."""
        from nexvara.memory.store import stem

        aliases = sorted(self._aliases(), key=lambda a: -len(a[0]))
        if not aliases:
            return text
        tokens = list(re.finditer(r"[\w‘’']+", text))
        stems = [stem(fold(t.group())) for t in tokens]
        for words, path in aliases:
            n = len(words)
            for i in range(len(stems) - n + 1):
                if stems[i : i + n] == words:
                    start, end = tokens[i].start(), tokens[i + n - 1].end()
                    tail = fold(tokens[i + n - 1].group())
                    case = re.search(r"(dagi|dan|da|ga|ni)$", tail)  # keep "...papkamdagi" sense
                    return text[:start] + f"«{path}»" + (case.group(1) if case else "") + text[end:]
        return text

    # ----- references -----
    def _bind_refs(self, text: str) -> str:
        """ "uni PDF qil" right after a copy -> "«D:\\Arxiv\\A.xlsx» ni PDF qil"."""
        from nexvara.agent.parse import find_file

        # A file of this conversation named without its folder: «1000006389 (2)_NEXVARA.xlsx
        # ni och» (spaces, brackets) is read as the whole name, not «(2)_NEXVARA.xlsx».
        for known in (self._ctx.result, self._ctx.file):
            if known and " " in known and known in text and f"«{known}»" not in text:
                # The AI planner wrote the full path unquoted (live 2026-10-24): «Savdo
                # jadvali 2026….xlsx» was read as just «2026….xlsx» and not found.
                return text.replace(known, f"«{known}»", 1)
            name = Path(known).name if known else ""
            # Only expand a bare file name.  The same basename may already be
            # present in a different full path (for example after copying
            # Ish\savdo.csv to Arxiv\savdo.csv); replacing that suffix corrupts
            # the explicit path and can also turn a dashboard title into a path.
            bare = re.search(rf"(?<![\w\\/]){re.escape(name)}", text) if name else None
            if bare and known not in text and f"«{name}»" not in text:
                start, end = bare.span()
                return text[:start] + f"«{known}»" + text[end:]
        res = self._ctx.result
        if not res or find_file(text) or not res.lower().endswith(_OFFICE_EXT):
            return text
        pat = r"\b(uni|natijani|natija faylni|yangi faylni)\b"
        return re.sub(pat, lambda _m: f"«{res}» ni", text, count=1, flags=re.IGNORECASE)

    def _repeat(self, text: str) -> dict[str, Any] | None:
        """ "xuddi shunday Savdo.xlsx bilan ham qil" repeats the last Office command."""
        from nexvara.agent.parse import find_file

        f = fold(text)
        if not re.search(r"\b(xuddi shunday|huddi shunday|xuddi shu|shuning ozini|shuni)\b", f):
            return None
        new = find_file(text)
        old = self._ctx.command
        if not new or not old:
            return None
        prev = find_file(old)
        cmd = old.replace(prev, new, 1) if prev else f"{new} ni och, {old}"
        out = self._chat_command(cmd)
        if out is not None:
            out["reply"] = f"Takrorlayman: «{cmd}»\n\n" + out["reply"]
        return out

    # ----- running tool calls -----
    def _approved_now(self) -> bool:
        return bool(getattr(self._local, "approved", False))

    def _run_calls(
        self, calls: list, approved: bool = False, intro: str = "", from_ai: bool = False
    ) -> dict[str, Any]:
        """Run a validated plan; only destructive/irreversible tools require explicit approval.

        Safe edits already preserve the original or create a new result, so an AI-authored plan
        should feel like a direct assistant command instead of asking «Ha» for every step.
        """
        from nexvara.agent import tools

        try:
            calls = [tools.validate(c) for c in calls]
        except tools.ToolError as e:
            return {"reply": str(e), "error": True}
        risky = [c for c in calls if tools.TOOLS[c.tool].risky]
        if risky and not (approved or self._approved_now()):
            token = uuid.uuid4().hex[:12]
            self._pending[token] = ("tools", calls)
            lines = "\n".join(f"{i}. {c.describe()}" for i, c in enumerate(calls, 1))
            warn = "Diqqat: " + "; ".join(tools.TOOLS[c.tool].title for c in risky) + ". "
            return {"reply": f"{intro}Bajaraman:\n{lines}\n\n{warn}Davom etaymi?",
                    "confirm": token}  # fmt: skip
        if len(calls) == 1:
            one = calls[0]
            args = {k: (self._ctx.result if v == "@prev" else v) for k, v in one.args.items()}
            try:
                out = tools.run(self, tools.ToolCall(one.tool, args))
            except tools.ToolError as e:
                return {"reply": str(e), "error": True}
            if intro:
                out["reply"] = intro + out["reply"]
            if from_ai:
                self._watch_result(out, one.tool)
            return out
        return self._start_chain(calls, intro=intro, approved=True)

    def _start_chain(self, steps: list, intro: str = "", approved: bool = False) -> dict[str, Any]:
        """Several steps (ToolCalls or command texts) in one background task."""
        from nexvara.agent.tools import ToolCall

        labels = [s.describe() if isinstance(s, ToolCall) else s for s in steps]
        risky = [] if approved else self._risky_steps(steps)
        if risky:
            token = uuid.uuid4().hex[:12]
            self._pending[token] = ("chain", steps)
            lines = "\n".join(f"{i}. {x}" for i, x in enumerate(labels, 1))
            return {"reply": f"{intro}Ketma-ket bajaraman:\n{lines}\n\nDiqqat: "
                    + "; ".join(risky) + ". Davom etaymi?", "confirm": token}  # fmt: skip

        def fn(task: Any) -> dict[str, Any]:
            self._local.approved = True  # the user said "Ha" to the whole list (or none is risky)
            self._local.in_chain = True  # a step is one task: it is not split again
            try:
                return self._chain_body(task, steps, labels)
            finally:
                self._local.approved = self._local.in_chain = False

        snap = self._runner.start(f"Ketma-ket: {len(steps)} ta topshiriq", fn, timeout=3 * 3600)
        lines = "\n".join(f"{i}. {x}" for i, x in enumerate(labels, 1))
        return {"reply": f"{intro}Ketma-ket bajaraman:\n{lines}\n\nJarayon o‘ng panelda.",
                "task": snap.snapshot(), "plan": labels}  # fmt: skip

    def _risky_steps(self, steps: list) -> list[str]:
        from nexvara.agent import nlu, tools
        from nexvara.agent.tools import ToolCall

        out = []
        for s in steps:
            calls = [s] if isinstance(s, ToolCall) else (nlu.parse(s) or [])
            out += [tools.TOOLS[c.tool].title for c in calls if c.tool in tools.TOOLS
                    and tools.TOOLS[c.tool].risky]  # fmt: skip
        return out

    def _chain_body(self, task: Any, steps: list, labels: list[str]) -> dict[str, Any]:
        from nexvara.agent import tools
        from nexvara.agent.tools import ToolCall
        from nexvara.core.task import UserError

        outputs: list[str] = []
        report: list[str] = []
        replies: list[str] = []  # what each step said (taught rules applied, plan ...)
        for i, (step, label) in enumerate(zip(steps, labels, strict=True), 1):
            with task.step(f"{i}. {label[:90]}") as st:
                if isinstance(step, ToolCall):
                    args = {k: (self._ctx.result if v == "@prev" else
                                [self._ctx.result if x == "@prev" else x for x in v]
                                if isinstance(v, list) else v)
                            for k, v in step.args.items()}  # fmt: skip
                    try:
                        out = tools.run(self, ToolCall(step.tool, args))
                    except tools.ToolError as e:
                        out = {"reply": str(e), "error": True}
                else:
                    out = self._chat_inner(step, _use_ai=False)
                reply = out.get("reply", "")
                replies.append(reply)
                st.detail = reply[:200]
                if out.get("confirm"):
                    raise UserError(f"{i}-qadam tasdiq so‘radi: {reply[:200]}")
                if out.get("error") or out.get("unhandled") or reply.startswith(_FAILED):
                    raise UserError(f"{i}-qadam bajarilmadi: {reply[:300] or label}")
                sub = out.get("task")
                if sub:
                    sub_task = self._runner.get(sub["id"])
                    while not sub_task.wait(0.5):
                        task.check_cancelled()
                    snap = sub_task.snapshot()
                    if snap["status"] != "succeeded":
                        raise UserError(f"{i}-qadam: {snap.get('error') or snap['status']}")
                    self._ctx.task_done(snap)
                    res = snap.get("result") or {}
                    outs = [
                        res[k]
                        for k in ("pdf", "path")
                        if isinstance(res.get(k), str) and res.get(k)
                    ]
                    outputs += outs
                    st.detail = ", ".join(Path(o).name for o in outs) or "bajarildi"
                for p in out.get("files") or []:
                    outputs.append(p)
                report.append(f"{i}. {label}: {st.detail}")
        last = next((o for o in reversed(outputs) if Path(o).exists()), "")
        return {"report": report, "path": last, "replies": replies}

    # ----- the agent's entry -----
    def _chat_agent(self, text: str, use_ai: bool) -> dict[str, Any] | None:
        from nexvara.agent import nlu

        rep = self._repeat(text)
        if rep is not None:
            return rep
        steps = nlu.split_chain(text)
        if len(steps) > 1 and not getattr(self._local, "in_chain", False):
            return self._start_chain(steps)
        calls = nlu.parse(text)
        if calls:
            return self._run_calls(calls)
        return None

    # ----- a month of conversation for the AI (recent turns + matching older ones) -----
    def _recall(self, text: str):
        from nexvara.ai.features import Recall

        mem = self._mem()
        if mem is None:
            return Recall(list(self._ctx.turns)[:-1])
        try:
            st = self.get_settings().get("memory") or {}
        except Exception:
            st = {}
        days, n = int(st.get("chat_days", 30)), int(st.get("recent_turns", 15))
        turns = mem.recent_turns(n + 1, days) if n else []
        if turns and turns[-1]["role"] == "user" and turns[-1]["text"].strip() == text.strip():
            turns = turns[:-1]  # chat() logged the current message already
        turns = [t for t in turns if not _service_line(t["text"])]
        turns = turns[-n:] if n else []
        older = [x for x in mem.recall(text, days, skip_last=n + 1)
                 if not _service_line(x["user"]) and not _service_line(x["nexvara"])]  # fmt: skip
        return Recall(turns, older, mem.day_summaries(min(days, 7)))

    def _chat_forget(self, text: str) -> dict[str, Any] | None:
        """«buni unut» (the last exchange), «Savdo hisoboti haqidagi gaplarni unut»."""
        f = fold(text).strip(" .!")
        if not re.search(r"\bunut(ib yubor|gin|ing)?$", f) or re.search(r"\bunutma", f):
            return None
        mem = self._mem()
        if mem is None:
            return {"reply": "Suhbat xotirasi bu rejimda yo‘q."}
        if re.fullmatch(r"(buni|shuni|oxirgisini|oxirgi gapni|bu gapni) unut\w*", f):
            n = mem.forget_last(3)  # the earlier question, its answer and this message
            self._ctx.turns.clear()
            return {"reply": f"Unutdim: oxirgi suhbatdan {n} ta xabar o‘chirildi."}
        if re.search(r"\b(hamma|barcha|butun)\w* (suhbat|gap|xabar)", f):
            return {"reply": "Butun suhbatni o‘chirish uchun «Xotira» bo‘limida «Suhbatni "
                    "tozalash» tugmasini bosing (qaytarib bo‘lmaydi)."}  # fmt: skip
        m = re.fullmatch(
            r"(.+?)\s+(haqidagi|haqida|to.?g.?risidagi|bilan bog.?liq)?\s*"
            r"(gaplarni|gapni|suhbatni|xabarlarni|narsalarni)?\s*(ni )?unut\w*",
            f,
        )
        what = (m.group(1) if m else "").strip()
        what = re.sub(r"\b(ni|ga|haqida)$", "", what).strip()
        if len(what) < 3:
            return None
        n = mem.forget_chat(what)
        self._ctx.turns.clear()
        if not n:
            return {"reply": "Bu mavzuda suhbatda hech narsa topilmadi."}
        # The phrase itself is not repeated: the reply is logged and would be found again.
        return {"reply": f"Unutdim: shu mavzudagi {n} ta xabar suhbat xotirasidan o‘chirildi. "
                "Eslab qolingan faktlar va qoidalar o‘zgarmadi («Xotira» bo‘limida)."}  # fmt: skip

    # ----- self-repair: the AI reads the error of a failed command and tries again -----
    def _self_repair_on(self) -> bool:
        if not self._ai_ready():
            return False
        try:
            return bool(self._router().config().get("self_repair", True))
        except Exception:
            return True

    def _repair(self, text: str, error: str, tries: int = 2) -> dict[str, Any] | None:
        """Re-plan with the error message (max `tries`). Only risky corrected steps wait for
        «Ha»; safe edits preserve the original and run directly. None means AI could not help."""
        from nexvara.agent import tools as agent_tools
        from nexvara.ai import features
        from nexvara.ai.router import NeedsConfirmation
        from nexvara.core.task import UserError

        router = self._router()
        mem = self._mem()
        recall = self._recall(text)
        facts = mem.relevant_facts(text) if mem is not None else []
        for attempt in range(1, tries + 1):
            try:
                p = features.plan(router, text, agent_tools.catalog(), self._ctx.snapshot(),
                                  recall.turns, facts, (), False, recall.older,
                                  error=error)  # fmt: skip
            except NeedsConfirmation:
                return None  # a repair never spends above the "ask first" limit on its own
            except UserError:
                return None
            if p.kind != "tools" or not p.calls:
                return None
            calls = [agent_tools.ToolCall(str(c["tool"]), dict(c.get("args") or {}))
                     for c in p.calls]  # fmt: skip
            intro = (f"🔧 Birinchi urinish bajarilmadi: {error[:300]}\n"
                     f"AI xatoni o‘qib, tuzatilgan rejani tuzdi ({attempt}-urinish)"
                     + (f": {p.say}" if p.say else "") + "\n\n")  # fmt: skip
            out = self._run_calls(calls, intro=intro, from_ai=True)
            if not out.get("error"):
                out["repaired"] = attempt
                return out
            error = out.get("reply", "") or error
        return {"reply": f"AI {tries} marta tuzatib ko‘rdi, bo‘lmadi. Oxirgi xato: {error[:400]}"
                "\n\nBuyruqni boshqacharoq yozib ko‘ring.", "error": True}  # fmt: skip

    def _repair_task(self, snap: dict[str, Any]) -> None:
        """An Office task started from chat failed: try a corrected plan in the background
        and show the result in the chat."""
        if snap.get("status") != "failed" or snap.get("id") != getattr(self, "_chat_task", ""):
            return
        self._chat_task = ""
        origin = getattr(self, "_repair_origin", None) or [self._ctx.command, 0]
        if not origin[0] or origin[1] >= 2 or not self._self_repair_on():
            return
        origin[1] += 1  # the user's own message is repaired at most twice in all
        self._repair_origin = origin
        error = str(snap.get("error") or "xato")

        def work() -> None:
            try:
                out = self._repair(origin[0], error, tries=1)
            except Exception:
                out = None
            if out is not None:
                self.ui_push({"kind": "nexvara_reply", "reply": out})

        threading.Thread(target=work, daemon=True).start()

    # ----- «bajar → tekshir → tuzat»: the AI reads what was made and fixes what is wrong -----
    def _watch_result(self, out: dict[str, Any], tool: str) -> None:
        """Remember a task an AI plan started, so its file is checked when it is done."""
        from nexvara.agent import tools

        task = out.get("task") or {}
        if tool not in tools.VERIFIED or not task.get("id"):
            return
        origin = getattr(self, "_repair_origin", None) or [self._ctx.command, 0]
        if not origin[0]:
            return
        if not hasattr(self, "_verify_jobs"):
            self._verify_jobs: dict[str, tuple[str, int]] = {}
        self._verify_jobs[task["id"]] = (origin[0], int(getattr(self._local, "verify_round", 0)))

    def _verify_task(self, snap: dict[str, Any]) -> None:
        job = getattr(self, "_verify_jobs", {}).pop(snap.get("id"), None)
        if job is None or snap.get("status") != "succeeded" or not self._self_repair_on():
            return
        text, round_no = job

        def work() -> None:
            from nexvara.ai import verify

            try:
                files = verify.outputs(snap.get("result") or {})
                res = verify.check(self._router(), text, files) if files else None
            except Exception:  # noqa: BLE001 - a check never breaks the finished work
                res = None
            if res is None:
                return
            name = Path(files[0]).name
            if res["ok"]:
                self._say_later({"reply": f"✔ Tekshirdim: «{name}» so‘rovingizga mos."})
                return
            found = "\n".join(f"• {p}" for p in res["problems"]) or "• so‘rovga to‘liq mos emas"
            head = f"🔎 «{name}» ni tekshirdim, kamchilik topildi:\n{found}"
            if round_no >= 1 or not res["fixed_request"]:
                self._say_later({"reply": head + "\n\nQolganini ko‘rib chiqing yoki nimani "
                                 "o‘zgartirishni yozing."})  # fmt: skip
                return
            self._local.verify_round = round_no + 1
            try:
                fixed = self._repair(text, "Natija tekshirildi, kamchiliklar: "
                                     + "; ".join(res["problems"]) + ". Ko‘rsatma: "
                                     + res["fixed_request"], tries=1)  # fmt: skip
            except Exception:  # noqa: BLE001
                fixed = None
            finally:
                self._local.verify_round = 0
            if fixed is None or fixed.get("error"):
                self._say_later({"reply": head + "\n\nO‘zim tuzata olmadim — nimani o‘zgartirish "
                                 "kerakligini yozing."})  # fmt: skip
                return
            fixed["reply"] = (
                head
                + "\n\nTuzatyapman (yangi fayl, eskisi o‘zgarmaydi):\n"
                + (fixed.get("reply") or "")
            )
            self._say_later(fixed)

        threading.Thread(target=work, name="verify", daemon=True).start()

    def _say_later(self, out: dict[str, Any]) -> None:
        """A reply that comes after the chat answer: the PC window, the chat log, the phone."""
        self.ui_push({"kind": "nexvara_reply", "reply": out})
        mem = self._mem()
        if mem is not None:
            mem.log_chat("nexvara", out.get("reply", ""))
        self._ctx.add_turn("nexvara", out.get("reply", ""))

    def _ai_has_key(self) -> bool:
        if self._history is None and "ai_router" not in self._overrides:
            return False
        try:
            return self._router().provider_name() is not None
        except Exception:
            return False
