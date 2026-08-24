---
title: "Retire telegram_cli, record its LLM pipelines for POS"
status: "accepted"
date: "2026-08-24"
---

# Retire telegram_cli, record its LLM pipelines for POS

## Context

`plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` is not a Telegram client. It is an
LLM pipeline that happens to read from Telegram — an early formulation of the POS concept
(capture → summarise → classify), written before POS existed. #383 asked where those workflows
belong.

Measured on `main` at 53c0191 (2026-08-24):

- **It does not run.** `telegram_cli.py --help` exits 1 with
  `ImportError: cannot import name 'genai' from 'google'`. The import is module-level, so every
  subcommand dies, including `auth`, which needs no model at all. `google-genai` is declared
  only in `plugins/h2t/requirements.txt` — the frozen rollback archive — never in
  `pyproject.toml`, so the wheel cannot run it either.
- **It is not a skill, and the reason is traceable.** `plugins/h2t-ops/skills/telegram/`
  contained exactly one file: the script. A `SKILL.md` did exist — it was deleted on 2026-05-23
  in `aa93483 refactor(h2t-ops): consolidate connector skills`, which folded six connector
  SKILL.md files into `h2t-ops:connectors`. The other five had no scripts beside them; this one
  did, and it was left behind. So #383's "copied during wave 2, then never wired up" is not
  quite right: it *was* wired up, and the consolidation unwired it without noticing the script.
- **Nothing references it.** The only mention in the live tree is the ruff `per-file-ignores`
  entry in `pyproject.toml`, added for the script itself. Every other reference — SKILL.md,
  invocation examples, the dependency declaration — lives under `plugins/h2t/`, which holds its
  own 1173-line copy.
- **The live path is elsewhere.** `h2t_ops/connectors/telegram/` covers auth, dialogs and
  messages, and contains zero references to Gemini.
- **#383 undercounts.** It names three workflows. There are **six** LLM pipelines and five
  further commands without one.

`#399` — `_create_notion_tasks` reading an undefined `REPO_ROOT`, silenced by an `F821`
suppression — is a symptom of this, not a separate defect.

## Decision

Delete the live copy and its lint suppression. Record the pipeline mechanics here, so what
survives is the behaviour rather than 1190 lines that cannot execute. The rollback archive
under `plugins/h2t/` keeps the code itself.

The mechanics are to be redeployed on POS, not revived in `h2t-ops`. Tracked in the backlog;
this ADR is the specification that work reads from.

## The six LLM pipelines

Two models throughout: `gemini-2.5-flash-lite` for summarisation, `gemini-2.5-flash` where the
source comments say "нужен reasoning" — extraction into typed records.

| command | source | model | output |
|---|---|---|---|
| `saved` | Saved Messages, ≤200 | flash-lite | `telegram/saved-YYYY-MM-DD.md` |
| `digest` | educational channels, ≤20 posts each | flash-lite | `telegram/digest-YYYY-MM-DD.md` |
| `tasks` | work chats, ≤300 messages | flash | `telegram/tasks-YYYY-MM-DD.md` + Notion |
| `scan-chats` | dialog names, batched | flash-lite | `~/.config/telegram/chats.yaml` |
| `research` | own channels + Saved, ≤300 | flash-lite | `telegram/research-YYYY-MM-DD.md` |
| `students` | student groups | flash | Notion urgent tasks |

Output root: `$DOR_ROOT/context/telegram`, falling back to `~/.dor/output/telegram`.

### 1. `saved` — themed digest of Saved Messages

Input lines are `[date] text URL: urls`, text truncated to 300 chars, ≤3 URLs each. Asks for:
grouping by domain (Art/Digital, Tech/AI, Личное, Разное), a one-line Russian annotation per
item, a `📌 To Read Later` section for deep study, and a `✅ TODO` section for actionable items.
Markdown out, Russian, terse.

### 2. `digest` — per-channel summary

Input is grouped `=== channel ===` blocks, posts truncated to 200 chars. Asks for 3–5 bullets
per channel plus a closing `## 💡 Top 3 insights дня` drawn across all channels.

### 3. `tasks` — typed extraction into JSON

The one that matters most for POS: `response_mime_type="application/json"`, `flash` rather than
`flash-lite`. Input lines are `[chat][sender]: text`. Extracts three types:

- `action_item` — tasks addressed to or taken on by "Я"
- `promise` — promises made to or by me
- `decision` — decisions and agreements

Record shape, with a confidence floor that is part of the contract:

```json
[{"type": "action_item", "text": "...", "from": "...", "chat": "...", "confidence": 0.9}]
```

Rules given to the model: `confidence` 0.0–1.0, include only items ≥ 0.7, `text` is the concrete
formulation, Russian, empty array when nothing qualifies.

### 4. `scan-chats` — five-way classification

Batched. Categories: `work_chat` (colleagues, partners, professional DMs), `student_group`
(learning cohorts, support groups), `own_channel`, `ext_channel` (news, tech, communities),
`noise`. Output is one bare category per line, same order, no explanations.

Worth carrying over: the caller does not trust the format. It takes the last token of each line
(stripping any preamble the model adds), maps anything outside the valid set to `noise`, and
pads short responses. A plain-text classifier without that guard produces silent
misclassification.

### 5. `research` — knowledge curation

Own channels plus Saved, ≤300 items formatted as `[date][source][domain] text`. Grouped by
domain (dev / learning / art / hou2touch / other), each item as
`**[topic]** (tags: …)` plus a 1–2 sentence insight. Language follows the source: Russian in,
Russian out.

### 6. `students` — support triage into typed records

JSON mode, `flash`. Per message: `question`, `urgency` (`urgent` for no-access or payment,
`normal` for technical, `fyi` for feedback), `topic` (`access` / `billing` / `technical` /
`feedback` / `other`), `student`, `group`. Greetings, off-topic and administrative messages are
skipped.

The caller strips a ```` ```json ```` fence before parsing — the model wraps its output despite
`response_mime_type`.

## Consequences

- `pyproject.toml` loses the `telegram_cli.py` entry from `per-file-ignores`; `F821` is then
  live everywhere with nothing suppressed. Closes #399.
- The repo carries no code path that imports `google.genai`. If POS work brings the pipelines
  back, `google-genai` must be declared in `pyproject.toml` and the import guarded, the way
  `drive_cli.py` degrades with a message rather than a traceback.
- `h2t_ops/connectors/telegram` stays the only Telegram surface, and stays LLM-free.
- If the code itself is wanted rather than this description, it is at
  `plugins/h2t/skills/telegram/scripts/telegram_cli.py` — 17 lines behind the deleted copy,
  which had gained `_load_secret_env_files()` in 0f9ab15.
