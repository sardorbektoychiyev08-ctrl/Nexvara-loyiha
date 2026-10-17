# AI providers, Model Router and spend control

Code: [src/nexvara/ai/](../src/nexvara/ai/) (`models.py` — providers, tiers, prices, official pages;
`router.py` — routing, limits, fallback, ledger; `providers.py` — HTTP/SDK adapters and the
DeepSeek balance call). Facts below were checked against the providers' official docs on
**2026-10-17**; prices drift, so `settings.json → ai.prices` can override any of them.

## Providers (one key is enough; the others are optional)

| Provider | API keys | Payment / balance page | Real balance via API | Free API quota (official) |
|---|---|---|---|---|
| OpenAI | platform.openai.com/api-keys | platform.openai.com/settings/organization/billing/overview | no | none announced (prepaid credit) |
| Claude (Anthropic) | platform.claude.com/settings/keys | platform.claude.com/settings/billing | no (Admin API only) | none announced |
| Google Gemini | aistudio.google.com/api-keys | aistudio.google.com/billing | no ("only in AI Studio") | yes: Free Tier for some models (Flash, Flash-Lite) within their rate limits; no free tier for Pro |
| DeepSeek | platform.deepseek.com/api_keys | platform.deepseek.com | **yes**: `GET https://api.deepseek.com/user/balance` | none announced; a granted balance, if any, shows in the balance call |

A ChatGPT / Claude / Gemini app subscription (Plus, Pro, Max, Advanced, Google One) is **not**
API credit. NEXVARA never takes payment: "To‘lov / Balans" opens the official page in the
default browser; no card number, CVV or bank password is ever entered into NEXVARA.

## Tiers

| Tier | Uzbek | Used for | OpenAI | Claude | Gemini | DeepSeek |
|---|---|---|---|---|---|---|
| cheap | Tejamkor | understanding a command, short replies | gpt-6-luna | claude-haiku-5-5 | gemini-3.5-flash-lite | deepseek-flash |
| balanced | Muvozanatli | everyday chat, Office plans, Q&A, AI tests | gpt-6-sol | claude-sonnet-5-5 | gemini-3.8-flash | deepseek-flash |
| powerful | Kuchli | analysis, planning, long multi-part tasks | gpt-6.1-sol | claude-opus-5-5 | gemini-3.1-pro-preview | deepseek-v4-pro |
| special | Maxsus | only on request ("eng kuchli model bilan"), always asks | gpt-6-astra | claude-fable-5-1 | gemini-3.1-pro-preview-customtools | deepseek-v4-pro |

When a key is saved, its model list is read (free). A tier model the account does not have
is replaced by the first available alternative from `models.PROVIDERS[...]["alternatives"]`;
if none is available the tier is shown as "bu hisobda mavjud emas" — never as a working model.
Outdated ids found in the check: `gemini-3.5-flash` (no longer listed), `deepseek-v4-flash`
(legacy name, now `deepseek-flash`).

## Spend control

- Every call is written to `app.db → ai_usage` with tokens and the **estimated** cost
  (provider token counts × price). It is not the bill; the provider's page is.
- Limits: overall daily / monthly, per provider daily / monthly (optional), one task
  (`task_limit_usd`, default $0.50), and "ask above" (`confirm_over_usd`, default $0.05).
  The special tier always asks. At 80% a warning is shown; at 100% new paid calls are blocked.
- Fallback (`ai.fallback`, on): a busy/down/unreachable provider (429, 5xx, network) hands the
  same request to another connected provider at the same tier, with the same limits and never
  above what the user agreed to. A wrong key or missing credit never switches silently.
- Home → "AI balans va xarajatlar": per provider spent today / month, limits, "left of
  limit" and — separately — the real provider balance (DeepSeek only; others say
  "Haqiqiy balansni avtomatik olish imkoni yo‘q").

## Security

Keys: Windows Credential Manager (`NEXVARA/ai/<provider>`) only. A key pasted into chat is
refused and not stored; key-like strings are masked in AI errors and in every log line
(`keys.redact`, `RedactingFilter`); keys are never synced (sync carries only safe settings).

## Real API test (not run yet — needs the owner's OK)

Estimated with NEXVARA's own estimator: one planner call ≈ 2,000 input + 400 output tokens:

| Provider | Tejamkor | Muvozanatli | Kuchli |
|---|---|---|---|
| OpenAI | $0.0004 | $0.0080 | $0.0080 |
| Claude | $0.0004 | $0.0080 | $0.0160 |
| Gemini | $0.0016 | $0.0060 | $0.0088 |
| DeepSeek | $0.0011 | $0.0011 | $0.0042 |

Proposed test per connected provider: key check (free) + 3 chat commands + 1 textbook question
≈ **under $0.05 per provider, under $0.20 for all four**; run with a temporary daily limit of
$0.25 so it cannot exceed that.
