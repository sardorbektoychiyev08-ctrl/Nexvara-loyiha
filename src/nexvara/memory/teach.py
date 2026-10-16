"""Teach NEXVARA: "Har doim Excel raqamlarini markazga joyla" becomes a rule that is added
to every later Excel command. Rules are checked when taught (the offline parser must
understand them), shown to the user, and saved only after the user's "Ha"."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from nexvara.agent.parse import Action, Plan, _classify, find_file, split_clauses
from nexvara.knowledge.textnorm import fold
from nexvara.memory.store import APP_LABELS, MemoryStore, Rule

_FACT_TRIGGER = re.compile(r"\b(eslab qol\w*|esla\w*|yodda tut\w*|unutma\w*|xotiraga yoz\w*)")
_RULE_TRIGGER = re.compile(
    r"\b(har doim|doimo|doim|hamisha|bundan buyon|bundan keyin|keyingi safar\w*|"
    r"odat qilib ol|organ\w*|o‘rgan\w*|qoida)\b"
)
_APP_WORDS = {
    "excel": r"excel\w*|eksel\w*|jadval\w*",
    "word": r"word\w*|hujjat\w*",
    "powerpoint": r"powerpoint\w*|taqdimot\w*|slayd\w*|prezentats\w*",
    "test": r"test\w*|savol\w*|variant\w*",
}
_NOISE = (
    r"\b(har doim|doimo|doim|hamisha|bundan buyon|bundan keyin|keyingi safar\w*|"
    r"odat qilib ol|organ\w*|qoida\w*|eslab qol\w*|esla\w*|yodda tut\w*|unutma\w*|"
    r"xotiraga yoz\w*|menga|iltimos|nexvara|shuni|buni|ham|da|dagi|larda|lardagi)\b"
)
_NOT_RULE_ACTIONS = {"open", "save"}
_TEMPLATE = re.compile(r"[A-Za-z]:[\\/][^\"«»\n]+?\.(?:dotx|dotm|dot|docx)\b", re.IGNORECASE)


@dataclass
class TeachRequest:
    kind: str  # fact | rule
    app: str = ""
    text: str = ""
    actions: list[str] = field(default_factory=list)  # what the rule will do, in words
    error: str = ""

    def describe(self) -> str:
        if self.kind == "fact":
            return f"Eslab qolaman: «{self.text}»"
        what = "; ".join(self.actions)
        return f"Qoida ({APP_LABELS[self.app]}): har safar «{self.text}» → {what}"


def _app_of(f: str) -> str | None:
    for app, pat in _APP_WORDS.items():
        if re.search(rf"\b({pat})", f):
            return app
    return None


def rule_actions(app: str, text: str) -> tuple[list[Action], list[str]]:
    """Actions the offline parser makes of a rule, and the parts it does not understand."""
    if app == "test":
        return [], []
    acts, unknown = [], []
    for clause in split_clauses(text):
        a = _classify(clause, app)
        if a is None or a.kind in _NOT_RULE_ACTIONS:
            unknown.append(clause)
        else:
            acts.append(a)
    return acts, unknown


def values_for_tests(text: str) -> dict:
    f = fold(text)
    out: dict = {}
    m = re.search(r"(\d{1,2})\s*(?:ta)?\s*(?:test|savol)", f)
    if m:
        out["count"] = int(m.group(1))
    m = re.search(r"(\d)\s*(?:ta)?\s*variant", f)
    if m:
        out["variants"] = int(m.group(1))
    if re.search(r"\b(ai|sun.?iy intellekt\w*)\b", f):
        out["ai"] = True
    return out


def describe_rule(app: str, text: str) -> tuple[list[str], str]:
    """(what it does, error). Errors explain what NEXVARA can learn instead."""
    from nexvara.agent.parse import DESCRIBE, _args_text

    if app == "word" and text.lower().startswith("shablon:"):
        path = text.split(":", 1)[1].strip()
        if not Path(path).is_file():
            return [], f"Shablon fayli topilmadi: {path}"
        return [f"yangi Word hujjatlar shu shablondan yaratiladi: {Path(path).name}"], ""
    if app == "test":
        vals = values_for_tests(text)
        if not vals:
            return [], "Testlar uchun savollar sonini, variantlarni yoki «AI bilan»ni yozing."
        parts = []
        if "count" in vals:
            parts.append(f"{vals['count']} ta savol")
        if "variants" in vals:
            parts.append(f"{vals['variants']} ta variant")
        if vals.get("ai"):
            parts.append("AI bilan")
        return ["testlar: " + ", ".join(parts)], ""
    acts, unknown = rule_actions(app, text)
    if not acts:
        return [], (
            "Bu qoidani tushunmadim. Masalan: «Har doim Excel jadvalini formatla va jami qo‘sh», "
            "«Word hujjatlarida doim sahifa raqamini qo‘y», «testlar doim 2 variant bo‘lsin»."
        )
    words = [DESCRIBE.get(a.kind, a.kind) + _args_text(a) for a in acts]
    if unknown:
        return words, "Tushunilmagan qism: " + "; ".join(f"«{u}»" for u in unknown)
    return words, ""


def parse_teach(text: str) -> TeachRequest | None:
    """'Eslab qol: maktabim 12-maktab' -> fact; 'Har doim Excel ... formatla' -> rule."""
    if find_file(text) and not _TEMPLATE.search(text):
        return None  # a command about a file, even if it says "doim"
    f = fold(text)
    tpl = _TEMPLATE.search(text)
    if tpl and "shablon" in f:  # "Mana shu Word shablonini ishlat: D:\...\maktab.dotx"
        body = f"shablon: {tpl.group(0)}"
        acts, err = describe_rule("word", body)
        return TeachRequest("rule", "word", body, acts, err)
    fact = _FACT_TRIGGER.search(f)
    rule = _RULE_TRIGGER.search(f)
    if not fact and not rule:
        return None
    app = _app_of(f)
    if rule and app:
        body = re.sub(_NOISE, " ", f)
        body = re.sub(rf"\b({_APP_WORDS[app]})", " ", body) if app != "test" else body
        body = re.sub(r"\s+", " ", re.sub(r"^[\s:,.-]+|[\s:,.-]+$", "", body)).strip()
        acts, err = describe_rule(app, body)
        return TeachRequest("rule", app, body, acts, err)
    if fact:
        body = re.sub(r"^[\s:,.-]+", "", _strip_trigger(text)).strip()
        if not body:
            return TeachRequest("fact", error="Nimani eslab qolishim kerakligini yozing.")
        return TeachRequest("fact", text=body)
    return None


def _strip_trigger(text: str) -> str:
    """Remove the 'eslab qol' words from the original text (keeps its spelling)."""
    pat = re.compile(
        r"\b(eslab\s+qol\w*|yodda\s+tut\w*|unutma\w*|xotiraga\s+yoz\w*|esla\w*)\b[\s:,-]*",
        re.IGNORECASE,
    )
    return pat.sub("", text, count=1)


# ---------------- applying rules ----------------


def apply_rules(plan: Plan, store: MemoryStore) -> tuple[Plan, list[Rule]]:
    """Add the user's rules for this app to the plan (before saving/exporting).
    Steps the command already has are not added twice."""
    if plan.app not in ("excel", "word", "powerpoint"):
        return plan, []
    applied: list[Rule] = []
    actions = list(plan.actions)
    have = {a.kind for a in actions}
    for rule in store.rules(plan.app, enabled_only=True):
        if rule.text.lower().startswith("shablon:"):
            continue
        new, _unknown = rule_actions(plan.app, rule.text)
        new = [a for a in new if a.kind not in have]
        if not new:
            continue
        cut = next(
            (i for i, a in enumerate(actions) if a.kind in ("save", "pdf", "csv")), len(actions)
        )
        for a in new:
            a.text = f"{a.text} (o‘rgatilgan qoida)"
        actions[cut:cut] = new
        have |= {a.kind for a in new}
        applied.append(rule)
    return Plan(plan.app, plan.file, actions, plan.unknown), applied


def defaults_for_tests(store: MemoryStore) -> dict:
    out: dict = {}
    for rule in store.rules("test", enabled_only=True):
        out.update(values_for_tests(rule.text))
    return out


def word_template(store: MemoryStore) -> str | None:
    for rule in reversed(store.rules("word", enabled_only=True)):
        if rule.text.lower().startswith("shablon:"):
            path = rule.text.split(":", 1)[1].strip()
            if Path(path).is_file():
                return path
    return None
