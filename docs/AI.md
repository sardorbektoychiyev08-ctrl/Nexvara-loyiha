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
- Fallback (`ai.fallback`, **off by default** — a paid fallback never starts by itself): when
  the user turns it on, a busy/down/unreachable provider (429, 5xx, network) hands the same
  request to another connected provider at the same tier, with the same limits and never
  above what the user agreed to. A wrong key or missing credit never switches silently.
- Saving a key only checks it (free model list); it does **not** switch paid AI on — the user
  ticks "AI yoqilgan" in Settings → AI.
- Per-provider limits also have a one-task cap (`limits.<provider>.task_usd`). Set for the
  first real OpenAI test: daily $0.25, one task $0.05. These are NEXVARA's own limits, not the
  provider's real spending cap — set that on the provider's site too.
- Home → "AI balans va xarajatlar": per provider spent today / month, limits, "left of
  limit" and — separately — the real provider balance (DeepSeek only; others say
  "Haqiqiy balansni avtomatik olish imkoni yo‘q").

## Personal data

Every request is masked locally first and restored locally after — see [PRIVACY.md](PRIVACY.md).
Unreliable detection blocks the request. Applies to all providers and to a fallback provider.

## Directions: AUTO / MANUAL per capability (2026-10-18)

`ai/capabilities.py` (registry), `ai/media.py` (official HTTPS APIs), `AiRouter.candidates /
media / set_capability / capabilities_status`, UI: chat 🧠 menu and Settings → AI.

| Direction | OpenAI | Gemini | Claude | DeepSeek |
|---|---|---|---|---|
| Text (tiers cheap/balanced/powerful/special) | ✓ | ✓ (Flash free) | ✓ | ✓ |
| Vision / OCR | ✓ | ✓ | ✓ | — |
| Image make/edit | gpt-image-1-mini, gpt-image-2, gpt-image-2.5-flare/-sunburst (Image API) | gemini-3.1-flash-lite-image, gemini-nano-banana-2.1, gemini-3.1-flash-image, gemini-3-pro-image (Interactions API, no free tier) | — | — |
| STT | gpt-4o-mini-transcribe, gpt-transcribe, whisper-1 | Flash/Flash-Lite with audio input (free) | — | — |
| TTS | gpt-4o-mini-tts | gemini-3.8-flash-lite-tts, gemini-3.8-flash-tts (free tier) | — | — |
| Realtime | STT → chat → TTS turn by turn | same | — | — |

Checked on 2026-10-18 against developers.openai.com/api/docs (pricing, image-generation,
text-to-speech, speech-to-text) and ai.google.dev/gemini-api/docs (models, pricing,
image-generation, speech-generation). A model is offered only if the key check found it in the
account's model list (`ai.catalog`). Uzbek is not listed by OpenAI TTS/STT docs; Gemini TTS lists
«Northern Uzbek» — real quality is NOT TESTED until the owner's key.

- **AUTO**: free first (Gemini free tier while «Bepul rejim» is on), then the cheapest; a busy
  provider (429/5xx/network) falls back to the next one inside the budget; a wrong key or no
  credit never falls back. For text an unusable answer (e.g. the planner's JSON) is retried once
  on the next stronger tier, never above the «ask first» limit.
- **MANUAL**: exactly the chosen provider+model, no fallback, no swapping; a choice the provider
  cannot do is refused when saved, and a missing key gives a clear message.
- **Money**: every media call goes through the same daily/monthly/provider/task limits and the
  ledger; ✨ pictures are never free and always ask «Ha» with the price; TTS/STT under the
  «ask first» limit run directly. 🔊 never sends personal data: found items are spoken as
  «yashirin ma’lumot».
- **Realtime**: the providers' streaming Realtime/Live APIs are not used (cost, complexity);
  🎧 chains 🎤 (silence ends a turn) → chat → 🔊 → 🎤.
- **New provider**: add it to `models.PROVIDERS` (tiers, prices, pages), a text adapter in
  `providers.make_provider`, and if it has media models a row in `capabilities.MEDIA` plus a
  client in `media.media_client`. Router, menu, budget and phone API pick it up from there.
- **Phone** (`docs/api/openapi.yaml`): `GET/POST /api/v1/ai/capabilities`, `POST
  /api/v1/ai/speak`; ✨ from the phone chat returns `image.path` for `GET /api/v1/files`.

## Conversation memory and self-repair (2026-10-18)

- **Memory**: chat, questions and the planner get the last `memory.recent_turns` (15) messages
  from `app.db` (they survive restarts), older exchanges from the last `memory.chat_days` (30)
  days that share words with the request (FTS5, at most 6), and one-line summaries of the
  previous 7 days (built locally, no AI). All of it is the user's text: masked by
  `ai/privacy.py` like the message. «… haqidagi gaplarni unut» / «buni unut» deletes chat
  lines (facts and rules stay); the whole chat is cleared only from the Memory page.
- **Self-repair** (`ai.self_repair`, on by default, only with AI ready): a command that fails
  (tool error, or an Office task started from chat) goes back to the planner with the error
  text; at most 2 tries per user message. A corrected plan that changes anything still waits
  for «Ha»; a repair never asks to spend above the confirm limit by itself.

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

Prepared script, synthetic texts only (the privacy guard must find nothing in them):

    .venv\Scripts\python.exe scripts\ai_live_test.py openai      # dry run: estimate, sends nothing
    .venv\Scripts\python.exe scripts\ai_live_test.py gemini
    .venv\Scripts\python.exe scripts\ai_live_test.py openai --run --i-approve   # real, after OK

Dry-run estimate (4 requests: chat, 2 plans, 1 question): OpenAI ≈ $0.021, Gemini ≈ $0.017.
A real run refuses without a key saved in Settings, without "AI yoqilgan", or with fallback on.
