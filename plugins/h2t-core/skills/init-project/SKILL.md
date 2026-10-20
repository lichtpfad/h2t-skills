---
name: init-project
description: Register existing repo or directory in h2t ecosystem. Triggers on "/init-project", "register project", or actionable hint from session-start when project.id == "unknown". NOT for creating new repos (use /h2t-factory:scaffold-project or similar).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.2.0
---

# Instructions

> **Manual project setup?** Use `/h2t-core:scaffold-project` — it handles new repos, existing dirs, and registration in one wizard. This skill (`init-project`) is for **automated** registration triggered by `session-start` when a project is discovered but not yet registered.

Register the current directory as a project in the h2t ecosystem. The PreToolUse hook has already detected the project type, domain, and task tracker.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect 4.0.0 --json
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
   it there is no install: give the user `uvx --isolated --python 3.12.11 --managed-python -c "https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt" --from "h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl" h2t-setup sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `uvx --isolated --python 3.12.11 --managed-python -c "https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt" --from "h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl" h2t-setup sync`.
<!-- version-check:end -->

## Variables

```bash
command -v h2t-project-register >/dev/null 2>&1 || {
  echo "ERROR: h2t-project-register not found. Run /h2t-core:setup"
  exit 1
}
```

## Procedure

### Step 1: Show Detection Result

Look for `INIT_DATA:` in hook output or system messages. **Use it only if** its JSON has
`cwd` equal to the current working directory and `at` (ISO-8601 with offset) no more than
120 s before now:

```bash
pwd; date +%Y-%m-%dT%H:%M:%S%z
```

Otherwise — no `INIT_DATA`, a stale one, one for another directory, one without
`cwd`/`at` (a 3.x hook), or Codex, which runs no hooks — detect it yourself. The command
prints the same JSON the hook injects, without the `INIT_DATA:` prefix:

```bash
h2t-detect-project --cwd "$(pwd)"
```

If it contains `"error":` — show the error and stop.
If it contains `"already_registered": true` — show confirm_message, ask if user wants to update. If no → stop.

**Show confirm_message VERBATIM.** Do not modify or supplement.

### Step 2: Collect Missing Input

If `needs_input` is true:
- Show confirm_message (it already contains the question)
- Collect user's answer for each field in `input_fields`
- If `domain` was collected and `tracker_confidence` == `"deferred"`:
  - Check if the chosen domain is `hou2touch` (has Notion) AND `detected.github` exists → ask: "GitHub и Notion оба доступны. Task tracker: github или notion?"
  - Otherwise resolve automatically: github if `detected.github`, else none

If `needs_input` is false — wait for "ок" or corrections from user.

Always collect a one-line `description` as well, unless the user declines. It is what
LLM task classification reads out of `domains.yaml`; a project registered without one
sorts worse from then on. Propose one from the repo's README or its issues rather than
asking cold.

### Step 3: Apply Registration

Call `h2t-project-register` with confirmed parameters:

```bash
h2t-project-register \
  --id "{id}" --domain "{domain}" --type "{type}" \
  --label "{label}" --task-tracker "{tracker}" \
  --description "{description}" \
  --cwd "$(pwd)" \
  [--github "{github}"]
```

`--description` fills a blank field only; a description already written by hand is kept.

Show the result JSON `actions` and `next_steps` to user.

### Step 4: Truth Gate (mandatory, also on re-run)

Load `references/truth-gate.md` (next to this file) and follow it: three questions, each
answered by a command that is run, empty output = red, result written into the project
`CLAUDE.md` under `## Truth gate`. If the heading already exists — re-run the commands and
update statuses; do not skip because "already answered".

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running detection when fresh INIT_DATA is there | The hook already ran it. Use INIT_DATA; run `h2t-detect-project` only when the freshness rule in Step 1 fails |
| Treating a missing INIT_DATA as normal | In Claude Code the hook is the executor by design (#12): a missing INIT_DATA means the hook failed — say so, then detect with `h2t-detect-project`. Only Codex has no hook |
| Writing YAML manually | Call `h2t-project-register`. It handles backups and comment preservation |
| Skipping domain question when needs_input | User MUST confirm domain before apply |
| Resolving tracker before domain is known | Tracker depends on domain. Wait for domain first |
| Ending after registration | Step 4 (truth gate) is part of this skill. Registration without the gate is the audit's root finding: flag says done, content missing |
