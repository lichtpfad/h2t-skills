---
name: handoff
description: This skill should be used when the user says "handoff", "завершить сессию", "конец сессии", "wrap up", "закончим", "сохрани сессию", or asks to close/end the current working session. Reconstructs what was done and what remains from conversation context and git history, shows summary, then writes the session record immediately — it never asks for a session name or any other confirmation before writing.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.1.5
---

# Handoff v3.1

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Setup

```bash
command -v h2t-handoff >/dev/null 2>&1 || {
  echo "ERROR: h2t-handoff not found. Act on outcome 3 of the Version check above."
  exit 1
}
```

## Pipeline

### Step 1: Establish session context

⛔ Ask the user nothing until the record is written (Step 6). Handoff runs when the session
is ending and the user is often already gone; a question here costs the whole record, while
a wrong name costs one rename. Resolve every value yourself:

- `SESSION_NAME` — the name confirmed in session-start, if it ran this session. Otherwise
  derive `{domain}-{project}-{topic}-YYYY-MM-DD` on your own, with `{topic}` a 1–2 word
  kebab-case summary of the dominant work. Do not offer it for approval; write with it.
- `DOMAIN`, `PROJECT_ID` — `project.domain` and `project.id` of a gather result for this
  directory. The PreToolUse hook injects a `BRIEFING:` / `GATHER_META:` block when this
  skill starts; **use it only if** its `GATHER_META` JSON has `cwd` equal to the current
  working directory and `at` no more than 120 s before now (`pwd; date +%Y-%m-%dT%H:%M:%S%z`).
  Otherwise — no block, a stale one, one for another directory, or Codex, which runs no
  hooks — run it yourself and read the same two fields from its `GATHER_META` line:

  ```bash
  h2t-gather --cwd "$(pwd)" --skill handoff --briefing-only
  ```

  If gather fails, **omit both flags** in Step 6 rather than substituting the repo name:
  the writer resolves them from the working directory through the same
  `identify_project()` the reader uses. A guessed name lands the record in a directory no
  session-start looks in.

### Step 2: Auto-generate what was done

DO NOT ask the user. Reconstruct from:
1. Conversation history — what was implemented, fixed, discussed
2. `git log --oneline -20` for current repo — recent commits this session
3. Files created or modified visible in context

Write 3–7 bullet points in Russian. Be specific: what changed, not process.
Store as WHAT_DONE.

### Step 3: Auto-generate what remains

DO NOT ask the user. Infer from:
1. Open issues mentioned in this conversation
2. TODOs or next steps discussed but not completed
3. Known blockers or pending decisions from conversation
4. **Pull open P0/blocker issues from GitHub** (run silently, merge with above):

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's|.*github\.com[:/]\(.*\)\.git$|\1|;s|.*github\.com[:/]\(.*\)$|\1|')
gh issue list --repo "$REPO" --label "priority:p0" --state open --json number,title --limit 20 2>/dev/null
gh issue list --repo "$REPO" --label "status:blocked" --state open --json number,title --limit 20 2>/dev/null
```

If `gh` is unavailable, auth fails, or the repo cannot be resolved — skip silently without error.
Add any issues not already covered by items 1–3 as additional checkboxes: `- [ ] #N — <title>`.
Optionally also include `priority:p1` issues if the milestone context makes them relevant.

Write 2–5 items as **checkboxes** (`- [ ] ...`). If nothing clear — write `- [ ] Нет явных следующих шагов.`
Store as WHAT_REMAINS.

### Step 4: Collect artifacts

Build ARTIFACT_LIST from session context:
- Commits: `commit:{sha7}`
- Issues closed: `issue:{number}`
- Files created: `file:{path}`
- PRs opened: `pr:{number}`

### Step 4a: Active autonomous-run runbook (resume pointer)

If an autonomous-run is in progress, record its resume pointer so the next session can
auto-resume across compaction (spec `autonomous-run` § Resume trigger, mechanism-1). Detect:
the newest `docs/superpowers/plans/*-runbook.md` whose pipeline still has an unchecked step
(an `- [ ] **step**` line — bold unchecked checkboxes appear only in `## Pipeline steps`):

```bash
_RB=$(ls -t docs/superpowers/plans/*-runbook.md 2>/dev/null | head -1)
[ -n "$_RB" ] && grep -q '^- \[ \] \*\*' "$_RB" && echo "ACTIVE_RUNBOOK: $_RB"
```

If it prints `ACTIVE_RUNBOOK: <path>`, the run is unfinished:
- add to ARTIFACT_LIST: `runbook:{path}`
- add to WHAT_REMAINS a checkbox: `- [ ] Автономный прогон не завершён → autonomous-run resume {path}`

If there is no runbook or nothing prints, skip silently.

### Step 4b: Rule promotion scan

Scan for agent behavioral rules discovered this session. These become candidates for `.claude/rules/` (current project only — no global CLAUDE.md writes).

**What counts as a rule candidate:**
- User corrections about agent behavior: "не делай", "стоп", "не используй X", repeated 1+ times
- Explicit protocol agreements: "договорились", "принято", "запомни", "всегда", "никогда"
- Behavioral feedback crystallized into a pattern (same issue corrected ≥2 times)
- Explicit rule statements: "правило:", "протокол:", "важно:" followed by actionable text

**What does NOT count:** project architecture/tech decisions (→ ADR), one-off requests, business logic.

**JSONL scan** — catches rules from compacted early-session context (grep-only, no full dump):

```bash
h2t-handoff rule-scan --json
```

It reads the newest transcript of this directory under `~/.claude/projects/` and returns
`{"ok": true, "transcript", "scanned", "hits"}` — `hits` are user messages (first 200
characters) that carry a rule trigger.

A missing transcript is `"ok": false` with `error.message` `no transcript found in <dir>` (exit 5)
— report it, do not read it as "no rules". `scanned 0` means the scan saw nothing, not that
the session had no rules. Neither stops the handoff: the record is written either way.

Cross-reference against existing `.claude/rules/*.md` — skip rules already captured there.

For each candidate, record:
- Concise rule text (1–2 sentences, imperative)
- Target file: existing file to append to, or new `{category}.md` to create
- Action: `append` | `create`

Store as RULE_CANDIDATES. If nothing found → empty list (skip Steps 6b–6c entirely).

### Step 5: Show summary + write immediately

Display summary (no confirmation gate — write immediately after showing).
**Follow the format from `references/handoff-example.md` exactly** — use `##` for session name, `###` for sections, bullet list for "Что сделано", checkboxes (`- [ ]`) for "Что передаём", dash list for "Артефакты".

```
## Handoff: {SESSION_NAME}

### Что сделано
{WHAT_DONE}

### Что передаём в следующую сессию
{WHAT_REMAINS}

### Артефакты
{ARTIFACT_LIST}
```

Proceed immediately to Step 6 — do NOT ask for confirmation.

### Step 6: Write handoff

Writer stores:
- full archival markdown as `<machine>/<project>/<session_id>.md` under
  `h2t-ops paths get records.sessions`;
- that markdown is the latest record too: `session-start` finds it through the index,
  so no separate summary file is written;
- one line in this machine's activity record (`h2t-ops paths get records.activity`).

```bash
h2t-handoff write \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>" \
  --what-done "<WHAT_DONE>" \
  --what-remains "<WHAT_REMAINS>" \
  --artifacts <ARTIFACT_LIST>
```

Replace all `<...>` with literal values (not shell variables).

Then show the `markdown` path the writer returned, on one line, so a derived name can be corrected later:
`Записано: <path>` — переименовать при необходимости.

### Step 6b: Rule promotion gate

Skip this step if RULE_CANDIDATES is empty.

Show each candidate with exact content and target:

```
### Rule Promotion — {N} кандидатов

**1.** Не использовать `&&` в Bash tool calls  
   → append `.claude/rules/bash.md`

**2.** Всегда использовать `git mv`, не `mv`  
   → create `.claude/rules/git.md`

[ADR-кандидат] Перейти на PostgreSQL — не rule, отложить как ADR

Подтвердить: `all` / `1,2` / `none` — или исправьте текст кандидата
```

⛔ GATE — wait for user selection before writing any rules.

### Step 6c: Write confirmed rules

For each confirmed rule:
1. Read target file if it exists — check the rule is not already there (skip duplicates).
2. If file exists: append `\n{rule_text}\n` after the last line.
3. If file does not exist: create with header `# {Category} Rules\n\n{rule_text}\n`.
4. Use Edit/Write tools to make changes; do NOT use shell redirection.

### Step 7: Confirm

```
✓ Сессия <SESSION_NAME> сохранена
✓ Activity stream: {spool_path}
✓ Запись: {markdown_path}
✓ Артефактов: {N}
✓ Правил промотировано: {M} (или "Правил не промотировано" если 0)
```

`{N}` — поле `artifacts` из ответа писателя: число записанных артефактов.
