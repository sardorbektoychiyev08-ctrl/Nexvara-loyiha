# HANDOFF → Codex (Windows side)

## ▶ CURRENT TASK 3 (2026-10-18 noon, Claude) — continue from here if Claude stopped

Owner: "do all six proposals; an AI button that redraws my rough sketch correctly; install the
update on the phone; be ready for API keys". APK 1.2.3 is installed on the phone (11:57).
Order and status (Claude ticks these as it goes):
- [x] (APK 1.2.4 installed) AI fix of a rough drawing: `src/nexvara/cad_ai.py` (AI prompt → editor JSON validated by
  `api_cad.json_to_doc`; offline `beautify()` when no AI), `CadApi.cad_ai_fix`, phone route
  `POST /api/v1/cad/ai`, PC toolbar button, phone «AI» button (CadScreen.kt). Android 1.2.4.
- [ ] Drawing templates (GOST A4/A3 frame + title block, bolt, nut, washer, bearing).
- [ ] Auto-fix documents («kamchiliklarni tuzat») for Excel/Word/PowerPoint.
- [ ] Lesson plan from a textbook topic («dars ishlanmasi»): plan (Word) + questions + slides.
- [ ] Weekly report workflow template (every Friday: Excel → PDF → phone).
- [ ] 3D view of a drawing (extrude closed shapes) in the PC editor.
- [ ] Voice command on the PC (mic → WAV → Gemini transcription; needs the user's key + consent).
- [ ] Full tests, PROGRESS entry, build/install APK.

## ▶ CURRENT TASK 2 (2026-10-18, Claude) — continue from here if Claude stopped

Owner asked: review Codex's work and fix gaps; Office "taught from official sources";
CAD on Android with hand drawing; CAD "full functionality"; Uzbek always in Latin (no
Cyrillic); then API keys; propose new features.

- [x] CAD 2.0 (commit 1643b22): `app/ui/cad.js` rewritten (hatch, ellipse, polygon, linear/
  aligned/radius/diameter dims, trim, extend, fillet, chamfer, scale, rect/polar array, explode,
  grips, osnaps end/mid/center/quad/int/perp/near with markers, layer colour/weight/linetype/
  lock/rename/delete, properties panel, area/distance, zoom window, Ctrl+C/V/A).
  `api_cad.py`: new JSON kinds `ldim`, `rdim`, `hatch`, entity `color`, layer `locked`.
  Real-window test `tests/ui_scripts/cad_tools.py` PASS.
- [x] Latin only: `textnorm.cyr_to_latin / to_latin_if_uzbek`; router adds `LATIN_RULE` to every
  system prompt and converts Cyrillic-Uzbek answers (not when the user asks for Russian);
  Uzbek Cyrillic textbooks are converted at indexing (Russian ones stay skipped).
  Tests `tests/unit/test_latin.py`.
- [x] (commit 66812ac, APK 1.2.3 built — NOT installed: phone was disconnected) Android «Chizma» screen with hand drawing (Compose canvas: finger strokes → straightened
  into line/rect/circle/arc; pinch zoom; tools; send to PC as DXF via a new `/api/v1` route
  that calls `CadApi.cad_save`; open the PC's last drawing on the phone).
- [x] (done) Office guidance from official sources (Microsoft support, O‘zDSt/«Davlat tilida ish
  yuritish») as `src/nexvara/knowledge/office_guide.py` used by AI prompts (`ai/features.py`).
- [x] Full test run PASS (511), PROGRESS entry (28). Next: install APK 1.2.3 when the phone is connected; owner adds Gemini key.

2026-10-18 Codex update: the textbook test-writing task is complete on
`claude/android-v1`. The AI test prompt now carries the assessment rules and the
requested grade/subject/topic; returned questions require an exact excerpt from
the claimed textbook page. Duplicate questions/options are filtered. The Word
answer key says whether AI was used. See PROGRESS entry (27) and
`docs/TEST_TUZISH_QOIDALARI.md`. `test.ps1` PASS (421 passed, 70 skipped),
`test.ps1 -Office` PASS (491 passed). Real paid AI was not called. No merge or push.

2026-10-18 Codex update: the later document-template task is complete on
`claude/android-v1` (general/leave/job applications, formal Word layout, eight real Word
DOCX/PDF tests). See PROGRESS entry (26) and `docs/HUJJAT_SHABLONLARI.md`. The CAD task
below is historical. No merge or push.

## ▶ CURRENT TASK (2026-10-18) — completed on `claude/android-v1` by Codex

Branch: **`claude/android-v1`**, worktree `D:\Nexvara loyiha\.worktrees\android` (no `.venv`
there: use `..\..\.venv\Scripts\python.exe`; for subprocess/smoke set
`PYTHONPATH=<worktree>\src`, otherwise the `main` copy is tested). Newest PROGRESS entry = what
is done. The owner (Uzbek, non-programmer) asked for 4 things on 2026-10-18:

| # | Task | Status | Where / how |
|---|---|---|---|
| A | **Built-in CAD ("AutoCAD inside NEXVARA")**: the user must not need AutoCAD. A «Chizma» page in the Windows app: open DXF, view (pan/zoom), draw line/polyline/rect/circle/arc/text/dimension, layers, snap/ortho, undo/redo, save DXF (R2010 via `cad.py`), export PDF/PNG; chat drawings open in it | DONE: API and real window test PASS | `src/nexvara/cad.py` (DXF read/write, render), `drawing.py`/`drawing_offline.py` (spec), new `app/api_cad.py` + `app/ui/cad.js` |
| B | **Gemini free tier first** so costs stay ~0: «Bepul rejim» — all purposes go to Gemini Flash/Flash-Lite (no Pro), cost recorded as 0, no paid fallback, clear message on 429 (free daily limit), privacy note (free tier data may be used by Google) | DONE by Claude | `ai/router.py`, `ai/models.py`, `appdata.py` defaults, Settings UI (`index.html`, `app.js`) |
| C | Handoff (this section) kept up to date | ongoing | — |
| D | **Professional design**: app icon (Windows .ico + Android adaptive launcher icon), consistent UI icons, polished look | DONE: APK 1.2.2 built and installed | `src/nexvara/app/ui/`, `installer/`, `android/app/src/main/res/` |

Codex completion note (2026-10-18): `cad.js`, `test_cad_api.py`, `cad_page.py`, chat-to-CAD
button, sidebar/CAD toolbar icons, shared brand SVG/Windows icon/Android adaptive icon done.
`test.ps1` PASS (405 passed, 62 Office tests skipped); `test.ps1 -Office` first run
465 passed, 2 Uzbek UI text failures; both fixed and separately rerun PASS (including
real-window Uzbek UI at 100%). Android assembleDebug + unit PASS, version 1.2.2 (code 6)
installed with `adb install -r`. See newest PROGRESS for details. No merge or push.

Historical Claude plan below (its unchecked items were completed by Codex):
- [x] B Gemini free mode — DONE (router `free_active()`, settings `ai.free_mode` default true, UI checkbox + note, chat «bepul rejimni yoq/o‘chir», tests in test_ai_router.py)
- [ ] A CAD page — IN PROGRESS (Claude stopped here, limit). Done and committed as WIP:
  - `src/nexvara/app/api_cad.py` (CadApi, mixed into Api): `cad_open(path)` DXF→JSON
    (`doc_to_json`, explodes blocks, splines→polylines), `cad_save(drawing, path)` JSON→DXF
    (`json_to_doc`, validated, audited, old file backed up), `cad_export(drawing, "pdf"|"png")`,
    `cad_last_drawing()`, `_cad_dialog` (override key `cad_dialog` for tests). JSON format in
    the module docstring (y up, mm, arc angles CCW degrees, dim offset = left of p1→p2).
  - `index.html`: nav item `data-page="cad"` («Chizmalar», i18n `nav.cad`), section
    `#page-cad` (toolbar `data-cad=` actions / `data-tool=` tools, `#cad-canvas`, layers
    `#cad-layers`, props `#cad-props`, command line `#cad-cmd`, status toggles
    `data-toggle=snap|grid|ortho`), `<script src="cad.js">`. Tests updated to 13 nav items.
  - NOT DONE (next steps, in order):
    1. Write `src/nexvara/app/ui/cad.js` (file does not exist yet!) — canvas editor: pan
       (middle drag), wheel zoom at cursor, grid, layers panel, select (click, window L→R /
       crossing R→L), tools line/polyline/rect/circle/arc(center,start,end)/text/dim/move/copy/
       rotate/mirror/offset/measure, erase, undo/redo (JSON snapshots), osnap (end, mid,
       center, quadrant) + grid snap + ortho, AutoCAD-like command line (L, PL, REC, C, A, T,
       DIM, M, CO, RO, MI, O, E, U, Z; input `x,y`, `@dx,dy`, `@len<ang`, plain number =
       distance), keys F3/F7/F8, Esc, Enter/space, Delete, Ctrl+Z/Y/S. Calls `api().cad_open`,
       `cad_save`, `cad_export`, `cad_last_drawing`. Expose `window.cad = {exec, doc, load}` for
       UI tests. Register: add "cad" to `PAGES` in app.js and `if (page === "cad") renderCad();`;
       add `body.cad-mode` (hide right panel) CSS + `.cad-*` styles in app.css.
    2. Unit test `tests/unit/test_cad_api.py`: cad.build(spec) → save DXF → `cad_open` →
       entities by type; `cad_save` round trip (audit clean, counts equal); bad JSON rejected.
    3. UI script `tests/ui_scripts/cad_page.py` (pattern: files_page.py): open page, run
       `cad.exec("L"); cad.exec("0,0"); cad.exec("@100,0")…`, save via override, check DXF.
    4. Chat: after «… chizib ber» offer «Chizmalar’da ochish» (api_drawing result has `dxf`).
    5. Smoke + `.\scripts	est.ps1 -Office`, PROGRESS entry, ROADMAP.
- [ ] D icons/design — NOT STARTED: Windows app icon (.ico for installer/shortcut, sidebar
  logo SVG instead of letter «N»), Android adaptive launcher icon
  (`android/app/src/main/res/mipmap-*`, `drawable/ic_launcher_foreground.xml`), SVG icons on
  nav items and CAD toolbar; keep dark/light themes. Then rebuild APK (1.2.2, versionCode 6)
  with `ANDROID_USER_HOME=.toolsndroid-home` and `adb install -r`.

Rules for this task: tests stay green (`.\scripts\test.ps1`, Office with `-Office`); Uzbek UI
text only (i18n test); phone APK must be built with `ANDROID_USER_HOME=.tools\android-home`
(the project debug key — another key makes the phone refuse the update); install with
`adb install -r` (keeps the user's data). Do not push or merge to `main` without the owner.

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
| 1 | Real AI test with the user's key(s) | Only with the owner's explicit OK (paid). `scripts/ai_live_test.py <provider>` (dry run first; `--run --i-approve` only after OK). OpenAI own limits: $0.25/day, $0.05/task |
| 2 | Real Google login + Drive sync | User creates a *Desktop app* OAuth client, imports JSON in Settings, signs in **themselves**. Never sign in for them. Steps: docs/GOOGLE_LOGIN.md |
| 2b | Second device for OneDrive sync | Nilufar's PC must sync once into `OneDrive\NEXVARA-SYNC` with the same passphrase; then verify both ways |
| 3 | Task history sync | `sync.py` syncs facts, rules, safe settings. History rows hold PC paths; sync titles/status only, mark files as "on <pc>" |
| 4 | BI: slicer list editing via chat | Tools `bi.*` in tools.py; UI in `app/ui/bi.js` (moving widgets between pages and deleting pages are done) |
| 5 | M5: Vision / Web research / Computer control | not started |
| 6 | Code signing (Authenticode) | BLOCKED: needs a certificate |
| 8 | Leftover hidden Office processes | Earlier test runs left windowless `/automation` Excel/PowerPoint instances (see PROGRESS 16). Never force-kill without the user's OK; check `Workbooks.Count` first |
| 7 | Two real PCs / phone sync E2E | needs the user's second device |

## Safety rules that tests enforce — do not weaken

- Personal data is masked locally before any AI request and restored after (`ai/privacy.py`,
  applied in `AiRouter.complete`); unreliable detection blocks the request. Never send user
  text to a provider by another path. Paid fallback is off by default; saving a key does not
  switch AI on.
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

## UI language

All user-visible text is Uzbek (Latin). New strings: add a key to `app/ui/i18n.js` and use
`i18n("key")` in JS or `data-i18n="key"` in HTML. `tests/unit/test_uzbek_ui.py` and
`tests/ui_scripts/uzbek_ui.py` fail on English words (brands, API, file types, model ids allowed).

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
