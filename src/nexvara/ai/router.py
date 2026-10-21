"""Model router: picks provider and tier, enforces the budget, records every call's cost.

Rules (spec: no surprise spending):
- nothing is sent unless the user turned AI on and saved a key; one key is enough;
- a call whose estimate would cross the daily or monthly budget (overall, or the
  provider's own limit) is refused; so is a single task above `task_limit_usd`;
- a call estimated above `confirm_over_usd` — and every "special" tier call — waits for "Ha";
- AUTO tries the provider chosen in Settings first, the other connected ones after it;
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
from nexvara.ai import capabilities as caps
from nexvara.ai import catalog as model_catalog
from nexvara.ai import models
from nexvara.ai.keys import KeyStore, mask
from nexvara.ai.privacy import Guard
from nexvara.ai.providers import AiError, Provider, Reply, fetch_balance, make_provider
from nexvara.core.task import UserError

# purpose -> tier. Understanding a command is easy; daily work is balanced; analysis and
# planning of big tasks use the strong tier; "special" only when the user asks for it.
TIER_FOR = {
    "classify": "cheap", "command": "cheap", "chat": "balanced",
    "plan": "balanced", "qa": "balanced", "test": "balanced",
    "analysis": "powerful", "special": "special", "drawing": "powerful", "ocr": "balanced",
    "translate": "balanced",
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
    "translate": "Tarjima / qayta yozish",
    "vision": "Rasmni tahlil qilish",
    "image": "Rasm yaratish",
    "image_edit": "Rasmni tahrirlash",
    "stt": "Ovoz → matn",
    "tts": "Matn → ovoz",
}
_TIER_UP = {"cheap": "balanced", "balanced": "powerful"}
WARN_AT = 0.8  # warn when 80% of a limit is spent
FREE_PROVIDER = "gemini"  # the only provider with an official free API tier
# Every answer is Uzbek in the Latin alphabet unless the user asked for another language/script.
LATIN_RULE = (
    "\n\nTIL QOIDASI: javobni faqat o‘zbek tilida, lotin alifbosida yoz (o‘, g‘, sh, ch, ’). "
    "Kirill harflarini ishlatma. Foydalanuvchi boshqa til yoki yozuvni aniq so‘ragan bo‘lsagina "
    "o‘sha tilda yoz. Foydalanuvchiga hurmat bilan «siz» deb murojaat qil («sen» emas)."
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
        what = models.TIER_LABELS.get(self.tier) or caps.CAP_LABELS.get(self.tier, self.tier)
        size = (f" (≈{self.input_tokens} + {self.output_tokens} token)"
                if self.tier in models.TIER_LABELS else "")  # fmt: skip
        return f"{models.PROVIDERS[self.provider]['label']} · {self.model} ({what}): {price}{size}"


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
        media_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        from nexvara.appdata import Settings

        self.settings = settings or Settings()
        self.keys = keys or KeyStore()
        self.ledger = ledger or Ledger()
        self.factory = factory or make_provider
        self.balance_fetch = balance_fetch or fetch_balance
        if media_factory is None:
            from nexvara.ai.media import media_client as media_factory
        self.media_factory = media_factory
        self._balances: dict[str, dict] = {}  # provider -> last real balance (memory only)
        self.last_masked = 0  # personal items hidden in the last request (count only)
        self._catalog_lock = threading.Lock()
        self._auto_catalog = factory is None
        self._catalog_started = False
        self._last_call = threading.local()

    # ----- configuration -----
    def config(self) -> dict[str, Any]:
        return self.settings.load()["ai"]

    def connected(self) -> list[str]:
        return [n for n in models.PROVIDERS if self.keys.load(n)]

    def free_active(self) -> bool:
        """Free mode: every request goes to Gemini's free tier (Flash / Flash-Lite), recorded
        at $0, never to a paid provider. On only while a Gemini key is connected."""
        cfg = self.config()
        return (bool(cfg.get("free_mode", True)) and bool(cfg.get("free_tier_confirmed"))
                and bool(self.keys.load(FREE_PROVIDER)))  # fmt: skip

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
                 provider: str | None = None, model: str | None = None) -> Estimate:  # fmt: skip
        """`model`: a model the user picked by hand (MANUAL) — used as is, never swapped."""
        provider = provider or self.provider_name()
        if provider is None:
            raise AiUnavailable("AI kaliti kiritilmagan (Sozlamalar → AI).")
        model = model or self.model_for(provider, tier)
        if model is None:
            raise AiUnavailable(
                f"{models.PROVIDERS[provider]['label']} hisobida "
                f"«{models.TIER_LABELS[tier]}» darajasiga mos model topilmadi."
            )
        free = (
            provider == FREE_PROVIDER
            and self.free_active()
            and tier != "special"
            and model in self._free_text_models()
        )
        tin = models.estimate_tokens(system + "".join(m["content"] for m in messages))
        tin += IMAGE_TOKENS * sum(len(m.get("images") or []) for m in messages)
        # Gemini counts 32 tokens per second of audio; 16 kHz 16-bit WAV is 32 000 bytes a second
        tin += sum(len(m["audio"]["data"]) * 3 // 4 // 1000 for m in messages if m.get("audio"))
        try:
            c = 0.0 if free else models.cost(model, provider, tin, expected_out,
                                             self.config().get("prices"))  # fmt: skip
        except ValueError as e:
            raise AiUnavailable(str(e) + ". Narx tekshirilmaguncha so‘rov yuborilmaydi.") from e
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
        if approved or est.free and est.tier != "special":
            return
        if est.tier == "special" or est.cost > float(cfg.get("confirm_over_usd") or 0):
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
        accept: Callable[[str], bool] | None = None,
        capability: str | None = None,
        provider_override: str | None = None,
    ) -> Reply:
        """`accept`: a check of the answer (e.g. "is it valid JSON"). In AUTO a failed check
        retries once on the next stronger tier, inside the same budget rules."""
        reply = self._complete(purpose, system, messages, max_tokens=max_tokens,
                               expected_out=expected_out, approved=approved, tier=tier,
                               effort=effort, capability=capability,
                               provider_override=provider_override)  # fmt: skip
        tier = tier or TIER_FOR.get(purpose, "balanced")
        if accept is None or accept(reply.text) or self.manual("text") or tier not in _TIER_UP:
            return reply
        next_tier = _TIER_UP[tier]
        cap = capability or ("vision" if any(m.get("images") for m in messages) else "text")
        try:
            next_choice = self.text_candidates(
                next_tier, system, messages, expected_out or max_tokens // 2, cap, provider_override
            )[0]
        except AiUnavailable:
            return reply
        first_cost = (getattr(self._last_call, "value", None) or {}).get("estimated_cost", 0)
        if next_choice.cost > first_cost and not next_choice.free:
            return reply  # a stronger paid retry exceeds the approved first estimate
        try:
            better = self._complete(purpose, system, messages, max_tokens=max_tokens,
                                    expected_out=expected_out, approved=approved,
                                    tier=next_tier, effort=effort,
                                    capability=capability,
                                    provider_override=provider_override)  # fmt: skip
        except (NeedsConfirmation, BudgetExceeded, AiUnavailable, AiError):
            return reply  # the stronger model is not allowed now: keep the first answer
        better.escalated_from = reply.model  # type: ignore[attr-defined]
        return better if accept(better.text) else reply

    def _complete(
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
        capability: str | None = None,
        provider_override: str | None = None,
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
        # Speech is written down in the language it was spoken (uz/ru/en), never translated.
        latin = not _OTHER_SCRIPT.search(last_user or "") and not any(
            m.get("audio") for m in messages
        )
        if latin:
            system += LATIN_RULE
        has_audio = any(m.get("audio") for m in messages)
        has_images = any(m.get("images") for m in messages)
        cap = capability or ("vision" if has_images else "text")
        pinned = self.manual(cap) if not provider_override else None
        if pinned and has_images and not caps.supports(pinned["provider"], "vision"):
            raise AiUnavailable("Qo‘lda tanlangan model rasmni o‘qiy olmaydi.")
        choices = self.text_candidates(tier, system, messages,
                                       expected_out or max_tokens // 2, cap,
                                       provider_override)  # fmt: skip
        if has_audio:
            choices = [e for e in choices if e.provider == FREE_PROVIDER]
            if not choices:
                raise AiUnavailable("Ovozni tinglaydigan Gemini modeli topilmadi.")
        first = choices[0].provider
        self.check_budget(choices[0], approved)
        last_error: AiError | None = None
        for i, est in enumerate(choices):
            provider = est.provider
            if i and (pinned or provider_override):
                break  # MANUAL never swaps models
            if i:
                if not cfg.get("fallback"):
                    break
                try:
                    self.check_budget(est, approved=True)
                except (AiUnavailable, BudgetExceeded):
                    continue
                # A retry cannot silently start a paid call or exceed the amount
                # already approved for the first candidate.
                if not approved and not est.free:
                    continue
                if approved and est.cost > choices[0].cost:
                    raise NeedsConfirmation(est)
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
            if purpose in ("chat", "qa", "vision", "analysis", "special"):
                # The chat shows plain text: «**qalin**» markdown would appear as stars.
                reply.text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2),
                                    reply.text)  # fmt: skip
            reply.masked = guard.count  # type: ignore[attr-defined]
            try:
                reply.cost = 0.0 if est.free else models.cost(
                    reply.model or est.model, provider, reply.input_tokens, reply.output_tokens,
                    cfg.get("prices"))  # fmt: skip
            except ValueError:
                # A provider may report a different alias. Use the approved model's
                # reviewed rate and retain the reported ID for the activity log.
                reply.cost = models.cost(est.model, provider, reply.input_tokens,
                                         reply.output_tokens, cfg.get("prices"))  # fmt: skip
            self.ledger.record(provider, reply.model or est.model, purpose, reply.input_tokens,
                               reply.output_tokens, reply.cost)  # fmt: skip
            self._last_call.value = {
                "provider": provider,
                "model": reply.model or est.model,
                "mode": "MANUAL" if pinned else "AUTO",
                "free": est.free,
                "estimated_cost": est.cost,
                "cost": reply.cost,
                "cost_kind": "token estimate",
            }
            if i:
                reply.fallback_from = first  # type: ignore[attr-defined]
            return reply
        raise last_error or AiUnavailable("Hech bir AI provayderi javob bermadi.")

    # ----- directions: AUTO / MANUAL per capability -----
    def _free_text_models(self) -> set[str]:
        tiers = (self.config().get("models") or {}).get(FREE_PROVIDER) or {}
        return {m for t, m in tiers.items() if m and t in ("cheap", "balanced")} | {
            models.PROVIDERS[FREE_PROVIDER]["tiers"][t] for t in ("cheap", "balanced")
        }

    def cap_settings(self) -> dict[str, dict[str, str]]:
        saved = self.config().get("capabilities") or {}
        out = caps.default_settings()
        for c in caps.CAPABILITIES:
            if isinstance(saved.get(c), dict):
                out[c].update({k: str(v) for k, v in saved[c].items()
                               if k in ("mode", "provider", "model")})  # fmt: skip
        return out

    def manual(self, cap: str) -> dict[str, str] | None:
        s = self.cap_settings()[cap]
        if s["mode"] == "manual" and s["provider"] and s["model"]:
            return s
        return None

    def _store_catalog(self, provider: str, raw: list[str | dict[str, Any]]) -> dict:
        rows = model_catalog.normalize(provider, raw)
        if not rows:
            raise AiUnavailable("Model ro‘yxati bo‘sh: oldingi katalog saqlandi.")
        cfg = self.config()
        states = dict(cfg.get("catalog_state") or {})
        old = states.get(provider) or {}
        changes = model_catalog.changed(old, rows)
        states[provider] = {
            "checked_at": time.time(),
            "source": model_catalog.PROVIDERS_API[provider],
            "price_source": models.PRICE_SOURCES[provider],
            "prices_checked_on": models.PRICES_CHECKED_ON,
            "models": rows,
            **changes,
            "error": "",
        }
        ids = [r["id"] for r in rows if r["lifecycle"] == "active"]
        tiers = {t: models.pick_tier(provider, t, ids) for t in models.TIERS}
        selected = dict(cfg.get("models") or {})
        selected[provider] = tiers
        checked = dict(cfg.get("checked") or {})
        checked[provider] = {"at": states[provider]["checked_at"], "models": len(ids)}
        catalog = dict(cfg.get("catalog") or {})
        catalog[provider] = model_catalog.by_direction(rows)
        self.settings.update(
            {
                "ai": {
                    "catalog_state": states,
                    "models": selected,
                    "checked": checked,
                    "catalog": catalog,
                }
            }
        )
        return {
            "models": {t: m for t, m in tiers.items() if m},
            "available": len(ids),
            "missing": [models.TIER_LABELS[t] for t, m in tiers.items() if m is None],
            "changes": changes,
        }

    def refresh_catalog(self, force: bool = False) -> dict[str, Any]:
        """Read only Models APIs. On failure keep the previous verified account list."""
        result: dict[str, Any] = {}
        with self._catalog_lock:
            for provider in self.connected():
                state = (self.config().get("catalog_state") or {}).get(provider) or {}
                if not force and not model_catalog.stale(state):
                    result[provider] = {"ok": True, "cached": True}
                    continue
                try:
                    client = self.factory(provider, self.keys.load(provider) or "")
                    details = getattr(client, "list_model_details", None)
                    raw = details() if callable(details) else client.list_models()
                    result[provider] = {"ok": True, **self._store_catalog(provider, raw)}
                except (AiError, AiUnavailable, OSError, ValueError) as e:
                    states = dict(self.config().get("catalog_state") or {})
                    states[provider] = {**state, "error": str(e), "last_attempt": time.time()}
                    self.settings.update({"ai": {"catalog_state": states}})
                    result[provider] = {"ok": False, "error": str(e), "cached": bool(state)}
        return result

    def _ensure_catalog_refresh(self) -> None:
        if not self._auto_catalog or self._catalog_started:
            return
        self._catalog_started = True

        def work() -> None:
            while True:
                try:
                    self.refresh_catalog()
                except Exception:  # noqa: BLE001 - cache remains available offline
                    pass
                time.sleep(3600)

        threading.Thread(target=work, name="nexvara-model-catalog", daemon=True).start()

    def catalog_status(self) -> dict[str, Any]:
        self._ensure_catalog_refresh()
        states = self.config().get("catalog_state") or {}
        return {
            p: {k: v for k, v in (states.get(p) or {}).items() if k != "models"}
            | {
                "stale": model_catalog.stale(states.get(p) or {}),
                "count": len((states.get(p) or {}).get("models") or []),
            }
            for p in models.PROVIDERS
        }

    def catalog(self, provider: str) -> dict[str, list[str]]:
        """Models of this account per direction (from the last key check)."""
        saved = ((self.config().get("catalog") or {}).get(provider)) or {}
        out: dict[str, list[str]] = {}
        configured = (self.config().get("models") or {}).get(provider, {})
        text = saved["text"] if "text" in saved else [m for m in configured.values() if m]
        out["text"] = sorted(
            set(text if "text" in saved else (text or models.PROVIDERS[provider]["tiers"].values()))
        )
        out["vision"] = (
            saved.get("vision")
            if "vision" in saved
            else [m for m in out["text"] if "vision" in model_catalog.directions(provider, m)]
        )
        for c in ("image", "stt", "tts", "web"):
            out[c] = (
                saved.get(c)
                if saved.get(c) is not None
                else [r["model"] for r in caps.models_for(provider, c)]
            )
        out["realtime"] = ["stt+tts"] if out["stt"] and out["tts"] else []
        return out

    def text_candidates(
        self,
        tier: str,
        system: str,
        messages: list[dict],
        expected_out: int,
        cap: str = "text",
        provider_override: str | None = None,
    ) -> list[Estimate]:
        """Compare the account's reviewed models across all connected providers."""
        pinned = self.manual(cap) if not provider_override else None
        if pinned:
            p, model = pinned["provider"], pinned["model"]
            if not self.keys.load(p):
                raise AiUnavailable("Qo‘lda tanlangan AI kaliti kiritilmagan.")
            if model not in self.catalog(p)[cap]:
                raise AiUnavailable(f"Qo‘lda tanlangan «{model}» katalogda mavjud emas.")
            return [self.estimate(tier, system, messages, expected_out, p, model)]
        target = model_catalog.QUALITY[tier]
        candidates: list[tuple[int, Estimate]] = []
        for p in self.connected():
            if provider_override and p != provider_override:
                continue
            if self.free_active() and tier != "special" and p != FREE_PROVIDER:
                continue
            for model in self.catalog(p)[cap]:
                level = model_catalog.tier_of(p, model)
                if level is None:
                    continue
                quality = model_catalog.QUALITY[level]
                # A verified free Flash can attempt a strong task; output validation
                # may then request a stronger paid model with a fresh approval.
                free_trial = (
                    self.free_active()
                    and p == FREE_PROVIDER
                    and tier == "powerful"
                    and quality == target - 1
                )
                if quality < target and not free_trial:
                    continue
                if tier != "special" and level == "special":
                    continue
                if (
                    self.free_active()
                    and tier != "special"
                    and model not in self._free_text_models()
                ):
                    continue
                try:
                    est = self.estimate(tier, system, messages, expected_out, p, model)
                except AiUnavailable:
                    continue  # unknown price: not an AUTO candidate
                candidates.append((model_catalog.QUALITY[level], est))
        if not candidates:
            raise AiUnavailable(
                "Vazifaga mos, narxi tekshirilgan AI model topilmadi. "
                "Katalogni yangilang yoki qo‘lda model tanlang."
            )
        # The provider the owner chose in Settings goes first; the others are the fallback.
        chosen = self.config().get("provider") or ""
        candidates.sort(key=lambda x: (not x[1].free, x[1].provider != chosen, x[1].cost,
                                       -x[0], x[1].model))  # fmt: skip
        return [est for _, est in candidates]

    def set_capability(self, cap: str, mode: str, provider: str = "", model: str = "") -> dict:
        if cap not in caps.CAPABILITIES:
            raise ValueError("noma’lum yo‘nalish")
        if mode not in ("auto", "manual"):
            raise ValueError("rejim: auto yoki manual")
        if mode == "manual":
            if provider not in models.PROVIDERS:
                raise ValueError("provayderni tanlang")
            if not caps.supports(provider, cap):
                label = models.PROVIDERS[provider]["label"]
                raise ValueError(f"{label} da «{caps.CAP_LABELS[cap]}» imkoniyati yo‘q")
            if cap == "realtime":
                if not self.catalog(provider)["realtime"]:
                    raise ValueError("Bu hisobda jonli suhbat uchun STT va TTS topilmadi")
                model = "stt+tts"
            elif model not in self.catalog(provider)[cap]:
                label = models.PROVIDERS[provider]["label"]
                raise ValueError(f"«{model}» bu yo‘nalish uchun {label} hisobida topilmadi")
        else:
            provider, model = "", ""
        cur = self.cap_settings()
        cur[cap] = {"mode": mode, "provider": provider, "model": model}
        self.settings.update({"ai": {"capabilities": cur}})
        return cur[cap]

    def candidates(self, cap: str, provider_override: str | None = None) -> list[tuple[str, dict]]:
        """(provider, model row) to try for a media direction, best first. MANUAL: exactly the
        chosen one. AUTO: connected providers, free ones first, then the cheapest."""
        if cap == "realtime":
            realtime_pinned = self.manual("realtime")
            providers = (
                [provider_override]
                if provider_override
                else [realtime_pinned["provider"]]
                if realtime_pinned
                else self.connected()
            )
            out = []
            for p in providers:
                if not p or not self.keys.load(p):
                    continue
                try:
                    ears = self.candidates("stt", p)[0][1]
                    voice = self.candidates("tts", p)[0][1]
                except AiUnavailable:
                    continue
                out.append(
                    (
                        p,
                        {
                            "model": "stt+tts",
                            "price": (ears["price"] or 0) + (voice["price"] or 0),
                            "free": ears.get("free") and voice.get("free"),
                        },
                    )
                )
            out.sort(key=lambda x: (not x[1]["free"], x[1]["price"]))
            if not out:
                raise AiUnavailable("Jonli suhbat uchun mos STT va TTS modellari topilmadi.")
            return out
        pinned = self.manual(cap) if not provider_override else None
        if pinned is not None:
            p = pinned["provider"]
            row = caps.find(p, cap, pinned["model"])
            if row is None:
                what = caps.CAP_LABELS[cap].lower()
                raise AiUnavailable(f"Qo‘lda tanlangan «{pinned['model']}» {what} uchun "
                                    "ishlamaydi. 🧠 menyusida boshqasini tanlang yoki AUTO ni "
                                    "yoqing.")  # fmt: skip
            if not self.keys.load(p):
                raise AiUnavailable(f"Qo‘lda tanlangan {models.PROVIDERS[p]['label']} kaliti "
                                    "kiritilmagan (Sozlamalar → AI).")  # fmt: skip
            if row["model"] not in self.catalog(p)[cap]:
                raise AiUnavailable("Qo‘lda tanlangan model hisob katalogida mavjud emas.")
            free = bool(row.get("free") and self.free_active())
            if row.get("price") is None and not free:
                raise AiUnavailable("Bu modelning pullik tarif narxi tasdiqlanmagan.")
            return [(p, {**row, "free": free})]
        out = []
        for p in self.connected():
            if provider_override and p != provider_override:
                continue
            have = self.catalog(p).get(cap) or []
            for row in caps.models_for(p, cap):
                free = bool(row.get("free")) and p == FREE_PROVIDER and self.free_active()
                if row["model"] in have and (row.get("price") is not None or free):
                    out.append((p, {**row, "free": free}))
        chosen = self.config().get("provider") or ""
        out.sort(key=lambda x: (not x[1]["free"], x[0] != chosen, float(x[1]["price"] or 0)))
        if not out:
            need = [models.PROVIDERS[p]["label"] for p in models.PROVIDERS if caps.supports(p, cap)]
            raise AiUnavailable(
                f"{caps.CAP_LABELS[cap]} uchun mos AI ulanmagan: "
                f"{' yoki '.join(need)} kalitini kiriting (Sozlamalar → AI)."
            )
        return out

    def media_estimate(self, cap: str, units: float) -> Estimate:
        p, row = self.candidates(cap)[0]
        return Estimate(p, row["model"], cap, 0, 0, caps.cost(row, units), bool(row.get("free")))

    def media(
        self,
        cap: str,
        units: float,
        call: Callable[[Any, str], Any],
        *,
        approved: bool = False,
        purpose: str | None = None,
        confirm_always: bool = False,
        provider_override: str | None = None,
    ):
        """Run a picture/speech call (`call(client, model)`) on the chosen model: budget and
        «Ha» like text; in AUTO a busy provider falls back to the next candidate."""
        if not self.config().get("enabled"):
            raise AiUnavailable("AI o‘chirilgan (Sozlamalar → AI).")
        cands = self.candidates(cap, provider_override)
        last: AiError | None = None
        for i, (p, row) in enumerate(cands):
            est = Estimate(p, row["model"], cap, 0, 0, caps.cost(row, units), bool(row.get("free")))
            if i == 0:
                self.check_budget(est, approved)
                if confirm_always and not approved and not est.free:
                    raise NeedsConfirmation(est)
            else:
                if self.manual(cap) or provider_override or not self.config().get("fallback"):
                    break
                # Free mode never moves from a free model to a paid one by itself.
                if cands[0][1].get("free") and self.free_active() and not est.free:
                    continue
                try:
                    self.check_budget(est, approved=True)
                except (BudgetExceeded, AiUnavailable):
                    continue
                if not approved and not est.free:
                    continue
                if approved and est.cost > caps.cost(cands[0][1], units):
                    raise NeedsConfirmation(est)
            try:
                out = call(self.media_factory(p, self.keys.load(p) or ""), row["model"])
            except AiError as e:
                if not e.retryable or self.manual(cap) is not None:
                    raise
                last = e
                continue
            self.ledger.record(p, row["model"], purpose or cap, 0, 0, est.cost)
            self._last_call.value = {
                "provider": p,
                "model": row["model"],
                "mode": "MANUAL" if self.manual(cap) else "AUTO",
                "free": est.free,
                "estimated_cost": est.cost,
                "cost": None,
                "cost_kind": "unknown",
            }
            return out, est
        raise last or AiUnavailable("Hech bir AI provayderi javob bermadi.")

    def capabilities_status(self) -> dict[str, Any]:
        """For the 🧠 menu: every direction, its mode and what each provider offers."""
        st = self.cap_settings()
        conn = set(self.connected())
        out = {}
        for c in caps.CAPABILITIES:
            offers = {}
            for p in models.PROVIDERS:
                if not caps.supports(p, c):
                    continue
                offers[p] = {"label": models.PROVIDERS[p]["label"], "connected": p in conn,
                             "models": self.catalog(p)[c]}  # fmt: skip
            try:
                auto = None if c in ("text", "vision") else self.candidates(c)[0]
            except AiUnavailable:
                auto = None
            out[c] = {
                "label": caps.CAP_LABELS[c],
                **st[c],
                "offers": offers,
                "auto_pick": {
                    "provider": auto[0],
                    "model": auto[1]["model"],
                    "free": bool(auto[1].get("free")),
                }
                if auto
                else None,
            }
        return {"capabilities": out, "voices": caps.VOICES, "catalog": self.catalog_status()}

    # ----- keys -----
    def save_key(self, provider: str, key: str) -> dict[str, Any]:
        """Check the key with the free model list, then store it and remember which model
        ids this account really has for each tier (a missing one is not shown as working)."""
        if provider not in models.PROVIDERS:
            raise ValueError("noma’lum provayder")
        key = (key or "").strip()
        if len(key) < 10:
            raise ValueError("kalit juda qisqa — to‘liq nusxalang")
        client = self.factory(provider, key)
        details = getattr(client, "list_model_details", None)
        available = details() if callable(details) else client.list_models()
        if not model_catalog.normalize(provider, available):
            raise AiUnavailable("Model ro‘yxati bo‘sh: kalit saqlanmadi.")
        self.keys.save(provider, key)
        info = self._store_catalog(provider, available)
        changes: dict[str, Any] = {}
        if provider == FREE_PROVIDER:
            changes["free_tier_confirmed"] = False
        cfg = self.config()
        if not cfg.get("provider") or not self.keys.load(cfg["provider"]):
            changes["provider"] = provider
        if changes:
            self.settings.update({"ai": changes})
        return info

    def delete_key(self, provider: str) -> None:
        self.keys.delete(provider)
        self._balances.pop(provider, None)

    # ----- carrying keys to another PC: one password-sealed file (scrypt + AES-GCM) -----
    def export_keys(self, password: str) -> bytes:
        from nexvara.sync import seal

        if len(password or "") < 8:
            raise ValueError("Parol kamida 8 belgi bo‘lsin")
        keys = {p: k for p in models.PROVIDERS if (k := self.keys.load(p))}
        if not keys:
            raise ValueError("Saqlanadigan AI kaliti yo‘q")
        return seal({"kind": "nexvara-ai-keys", "keys": keys,
                     "provider": self.config().get("provider") or ""}, password)  # fmt: skip

    def import_keys(self, blob: bytes, password: str) -> dict[str, list[str]]:
        """Restore keys from `export_keys`. A provider that already has a key here is left as is
        (never overwritten). Each key is checked with the free model list when online."""
        from nexvara.sync import SyncError, unseal

        try:
            data = unseal(blob, password)
        except SyncError as e:
            raise ValueError("Parol noto‘g‘ri yoki fayl buzilgan") from e
        if not isinstance(data, dict) or data.get("kind") != "nexvara-ai-keys":
            raise ValueError("Bu NEXVARA AI kalitlari fayli emas")
        added, kept = [], []
        for p, key in (data.get("keys") or {}).items():
            if p not in models.PROVIDERS:
                continue
            if self.keys.load(p):
                kept.append(p)
                continue
            try:
                self.save_key(p, key)
            except Exception:  # noqa: BLE001 - offline: store now, the catalog refreshes later
                self.keys.save(p, key)
            added.append(p)
        chosen = data.get("provider") or ""
        if chosen in added and not self.config().get("provider"):
            self.settings.update({"ai": {"provider": chosen}})
        return {"added": added, "kept": kept}

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
            "free_tier_confirmed": bool(cfg.get("free_tier_confirmed")),
            "free_active": self.free_active(),
            "catalog": self.catalog_status(),
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
