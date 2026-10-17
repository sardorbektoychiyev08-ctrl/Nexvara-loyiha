# HANDOFF → Codex (Windows side)

Written by Claude Code on 2026-10-17 so that Codex can continue the **Windows** work if
Claude's limit runs out. Android has its own document: [docs/ANDROID_HANDOFF.md](docs/ANDROID_HANDOFF.md)
(Codex already works there on `codex/android-mobile` in `.worktrees/android` — Claude never
touches that branch or worktree; please keep Windows changes off it too).

Read first: [AGENTS.md](AGENTS.md) (rules), the newest entry of [PROGRESS.md](PROGRESS.md),
[docs/AGENT.md](docs/AGENT.md) (how a chat message becomes work),
[docs/SECTIONS_STATUS.md](docs/SECTIONS_STATUS.md) (what is done per section).

## State at handoff

- Branch `main` = last tested state; Claude's last branch is listed in PROGRESS.md.
- Tests: `.\scripts\test.ps1` (lint + unit + window smoke). With Office:
  `.\scripts\test.ps1 -Office` (opens visible Excel/Word/PowerPoint on throwaway files in
  pytest's temp folder; the user has allowed it for test files only — never on their files).
- Build: `.\scripts\build.ps1` → `dist\installer\NEXVARA-Setup-<ver>.exe` ([docs/RELEASE.md](docs/RELEASE.md)).

## How to add a new chat ability (the pattern used everywhere)

1. Add a tool in `src/nexvara/agent/tools.py` with `@tool("area.action", "Uzbek title",
   param=(type, required, description), risky=...)`. Resolve paths with `resolve_file`,
   `resolve_files`, `resolve_folder`; raise `ToolError("Uzbek message")` on problems.
   `risky=True` for anything that deletes, overwrites or reorganises user data.
2. Add an offline Uzbek pattern in `src/nexvara/agent/nlu.py` (the matching `_area()`
   function) that returns `[ToolCall(...)]`. Keep patterns strict; anything unmatched must
   fall through (return None). Use `fold()` text for matching and the original text for
   names/paths.
3. Unit test through `Api.chat("...")` and check the real effect (file on disk, store row,
   setting), e.g. `tests/unit/test_agent_sections.py`, `test_agent_bi.py`.
4. The AI planner sees new tools automatically (`tools.catalog()`); no prompt change needed.

## Open items (priority order)

| # | Item | Notes |
|---|---|---|
| 1 | Real AI planner test with the user's key | Only with the user's explicit OK (paid). `Settings → AI`; budget limits already enforced |
| 2 | Real Google login + Drive sync | User creates a *Desktop app* OAuth client, imports JSON in Settings, signs in **themselves**. Never sign in for them. Steps: docs/GOOGLE_LOGIN.md |
| 3 | Task history sync | `sync.py` syncs facts, rules, safe settings. History rows hold PC paths; sync titles/status only, mark files as "on <pc>" |
| 4 | BI: widget move between pages, delete page, slicer list editing via chat | Tools `bi.*` in tools.py; UI in `app/ui/bi.js` |
| 5 | M5: Vision / Web research / Computer control | not started |
| 6 | Code signing (Authenticode) | BLOCKED: needs a certificate |
| 7 | Two real PCs / phone sync E2E | needs the user's second device |

## Safety rules that tests enforce — do not weaken

- API keys only in Windows Credential Manager; a key pasted into chat is refused and never
  logged (`looks_like_secret`).
- Plans proposed by the AI that change anything are shown and need the user's "Ha";
  risky tools always need it.
- Copies/moves never overwrite (`fileagent.free_name`); deletes go to the Recycle Bin.
- Office executors write `<name>_NEXVARA.*`; the original file must stay byte-identical.
- Sync never transfers keys, tokens, `ai.enabled` or machine paths; files are AES-GCM
  encrypted with the user's passphrase.
- Updates are accepted only with a valid Ed25519 signature + SHA-256 (`updater.py`).
- Never commit `D:\NEXVARA\*` (keys, `google_client.json`, `app.db`, `release\signing_key.pem`).

## Where things are

| Area | Code | Tests |
|---|---|---|
| Chat entry, routing | `app/api.py` (`chat`, `_chat_inner`), `app/api_agent.py` | `tests/unit/test_agent_core.py` |
| Tools / offline rules / context | `agent/tools.py`, `agent/nlu.py`, `agent/context.py` | `test_agent_sections.py`, `test_agent_bi.py` |
| AI | `ai/` (router, providers, `features.plan`) | `test_ai.py` (fake providers only) |
| Office | `skills/excel|word|powerpoint`, `agent/*_exec.py` | `tests/office/` |
| BI | `bi/data.py` (load, ETL incl. calc/join/append), `bi/dash.py` | `test_bi.py`, `test_agent_bi.py` |
| Memory / Teach | `memory/` | `test_memory.py` |
| Workflows | `workflows.py`, `app/api_workflows.py` | `test_workflows.py` |
| Files | `fileagent.py` | `test_fileagent.py` |
| Sync | `sync.py`, `app/api_sync.py`, `/api/v1/sync` | `test_sync.py` |
| Phone API | `remote.py`, `remote_v1.py`, `protocol.py`, `docs/api/` | `test_remote*.py` |
| Google | `account.py`, `app/api_account.py` | `test_account.py` (fake Google) |
| Installer / updates | `installer/`, `scripts/build.ps1`, `updater.py` | `test_updater.py` |

When you finish a piece: run the tests, add a PROGRESS.md entry on top (date, "Codex",
what, PASS/FAIL/BLOCKED/NOT TESTED), commit on a `codex/<topic>` branch, and merge to
`main` only after `main` is merged in and tests pass.
