"""Model router: picks provider and tier, enforces the budget, records every call's cost.

Rules (spec: no surprise spending):
- nothing is sent unless the user turned AI on and saved a key;
- a call whose estimate would cross the daily or monthly budget is refused;
- a call estimated above `confirm_over_usd` waits for the user's "Ha";
- the real cost (from the provider's token counts) is written to app.db.
"""

from __future__ import annotations

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
from nexvara.ai.providers import AiError, Provider, Reply, make_provider
from nexvara.core.task import UserError

# purpose -> tier. Understanding a command is easy; answers and tests need a better model.
TIER_FOR = {"classify": "cheap", "qa": "balanced", "test": "balanced", "command": "cheap"}
PURPOSE_LABELS = {
    "classify": "Buyruqni tushunish",
    "qa": "Savolga javob",
    "test": "AI test",
    "check": "Kalitni tekshirish",
}

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

    def spent_since(self, ts: float) -> float:
        with self._db() as db:
            (v,) = db.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM ai_usage WHERE ts >= ?", (ts,)
            ).fetchone()
        return float(v)

    def today(self) -> float:
        t = time.localtime()
        return self.spent_since(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1)))

    def month(self) -> float:
        t = time.localtime()
        return self.spent_since(time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1)))

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

    def describe(self) -> str:
        return (
            f"{models.PROVIDERS[self.provider]['label']} · {self.model}: taxminan "
            f"${self.cost:.3f} (≈{self.input_tokens} + {self.output_tokens} token)"
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
    ) -> None:
        from nexvara.appdata import Settings

        self.settings = settings or Settings()
        self.keys = keys or KeyStore()
        self.ledger = ledger or Ledger()
        self.factory = factory or make_provider

    # ----- configuration -----
    def config(self) -> dict[str, Any]:
        return self.settings.load()["ai"]

    def provider_name(self) -> str | None:
        """The chosen provider if it has a key, else the first provider that has one."""
        chosen = self.config().get("provider") or ""
        if chosen and self.keys.load(chosen):
            return chosen
        for name in models.PROVIDERS:
            if self.keys.load(name):
                return name
        return None

    def ready(self) -> bool:
        return bool(self.config().get("enabled")) and self.provider_name() is not None

    def model_for(self, provider: str, tier: str) -> str:
        chosen = (self.config().get("models") or {}).get(provider) or {}
        return chosen.get(tier) or models.PROVIDERS[provider]["tiers"][tier]

    # ----- spending -----
    def estimate(self, tier: str, system: str, messages: list[dict], expected_out: int) -> Estimate:
        provider = self.provider_name()
        if provider is None:
            raise AiUnavailable("AI kaliti kiritilmagan (Sozlamalar → AI).")
        model = self.model_for(provider, tier)
        tin = models.estimate_tokens(system + "".join(m["content"] for m in messages))
        c = models.cost(model, provider, tin, expected_out, self.config().get("prices"))
        return Estimate(provider, model, tier, tin, expected_out, c)

    def check_budget(self, est: Estimate, approved: bool) -> None:
        cfg = self.config()
        today, month = self.ledger.today(), self.ledger.month()
        if today + est.cost > float(cfg["daily_budget_usd"]):
            raise BudgetExceeded(
                f"Kunlik AI byudjeti (${cfg['daily_budget_usd']:.2f}) tugaydi: bugun "
                f"${today:.3f} sarflangan, bu so‘rov ≈${est.cost:.3f}. Byudjetni "
                "Sozlamalar → AI bo‘limida oshirish mumkin."
            )
        if month + est.cost > float(cfg["monthly_budget_usd"]):
            raise BudgetExceeded(
                f"Oylik AI byudjeti (${cfg['monthly_budget_usd']:.2f}) tugaydi: shu oy "
                f"${month:.3f} sarflangan."
            )
        if not approved and est.cost > float(cfg["confirm_over_usd"]):
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
        if not self.config().get("enabled"):
            raise AiUnavailable("AI o‘chirilgan (Sozlamalar → AI).")
        tier = tier or TIER_FOR.get(purpose, "balanced")
        est = self.estimate(tier, system, messages, expected_out or max_tokens // 2)
        self.check_budget(est, approved)
        key = self.keys.load(est.provider) or ""
        reply = self.factory(est.provider, key).complete(
            est.model, system, messages, max_tokens, effort
        )
        reply.provider = est.provider
        reply.cost = models.cost(
            reply.model or est.model,
            est.provider,
            reply.input_tokens,
            reply.output_tokens,
            self.config().get("prices"),
        )
        self.ledger.record(
            est.provider, reply.model or est.model, purpose, reply.input_tokens,
            reply.output_tokens, reply.cost,
        )  # fmt: skip
        return reply

    # ----- keys -----
    def save_key(self, provider: str, key: str) -> dict[str, Any]:
        """Check the key with the free model list, then store it and remember which model
        ids this account really has for each tier."""
        if provider not in models.PROVIDERS:
            raise ValueError("noma’lum provayder")
        key = (key or "").strip()
        if len(key) < 10:
            raise ValueError("kalit juda qisqa — to‘liq nusxalang")
        available = self.factory(provider, key).list_models()
        tiers = {
            t: models.pick_model(models.PROVIDERS[provider]["tiers"][t], available)
            for t in models.TIERS
        }
        self.keys.save(provider, key)
        cfg = self.config()
        chosen = dict(cfg.get("models") or {})
        chosen[provider] = tiers
        changes: dict[str, Any] = {"models": chosen}
        if not cfg.get("provider") or not self.keys.load(cfg["provider"]):
            changes["provider"] = provider
        if not cfg.get("enabled"):
            changes["enabled"] = True
        self.settings.update({"ai": changes})
        missing = [m for m in tiers.values() if available and m not in available]
        return {"models": tiers, "available": len(available), "missing": missing}

    def delete_key(self, provider: str) -> None:
        self.keys.delete(provider)

    def status(self) -> dict[str, Any]:
        cfg = self.config()
        providers = {}
        for name, info in models.PROVIDERS.items():
            key = self.keys.load(name)
            providers[name] = {
                "label": info["label"],
                "key_url": info["key_url"],
                "key_hint": info["key_hint"],
                "has_key": bool(key),
                "key_masked": mask(key),
                "models": {t: self.model_for(name, t) for t in models.TIERS},
            }
        return {
            "enabled": bool(cfg.get("enabled")),
            "provider": self.provider_name() or "",
            "ready": self.ready(),
            "providers": providers,
            "tier_labels": models.TIER_LABELS,
            "spent_today": round(self.ledger.today(), 4),
            "spent_month": round(self.ledger.month(), 4),
            "daily_budget_usd": cfg["daily_budget_usd"],
            "monthly_budget_usd": cfg["monthly_budget_usd"],
            "confirm_over_usd": cfg["confirm_over_usd"],
            "send_textbook_text": cfg["send_textbook_text"],
        }


__all__ = [
    "AiError",
    "AiRouter",
    "AiUnavailable",
    "BudgetExceeded",
    "Estimate",
    "Ledger",
    "NeedsConfirmation",
]
