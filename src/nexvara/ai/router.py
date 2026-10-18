"""Model router: picks provider and tier, enforces the budget, records every call's cost.

Rules (spec: no surprise spending):
- nothing is sent unless the user turned AI on and saved a key; one key is enough;
- a call whose estimate would cross the daily or monthly budget (overall, or the
  provider's own limit) is refused; so is a single task above `task_limit_usd`;
- a call estimated above `confirm_over_usd` — and every "special" tier call — waits for "Ha";
- a busy/down/unreachable provider falls back to another connected provider at the same
  tier (`fallback`), with the same budget checks; a wrong key or missing credit never does;
- the real cost (from the provider's token counts) is written to app.db. It is an
  estimate of the bill: the provider's own billing page is the source of truth.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.ai import models
from nexvara.ai.keys import KeyStore, mask
from nexvara.ai.privacy import Guard
from nexvara.ai.providers import AiError, Provider, Reply, fetch_balance, make_provider
from nexvara.core.task import UserError

# purpose -> tier. Understanding a command is easy; daily work is balanced; analysis and
# planning of big tasks use the strong tier; "special" only when the user asks for it.
TIER_FOR = {
    "classify": "cheap", "command": "cheap", "chat": "cheap",
    "plan": "balanced", "qa": "balanced", "test": "balanced",
    "analysis": "powerful", "special": "special", "drawing": "powerful", "ocr": "balanced",
}  # fmt: skip
PURPOSE_LABELS = {
    "classify": "Buyruqni tushunish",
    "command": "Buyruqni tushunish",
    "chat": "Suhbat",
    "plan": "Rejalashtirish",
    "qa": "Savolga javob",
    "test": "AI test",
    "analysis": "Tahlil",
    "special": "Maxsus vazifa",
    "check": "Kalitni tekshirish",
    "drawing": "Chizma",
    "ocr": "Rasmdan matn",
}
WARN_AT = 0.8  # warn when 80% of a limit is spent
FREE_PROVIDER = "gemini"  # the only provider with an official free API tier
# Every answer is Uzbek in the Latin alphabet unless the user asked for another language/script.
LATIN_RULE = (
    "\n\nTIL QOIDASI: javobni faqat o‘zbek tilida, lotin alifbosida yoz (o‘, g‘, sh, ch, ’). "
    "Kirill harflarini ishlatma. Foydalanuvchi boshqa til yoki yozuvni aniq so‘ragan bo‘lsagina "
    "o‘sha tilda yoz."
)
_OTHER_SCRIPT = re.compile(
    r"\brus\w*\s+til\w*|\bruscha\b|\bkirill\w*|\bingliz\w*|\benglish\b|"
    r"на\s+русском|по-русски|русск\w*",
    re.IGNORECASE,
)
IMAGE_TOKENS = 1600  # a photo (<= 1600 px) counted for the estimate

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_usage (
    ts REAL NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    purpose TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_usage_ts ON ai_usage(ts);
"""


def _day_start(t: float | None = None) -> float:
    lt = time.localtime(t)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


def _month_start() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "app.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def record(self, provider: str, model: str, purpose: str, tin: int, tout: int, cost: float):
        with self._lock, self._db() as db:
            db.execute(
                "INSERT INTO ai_usage VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), provider, model, purpose, tin, tout, cost),
            )

    def spent_since(self, ts: float, provider: str | None = None) -> float:
        sql = "SELECT COALESCE(SUM(cost), 0) FROM ai_usage WHERE ts >= ?"
        args: tuple = (ts,)
        if provider:
            sql += " AND provider = ?"
            args += (provider,)
        with self._db() as db:
            (v,) = db.execute(sql, args).fetchone()
        return float(v)

    def count_today(self, provider: str, free_only: bool = False) -> int:
        """Requests sent today (free ones only: recorded at $0)."""
        q = "SELECT COUNT(*) FROM ai_usage WHERE ts >= ? AND provider = ?"
        if free_only:
            q += " AND cost = 0"
        with self._db() as db:
            return int(db.execute(q, (_day_start(), provider)).fetchone()[0])

    def today(self, provider: str | None = None) -> float:
        return self.spent_since(_day_start(), provider)

    def month(self, provider: str | None = None) -> float:
        return self.spent_since(_month_start(), provider)

    def daily(self, days: int = 30) -> list[dict[str, Any]]:
        """Spend per day and provider for the last `days` days (oldest first)."""
        start = _day_start(time.time() - (days - 1) * 86400)
        with self._db() as db:
            rows = db.execute("SELECT ts, provider, cost FROM ai_usage WHERE ts >= ?",
                              (start,)).fetchall()  # fmt: skip
        out = []
        for i in range(days):
            d0 = _day_start(start + i * 86400 + 3600)
            out.append({"day": dt.date.fromtimestamp(d0).isoformat(), "total": 0.0,
                        "providers": {}})  # fmt: skip
        index = {o["day"]: o for o in out}
        for ts, prov, cost in rows:
            o = index.get(dt.date.fromtimestamp(ts).isoformat())
            if o is not None:
                o["total"] += cost
                o["providers"][prov] = o["providers"].get(prov, 0.0) + cost
        return out

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT ts, provider, model, purpose, input_tokens, output_tokens, cost "
                "FROM ai_usage ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"ts": r[0], "provider": r[1], "model": r[2],
             "purpose": PURPOSE_LABELS.get(r[3], r[3]), "input_tokens": r[4],
             "output_tokens": r[5], "cost": r[6]}
            for r in rows
        ]  # fmt: skip


@dataclass
class Estimate:
    provider: str
    model: str
    tier: str
    input_tokens: int
    output_tokens: int
    cost: float
    free: bool = False  # Gemini free tier: no charge (only rate limits)

    def describe(self) -> str:
        price = "bepul (Gemini bepul darajasi)" if self.free else f"taxminan ${self.cost:.3f}"
        return (
            f"{models.PROVIDERS[self.provider]['label']} · {self.model} "
            f"({models.TIER_LABELS.get(self.tier, self.tier)}): {price} "
            f"(≈{self.input_tokens} + {self.output_tokens} token)"
        )


class NeedsConfirmation(Exception):
    def __init__(self, estimate: Estimate) -> None:
        super().__init__(estimate.describe())
        self.estimate = estimate


class BudgetExceeded(UserError):
    pass


class AiUnavailable(UserError):
    pass


class AiRouter:
    def __init__(
        self,
        settings: Any = None,
        keys: KeyStore | None = None,
        ledger: Ledger | None = None,
        factory: Callable[[str, str], Provider] | None = None,
        balance_fetch: Callable[[str, str], dict] | None = None,
    ) -> None:
        from nexvara.appdata import Settings

        self.settings = settings or Settings()
        self.keys = keys or KeyStore()
        self.ledger = ledger or Ledger()
        self.factory = factory or make_provider
        self.balance_fetch = balance_fetch or fetch_balance
        self._balances: dict[str, dict] = {}  # provider -> last real balance (memory only)
        self.last_masked = 0  # personal items hidden in the last request (count only)

    # ----- configuration -----
    def config(self) -> dict[str, Any]:
        return self.settings.load()["ai"]

    def connected(self) -> list[str]:
        return [n for n in models.PROVIDERS if self.keys.load(n)]

    def free_active(self) -> bool:
        """Free mode: every request goes to Gemini's free tier (Flash / Flash-Lite), recorded
        at $0, never to a paid provider. On only while a Gemini key is connected."""
        return bool(self.config().get("free_mode", True)) and bool(self.keys.load(FREE_PROVIDER))

    def provider_name(self) -> str | None:
        """The chosen provider if it has a key, else the first provider that has one."""
        if self.free_active():
            return FREE_PROVIDER
        chosen = self.config().get("provider") or ""
        if chosen and self.keys.load(chosen):
            return chosen
        conn = self.connected()
        return conn[0] if conn else None

    def ready(self) -> bool:
        return bool(self.config().get("enabled")) and self.provider_name() is not None

    def model_for(self, provider: str, tier: str) -> str | None:
        """The checked model for this tier; None when the account has no model for it."""
        chosen = (self.config().get("models") or {}).get(provider) or {}
        if tier in chosen:
            return chosen[tier]
        return models.PROVIDERS[provider]["tiers"][tier]

    def _limits(self, provider: str) -> tuple[float | None, float | None]:
        lim = (self.config().get("limits") or {}).get(provider) or {}  # daily/monthly/task
        d, m = lim.get("daily_usd"), lim.get("monthly_usd")
        return (float(d) if d not in (None, "") else None,
                float(m) if m not in (None, "") else None)  # fmt: skip

    # ----- spending -----
    def estimate(self, tier: str, system: str, messages: list[dict], expected_out: int,
                 provider: str | None = None) -> Estimate:  # fmt: skip
        provider = provider or self.provider_name()
        if provider is None:
            raise AiUnavailable("AI kaliti kiritilmagan (Sozlamalar → AI).")
        free = provider == FREE_PROVIDER and self.free_active() and tier != "special"
        if free and tier == "powerful":
            tier = "balanced"  # Pro has no free tier: Flash does the hard work for free
        model = self.model_for(provider, tier)
        if model is None:
            raise AiUnavailable(
                f"{models.PROVIDERS[provider]['label']} hisobida "
                f"«{models.TIER_LABELS[tier]}» darajasiga mos model topilmadi."
            )
        tin = models.estimate_tokens(system + "".join(m["content"] for m in messages))
        tin += IMAGE_TOKENS * sum(len(m.get("images") or []) for m in messages)
        c = 0.0 if free else models.cost(model, provider, tin, expected_out,
                                         self.config().get("prices"))  # fmt: skip
        return Estimate(provider, model, tier, tin, expected_out, c, free)

    def check_budget(self, est: Estimate, approved: bool) -> None:
        cfg = self.config()
        today, month = self.ledger.today(), self.ledger.month()
        label = models.PROVIDERS[est.provider]["label"]
        if today + est.cost > float(cfg["daily_budget_usd"]):
            raise BudgetExceeded(
                f"Kunlik AI limiti (${cfg['daily_budget_usd']:.2f}) tugaydi: bugun "
                f"${today:.3f} sarflangan, bu so‘rov ≈${est.cost:.3f}. Yangi pullik so‘rovlar "
                "to‘xtatildi. Limitni Sozlamalar → AI bo‘limida oshirish mumkin."
            )
        if month + est.cost > float(cfg["monthly_budget_usd"]):
            raise BudgetExceeded(
                f"Oylik AI limiti (${cfg['monthly_budget_usd']:.2f}) tugaydi: shu oy "
                f"${month:.3f} sarflangan. Yangi pullik so‘rovlar to‘xtatildi."
            )
        p_day, p_month = self._limits(est.provider)
        if p_day is not None and self.ledger.today(est.provider) + est.cost > p_day:
            raise BudgetExceeded(f"{label} uchun kunlik limit (${p_day:.2f}) tugaydi.")
        if p_month is not None and self.ledger.month(est.provider) + est.cost > p_month:
            raise BudgetExceeded(f"{label} uchun oylik limit (${p_month:.2f}) tugaydi.")
        p_task = ((cfg.get("limits") or {}).get(est.provider) or {}).get("task_usd")
        if p_task not in (None, "") and est.cost > float(p_task):
            raise BudgetExceeded(
                f"{label} uchun bitta topshiriq limiti (${float(p_task):.2f}) dan oshadi: bu "
                f"so‘rov ≈${est.cost:.3f}."
            )
        task = cfg.get("task_limit_usd")
        if task not in (None, "") and est.cost > float(task):
            raise BudgetExceeded(
                f"Bitta topshiriq limiti (${float(task):.2f}) dan oshadi: bu so‘rov "
                f"≈${est.cost:.3f}. Limitni Sozlamalar → AI bo‘limida o‘zgartirish mumkin."
            )
        if not approved and (est.cost > float(cfg["confirm_over_usd"]) or est.tier == "special"):
            raise NeedsConfirmation(est)

    def complete(
        self,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4000,
        expected_out: int | None = None,
        approved: bool = False,
        tier: str | None = None,
        effort: str = "medium",
    ) -> Reply:
        cfg = self.config()
        if not cfg.get("enabled"):
            raise AiUnavailable("AI o‘chirilgan (Sozlamalar → AI).")
        # Personal data is replaced locally before anything leaves this PC, for every
        # provider including a fallback one; unreliable detection blocks the request.
        guard = Guard()
        system = guard.mask(system)
        messages = [{**m, "content": guard.mask(m["content"])} for m in messages]
        self.last_masked = guard.count
        self.masked_total = getattr(self, "masked_total", 0) + guard.count
        tier = tier or TIER_FOR.get(purpose, "balanced")
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        latin = not _OTHER_SCRIPT.search(last_user or "")
        if latin:
            system += LATIN_RULE
        first = self.provider_name()
        if first is None:
            raise AiUnavailable("AI kaliti kiritilmagan (Sozlamalar → AI).")
        chain = [first]
        if self.free_active():
            pass  # free mode never falls back to a paid provider
        elif cfg.get("fallback", False):  # off by default: a paid fallback never starts by itself
            chain += [p for p in self.connected() if p != first]
        if any(m.get("images") for m in messages):  # only providers that can read a picture
            from nexvara.ai.providers import VISION

            vision = [p for p in chain if p in VISION]
            if not vision:
                raise AiUnavailable("Rasmni o‘qiydigan AI ulanmagan: OpenAI, Gemini yoki Claude "
                                    "kalitini kiriting (DeepSeek rasmni o‘qimaydi).")  # fmt: skip
            chain = vision
            first = chain[0]
        est = self.estimate(tier, system, messages, expected_out or max_tokens // 2, first)
        self.check_budget(est, approved)  # confirmation is asked for the main provider
        last_error: AiError | None = None
        for i, provider in enumerate(chain):
            if i:
                try:
                    est = self.estimate(tier, system, messages, expected_out or max_tokens // 2,
                                        provider)  # fmt: skip
                    # A fallback never costs more than what the user agreed to.
                    self.check_budget(est, approved=True)
                    if not approved and est.cost > float(cfg["confirm_over_usd"]):
                        continue
                except (AiUnavailable, BudgetExceeded):
                    continue
            key = self.keys.load(provider) or ""
            try:
                reply = self.factory(provider, key).complete(
                    est.model, system, messages, max_tokens, effort
                )
            except AiError as e:
                if est.free and "chegara" in str(e):
                    raise AiUnavailable(
                        "Gemini bepul limiti hozircha tugadi (daqiqalik yoki kunlik so‘rovlar "
                        "soni). Bir necha daqiqadan keyin yoki ertaga qayta urinib ko‘ring. "
                        "Pullik provayderga o‘zim o‘tmayman."
                    ) from e
                if not e.retryable:
                    raise
                last_error = e
                continue
            reply.provider = provider
            reply.text = guard.restore(reply.text)  # real values back, on this PC only
            if latin:  # a model that still slipped into Cyrillic Uzbek is corrected here
                from nexvara.knowledge.textnorm import to_latin_if_uzbek

                reply.text = to_latin_if_uzbek(reply.text)
            reply.masked = guard.count  # type: ignore[attr-defined]
            reply.cost = 0.0 if est.free else models.cost(
                reply.model or est.model, provider, reply.input_tokens, reply.output_tokens,
                cfg.get("prices"))  # fmt: skip
            self.ledger.record(provider, reply.model or est.model, purpose, reply.input_tokens,
                               reply.output_tokens, reply.cost)  # fmt: skip
            if i:
                reply.fallback_from = first  # type: ignore[attr-defined]
            return reply
        raise last_error or AiUnavailable("Hech bir AI provayderi javob bermadi.")

    # ----- keys -----
    def save_key(self, provider: str, key: str) -> dict[str, Any]:
        """Check the key with the free model list, then store it and remember which model
        ids this account really has for each tier (a missing one is not shown as working)."""
        if provider not in models.PROVIDERS:
            raise ValueError("noma’lum provayder")
        key = (key or "").strip()
        if len(key) < 10:
            raise ValueError("kalit juda qisqa — to‘liq nusxalang")
        available = self.factory(provider, key).list_models()
        tiers = {t: models.pick_tier(provider, t, available) for t in models.TIERS}
        self.keys.save(provider, key)
        cfg = self.config()
        chosen = dict(cfg.get("models") or {})
        chosen[provider] = tiers
        checked = dict(cfg.get("checked") or {})
        checked[provider] = {"at": time.time(), "models": len(available)}
        changes: dict[str, Any] = {"models": chosen, "checked": checked}
        if not cfg.get("provider") or not self.keys.load(cfg["provider"]):
            changes["provider"] = provider
        self.settings.update({"ai": changes})
        missing = [models.TIER_LABELS[t] for t, m in tiers.items() if m is None]
        shown = {t: m for t, m in tiers.items() if m}
        return {"models": shown, "available": len(available), "missing": missing}

    def delete_key(self, provider: str) -> None:
        self.keys.delete(provider)
        self._balances.pop(provider, None)

    # ----- real balance (only where the provider offers it officially) -----
    def balance(self, provider: str) -> dict[str, Any]:
        info = models.PROVIDERS[provider]
        if not info.get("balance_api"):
            return {"supported": False}
        key = self.keys.load(provider)
        if not key:
            return {"supported": True, "error": "Kalit kiritilmagan"}
        try:
            out = self.balance_fetch(provider, key)
        except AiError as e:
            return {"supported": True, "error": str(e)}
        self._balances[provider] = out
        return out

    # ----- state for the Settings page and the Home dashboard -----
    def _provider_state(self, name: str, cfg: dict[str, Any]) -> dict[str, Any]:
        info = models.PROVIDERS[name]
        key = self.keys.load(name)
        p_day, p_month = self._limits(name)
        day_lim = p_day if p_day is not None else float(cfg["daily_budget_usd"])
        month_lim = p_month if p_month is not None else float(cfg["monthly_budget_usd"])
        today, month = self.ledger.today(name), self.ledger.month(name)
        checked = (cfg.get("checked") or {}).get(name)
        return {
            "label": info["label"],
            "key_url": info["key_url"],
            "billing_url": info["billing_url"],
            "usage_url": info["usage_url"],
            "key_hint": info["key_hint"],
            "free_tier": info["free_tier"],
            "subscription_note": info["subscription_note"],
            "balance_api": bool(info.get("balance_api")),
            "balance": self._balances.get(name),
            "has_key": bool(key),
            "key_masked": mask(key),
            "checked": checked,
            "models": {t: self.model_for(name, t) for t in models.TIERS},
            "spent_today": round(today, 4),
            "spent_month": round(month, 4),
            "daily_limit": day_lim,
            "monthly_limit": month_lim,
            "own_limits": {
                "daily_usd": p_day,
                "monthly_usd": p_month,
                "task_usd": ((cfg.get("limits") or {}).get(name) or {}).get("task_usd"),
            },
            "left_today": round(max(0.0, day_lim - today), 4),
            "left_month": round(max(0.0, month_lim - month), 4),
        }

    def status(self) -> dict[str, Any]:
        cfg = self.config()
        today, month = self.ledger.today(), self.ledger.month()
        daily, monthly = float(cfg["daily_budget_usd"]), float(cfg["monthly_budget_usd"])
        warnings = []
        for label, spent, lim in (("Kunlik", today, daily), ("Oylik", month, monthly)):
            if lim > 0 and spent >= lim:
                warnings.append(f"{label} limit tugadi: yangi pullik AI so‘rovlari to‘xtatildi.")
            elif lim > 0 and spent >= lim * WARN_AT:
                warnings.append(f"{label} limitning {spent / lim:.0%} qismi sarflandi.")
        return {
            "enabled": bool(cfg.get("enabled")),
            "provider": self.provider_name() or "",
            "ready": self.ready(),
            "providers": {n: self._provider_state(n, cfg) for n in models.PROVIDERS},
            "tier_labels": models.TIER_LABELS,
            "tier_help": models.TIER_HELP,
            "spent_today": round(today, 4),
            "spent_month": round(month, 4),
            "daily_budget_usd": daily,
            "monthly_budget_usd": monthly,
            "task_limit_usd": cfg.get("task_limit_usd"),
            "confirm_over_usd": cfg["confirm_over_usd"],
            "send_textbook_text": cfg["send_textbook_text"],
            "fallback": bool(cfg.get("fallback", False)),
            "free_mode": bool(cfg.get("free_mode", True)),
            "free_active": self.free_active(),
            "free_requests_today": self.ledger.count_today(FREE_PROVIDER, free_only=True),
            "warnings": warnings,
            "blocked": today >= daily or month >= monthly,
        }

    def dashboard(self) -> dict[str, Any]:
        """Home page: cards, totals, split by provider, history and a 30-day series."""
        st = self.status()
        month_total = st["spent_month"] or 0.0
        split = [{"provider": n, "label": p["label"], "spent_month": p["spent_month"],
                  "share": (p["spent_month"] / month_total) if month_total else 0.0}
                 for n, p in st["providers"].items()]  # fmt: skip
        return {**st, "split": split, "series": self.ledger.daily(30),
                "history": self.ledger.recent(15), "estimated": True}  # fmt: skip


__all__ = [
    "AiError",
    "AiRouter",
    "AiUnavailable",
    "BudgetExceeded",
    "Estimate",
    "Ledger",
    "NeedsConfirmation",
]
