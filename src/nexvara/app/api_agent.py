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
        """`from_ai`: the plan came from the AI planner. Then anything that changes data or
        settings is shown first and runs only after "Ha" (read-only lookups run at once)."""
        from nexvara.agent import tools

        try:
            calls = [tools.validate(c) for c in calls]
        except tools.ToolError as e:
            return {"reply": str(e), "error": True}
        risky = [c for c in calls if tools.TOOLS[c.tool].risky]
        changes = [c for c in calls if c.tool not in tools.READ_ONLY]
        if (risky or (from_ai and changes)) and not (approved or self._approved_now()):
            token = uuid.uuid4().hex[:12]
            self._pending[token] = ("tools", calls)
            lines = "\n".join(f"{i}. {c.describe()}" for i, c in enumerate(calls, 1))
            if risky:
                warn = "Diqqat: " + "; ".join(tools.TOOLS[c.tool].title for c in risky) + ". "
            else:
                warn = "AI shunday tushundi — to‘g‘rimi? "
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

    def _ai_has_key(self) -> bool:
        if self._history is None and "ai_router" not in self._overrides:
            return False
        try:
            return self._router().provider_name() is not None
        except Exception:
            return False
