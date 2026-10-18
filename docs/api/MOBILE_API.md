# NEXVARA Phone API v1

The contract between the Android app and the Windows Agent. The machine-readable version is
[openapi.yaml](openapi.yaml); the server is [src/nexvara/remote_v1.py](../../src/nexvara/remote_v1.py),
the shared constants are in [src/nexvara/protocol.py](../../src/nexvara/protocol.py). A unit test
fails if the route list here and in the server differ.

## 1. Transport and trust

- HTTPS (TLS 1.2+) on the local network, default port `8765`. Nothing is exposed to the internet.
- The PC uses a self-signed ECDSA P-256 certificate (`D:\NEXVARA\remote\cert.pem`), renewed when
  the PC's IP changes.
- **Certificate pinning (mandatory):** the pairing QR code carries the SHA-256 of the
  certificate (DER, lowercase hex). The app accepts a TLS connection only if the leaf
  certificate's SHA-256 equals the stored `fp`. Do not trust user/system CAs for this host and
  do not disable verification globally.
- If the certificate changes (new IP), pinning fails: show "Kompyuter sertifikati o‘zgardi —
  qaytadan bog‘lang" and re-run pairing (scan a new QR).

## 2. Pairing

The QR code on the PC (Devices page, "Telefonni ulash") holds one URL:

```
https://192.168.1.10:8765/#p=123456&sid=c565070bb125e184&fp=f28bf5...9263
```

| Field | Meaning |
|---|---|
| host:port | where the PC listens |
| `p` | one-time 6-digit code, valid 10 minutes, locked after 5 wrong attempts |
| `sid` | stable random id of this PC (lets the app keep "Work PC" and "Home PC") |
| `fp` | SHA-256 of the PC certificate (pin it) |

A phone browser opening the same URL gets the web version, so one QR serves both.

Flow:
1. Scan QR → parse host, port, `p`, `sid`, `fp`.
2. `GET /api/v1/info` (pinned) → check `protocol >= 1` and `server_id == sid`.
3. `POST /api/v1/pair` `{code, device_name, platform:"android", app_version, install_id}`.
   `install_id` is a random UUID created on first app start; pairing again with the same id
   replaces the old entry on the PC (no duplicates).
4. Store `{server_id, host, port, fp, token, device_id, pc_name}` encrypted (Android Keystore key,
   AES-GCM). Several PCs may be stored; the user picks one.

Manual entry fallback: the user types the PC address and the 6-digit code; then the app has no
`fp` and must show the certificate fingerprint and ask the user to compare it with the PC
screen (the Devices page shows its first 16 and last 8 hex characters) before trusting it.
Prefer QR.

## 3. Requests

- `Authorization: Bearer <token>` on everything except `info` and `pair`.
- `X-Nexvara-Protocol: 1` on every request (the server answers `426 UNSUPPORTED_PROTOCOL` when
  the app is too old).
- `X-Request-Id: <uuid>` on every POST. Generate it **once per user action** and reuse it on
  retries: the server returns the first reply for the same id (10 minutes) and never runs a
  command twice.
- JSON bodies are UTF-8. Text limit 4000 characters. Uploads up to 50 MB.

Every JSON reply is an envelope:

```json
{"v": 1, "ok": true, "data": { ... }}
{"v": 1, "ok": false, "error": {"code": "TOKEN_EXPIRED", "message": "Ulanish muddati tugagan...", "retry": false}}
```

Switch on `error.code`; `error.message` is Uzbek text that may be shown as is.

## 4. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/info` | protocol, app version, PC name, `server_id`, whether pairing is open |
| POST | `/api/v1/pair` | code → token |
| GET | `/api/v1/session` | device name, token expiry, `rotate_recommended` |
| POST | `/api/v1/session/rotate` | new token (old one works until the new one is used) |
| POST | `/api/v1/session/logout` | unpair this phone |
| POST | `/api/v1/chat` | natural-language command → `{reply, confirm, task, open_bi?}` |
| POST | `/api/v1/confirm` | answer a confirmation (`{token, yes}`) |
| GET | `/api/v1/tasks?limit=20` | recent tasks + `etag` |
| GET | `/api/v1/tasks/watch?etag=&wait=25` | long-poll for changes |
| GET | `/api/v1/tasks/{id}` | one task |
| POST | `/api/v1/tasks/{id}/cancel` | cancel |
| POST | `/api/v1/files` | upload (raw body, `X-Filename`, optional `X-Content-SHA256`) |
| GET | `/api/v1/files?path=` | download a result file (header `X-Content-SHA256`) |

`/api/v1/chat` uses the **same agent pipeline as the PC chat** (Office commands, tests from
textbooks, topics, BI, files, workflows, memory, Teach, theme). A paid AI request never runs
without a `confirm` answered with `yes: true`.

## 5. Task state machine

```
pending → running → succeeded
             ⇅     ↘ failed
           paused   ↘ cancelled   (after POST /cancel; cancellation is cooperative)
```

`POST /tasks/{id}/pause` only sets `pause_requested`; the task stops at its **next step
boundary** (never in the middle of an Office call) and its status becomes `paused`.
`POST /tasks/{id}/resume` continues it. Cancel works while paused. Paused time does not count
towards the 10-minute hung-task timeout.

`succeeded`, `failed`, `cancelled` are final. `files` lists PC paths of results; download them
with `GET /api/v1/files?path=<exact string>` (only files that some task produced are served).

## 6. Live progress, offline and retries

- While the app is in the foreground: loop `GET /api/v1/tasks/watch?etag=<last>&wait=25`.
  It returns immediately when anything changed (`changed: true`), else after 25 s with
  `changed: false`; then call again with the new `etag`.
- In the background: a WorkManager periodic job (15 min) calls `GET /api/v1/tasks` and posts a
  local notification when a task the user started becomes final. (Real push via FCM needs a
  Firebase project and an internet relay — **BLOCKED**, see ANDROID_HANDOFF.md.)
- Offline queue: if the PC is unreachable, keep the message with its `X-Request-Id` in a local
  queue and show "Kompyuter javob bermayapti — buyruq navbatda". Retry with backoff
  (2 s, 5 s, 15 s, 60 s, then every 5 min). Thanks to the request id a retry never runs twice.
- Error handling:

| code | HTTP | app action |
|---|---|---|
| `BAD_REQUEST` | 400 | show message, do not retry |
| `AUTH_REQUIRED` | 401 | token unknown (revoked on PC) → remove this PC, ask to pair again |
| `TOKEN_EXPIRED` | 401 | token older than 30 days → pair again |
| `PAIRING_CODE_INVALID` / `_EXPIRED` / `PAIRING_LOCKED` | 403 | show message; the user takes a new code on the PC |
| `NOT_FOUND` | 404 | show message |
| `PAYLOAD_TOO_LARGE` | 413 | file > 50 MB |
| `UNSUPPORTED_PROTOCOL` | 426 | ask the user to update the app |
| `RATE_LIMITED` | 429 | wait `Retry-After` seconds |
| `INTERNAL` | 500 | retry later |
| network error / timeout | — | "Kompyuter o‘chiq yoki boshqa tarmoqda" + queue |

## 7. Token lifecycle

- Token: 256-bit random, stored on the PC only as SHA-256.
- `GET /api/v1/session` → when `rotate_recommended` is true (token older than 7 days) call
  `POST /api/v1/session/rotate`, store the new token, then use it. The old token keeps working
  until the new one is used once, so a lost reply does not lock the phone out.
- Expiry: 30 days without rotation → `TOKEN_EXPIRED`.
- Logout in the app → `POST /api/v1/session/logout`, then delete local data for that PC.
- The PC user can revoke any device on the Devices page.

## 8. Limits

240 requests/minute per address, 10 pairing attempts/minute per address, 5 wrong codes lock
the current code. Long-poll holds at most 25 s.

## 10. Sync (settings, memory, Teach rules)

`GET /api/v1/sync` → `{device, records}`; `POST /api/v1/sync` `{records}` → the PC merges and
returns `{applied, device, records}` (all records after the merge). A record:

```json
{"kind": "fact|rule|setting", "uid": "…", "data": {…}, "updated": 1792215013.9,
 "device": "phone-3", "deleted": false}
```

- `fact.data = {text}`, `rule.data = {app, text, enabled}`, `setting.data = {value}`
  (`uid` = key: theme, test_count, test_variants, keep_office_open, ai.daily_budget_usd,
  ai.monthly_budget_usd, ai.confirm_over_usd, ai.send_textbook_text). Other keys are ignored.
- Merge rule per item: the larger `(updated, device)` wins; deletions are records with
  `deleted: true` (keep them). New items on the phone get a random `uid`.
- App algorithm: keep local records the same way; on sync POST your changed records, replace
  local state with the returned list (apply newer ones), remember the time.

## 11. Sections (Android V1 screens)

All routes need the device token; POSTs take `X-Request-Id`. They wrap the same `Api`
methods the PC window uses (`src/nexvara/remote_v1_sections.py`), so the phone and the PC see
one database.

| Screen | Routes |
|---|---|
| Home | `GET /overview` — PC, last 5 tasks, running count, counts (memory, teach, workflows, dashboards), AI panel, sync state (folder *name* only), Google state |
| Chat history | `GET /chat/history?limit=&after=` — the PC chat log (`id`, `ts`, `role`, `text`); `after` is the last id the phone saw |
| AI spend | `GET /ai` — per provider (openai, gemini, anthropic, deepseek): spent today/month, NEXVARA limits, `left_today`/`left_month`, real `balance` if known, official `billing_url`/`usage_url`, 30-day series, last calls. **No key, not even masked.** `POST /ai/{provider}/balance` refreshes the real balance (DeepSeek only; no model call) |
| Memory | `GET/POST /memory`, `GET /memory/search?q=`, `POST /memory/{id}`, `POST /memory/{id}/delete` |
| Teach | `GET/POST /teach` (`preview: true` only checks), `POST /teach/{id}` (`text`, `enabled`), `POST /teach/{id}/delete` |
| Workflows | `GET/POST /workflows`, `POST /workflows/{id}/run` (`file` must be a file the phone uploaded), `POST /workflows/{id}/delete`, `POST /workflows/runs/{id}/{approve|pause|resume}` |
| NEXVARA BI | `GET /bi`, `POST /bi/open` (`file`, `state`, `show_on_pc`) → compact widgets (KPI, bar/pie top 12, line ≤ 60 points × 3 series, table ≤ 20 rows); the PC window opens the same dashboard |
| Textbooks | `GET /library`, `POST /library/test` (`grade`, `subject`, `topic`, `count`, `variants`, `ai`); a paid AI test returns `confirm` first |
| Office | `POST /office/{excel_demo|excel_dashboard|word_report|presentation}`; free-form Office commands go through `/chat` |
| Google | `GET /account`; `POST /account/link` (`id_token` from Android Credential Manager) |

**One system.** A command from the phone shows up in the PC chat ("📱 Telefondan: …"), its
task appears in the PC task panel, and a dashboard opened from the phone opens in the PC
window (`Api.ui_events`, polled by the PC page). Office runs **visibly** on the PC screen
unless the command says "fonda bajar".

**AI spend is counted once.** The phone never calls an AI provider: its requests run on the
PC through `AiRouter.complete` (privacy guard → provider → `ai_usage` ledger in `app.db`).

**Privacy.** Every AI request from the phone passes the same local masking as the PC (names,
JSHSHIR, phone numbers… → placeholders; blocked when unsure). Covered by
`test_phone_ai_chat_is_masked_and_counted_once`.

**Google on the phone.** The phone signs in with Android Credential Manager using the PC's
`android_web_client_id` (settings.json, public) as `serverClientId`; the PC verifies the ID
token's signature, audience and that `sub` equals the PC owner, then stores only the email on
the device row. Setup: [../GOOGLE_LOGIN.md](../GOOGLE_LOGIN.md) § Android.

## 12. Other networks, PC screen, PC files

**Other Wi-Fi / mobile data (Tailscale).** `info` and `session` return `port` and
`addresses` (`{"ip", "kind": "lan"|"tailscale"}`); the phone stores them and tries them in
order, remembering the one that answered. Trust is the certificate pin only (hostname is not
checked), so the PC is the same PC on any address. The certificate is made once and **kept**
when the PC changes network (older builds regenerated it per IP and broke the pin). Requests
from public internet addresses are refused (`remote.allowed_client`: private ranges,
loopback, link-local, Tailscale 100.64.0.0/10 only) — a router port-forward cannot expose it.

**PC screen.** `GET /screen` → JPEG of the primary monitor (view only). `settings.json →
remote.screen_view: false` turns it off; the PC window shows «📱 Telefon ekranni ko‘rmoqda».

**PC files.** `GET /files/search?q=&ext=` searches the user folders by name; results may be
opened on the PC (`POST /files/open`, programs/scripts refused) or shared to the phone
(`POST /files/share` → `GET /files?path=` for 30 minutes) for 10 minutes. Keys, databases,
`*.pem/*.jks/*.kdbx…` and NEXVARA's own `remote/`, `telegram/`, `release/` are never listed.

## 13. Teacher and office tools

| Area | Routes |
|---|---|
| Answer sheets | `GET/POST /omr`, `POST /omr/{id}/keys`, `POST /omr/{id}/grade` (`path` of an uploaded photo). Sheet = PDF with 4 corner squares; reading = homography + Otsu threshold (`src/nexvara/omr.py`); results → Excel |
| Class journal | `GET/POST /journal`, `GET /journal/{id}?subject=`, `POST /journal/{id}/students|delete|export`, `POST /journal/grade`, `POST /journal/grade/{id}/delete` |
| Documents | `GET /doctemplates`, `POST /doctemplates/{id}` (`fields`, `background`) → Word on the PC, DOCX + PDF |
| Photo → text | `POST /ocr` (`path`, `lang`): Windows OCR offline, enhanced photo, best of Latin/Cyrillic; in chat «AI bilan … o‘qi» reads handwriting after consent |
| Preview | `GET /files/preview?path=`: PDF / picture / text as is, Office → PDF in a temp folder |
| Control | `POST /control` (off unless `remote.control`; PC shows «📱 Telefon boshqarmoqda») |
| Autostart | `GET/POST /autostart`; `session.wake` = `{mac, broadcast}` for Wake-on-LAN |

## 9. Testing without the real PC data

```
.venv\Scripts\python.exe -m nexvara.devserver --port 8765
```

starts the real v1 server with a fake agent (each chat message → a 3-step task → a small text
file) in a temporary folder and prints the pairing link with `fp`. Use it from the Android
emulator (`10.0.2.2` is the host PC) or a phone on the same Wi-Fi.
