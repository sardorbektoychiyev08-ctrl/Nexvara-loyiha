# Core Agent: how a chat message becomes work

```
message
  │ API-key guard: a pasted key is refused and never stored (app/api_agent.py)
  │ memory aliases: "hisobot papkam" → «D:\Ish\Hisobotlar» (facts that contain a path)
  ▼
Api._chat_inner (app/api.py)
  1. section commands      memory recall, task history, devices, theme   (app/api_sections.py)
  2. Teach NEXVARA         "Eslab qol: …", "Har doim …" → confirm → store  (memory/teach.py)
  3. references            "uni PDF qil" → the file the last step produced (Context)
  4. Core Agent            (app/api_agent.py)
       • "xuddi shunday X bilan ham qil" → repeat the last Office command
       • several tasks? (agent/nlu.split_chain) → one chain task, steps in order
       • offline rules (agent/nlu.parse) → ToolCalls → validate → confirm risky → run
  5. older handlers        BI from a file, file search, Office command, test, topic, slides
  6. AI planner (optional) only if 1–5 did not understand and the user enabled AI:
       ai/features.plan: tool catalog + context + last turns + facts + Teach rules →
       {"kind": "tools", "calls": [...]} → the same validate/confirm/run path
```

AI-first routing (every message → planner first): see docs/AI.md «Avval AI».

## Tools (agent/tools.py)

Every section's actions are registered once with a typed parameter list and a `risky` flag:

| Section | Tools |
|---|---|
| Files | `files.search`, `info`, `copy`, `move`, `rename`, `rename_batch`, `zip`, `unzip`, `backup`, `versions`, `restore`⚠, `tidy`⚠, `recycle`⚠, `pdf` |
| NEXVARA BI | `bi.create`, `list`, `open`, `summary`, `export` (xlsx/csv here; pdf/png drawn by the page), `add_step` (calc, join, append, filter, rename, drop_col, fill_null, drop_null, dedupe, drop_empty, set_type), `steps`, `remove_step`, `widgets`, `add_widget`, `edit_widget`, `remove_widget`, `move_widget`, `add_page`, `delete_page`⚠, `rename`, `delete`⚠ |
| Workflows | `workflow.list`, `create` (steps, daily time, watched folder, retries, on_error), `run`, `pause`, `resume`, `approve`, `stop`, `enable`, `history`, `delete`⚠ |
| Settings | `settings.show`, `settings.set` (whitelist; never API keys), `settings.update_check`, `sync.now` |
| Everything else | `nexvara.command` → the offline pipeline (Office, tests, topics, slides, memory, Teach) |

⚠ = asks "Davom etaymi?" first. A plan from the AI planner that changes anything (any tool
outside `tools.READ_ONLY`) is always shown first and runs only after "Ha". `validate()` drops unknown parameters, checks types and
required values; unknown tools are refused. Paths are resolved by the tool (never trusted
from the AI): named files, folders this conversation used, memory aliases, special folders
("ish stoli", "hujjatlar", "yuklanmalar"); copies/moves never overwrite.

## Conversation context (agent/context.py)

`file` ("shu fayl"), `result` ("uni", "natijani" — the last output), `files` ("topilgan
fayllar"), `folder`, `dashboard`, `workflow`, the last Office `command`, recent folders and
the last 12 turns (sent to the AI planner). Every finished task updates `result`.

## Chains

`split_chain` splits on "keyin", "so‘ng", "undan keyin", ";", new lines and "1) 2)", but keeps
Office clauses about the same file together ("och, keyin saralab, PDF qil" stays one command).
The chain is one task; each step waits for the previous one; a failed step stops the chain.
If any step is risky, the whole list is shown and confirmed first.

## Memory ↔ Teach ↔ Office

- Facts with a path become aliases usable in any command (Files, BI, Office).
- "Shu faylni eslab qol: …" stores the real path.
- Teach rules are applied to every Office command (also inside chains and workflows) and are
  listed to the AI planner; relevant facts are sent too (only matching ones).

## Why JSON tool calls, not each provider's native tool API

One format for Anthropic, OpenAI, Gemini and DeepSeek, testable with a fake provider, and the
model never executes anything: it only proposes calls that go through the same checks as a
button. Planner calls use the cheap tier and the normal budget/confirmation rules.
