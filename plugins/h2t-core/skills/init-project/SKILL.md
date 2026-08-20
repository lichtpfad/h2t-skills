---
name: init-project
description: Register existing repo or directory in h2t ecosystem. Triggers on "/init-project", "register project", or actionable hint from session-start when project.id == "unknown". NOT for creating new repos (use /h2t-factory:scaffold-project or similar).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

> **Manual project setup?** Use `/h2t-core:scaffold-project` — it handles new repos, existing dirs, and registration in one wizard. This skill (`init-project`) is for **automated** registration triggered by `session-start` when a project is discovered but not yet registered.

Register the current directory as a project in the h2t ecosystem. The PreToolUse hook has already detected the project type, domain, and task tracker.

## Variables

```bash
command -v h2t-project-register >/dev/null 2>&1 || {
  echo "ERROR: h2t-project-register not found. Run /h2t-core:setup"
  exit 1
}
```

## Procedure

### Step 1: Show Detection Result

Look for `INIT_DATA:` in hook output or system messages.

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

### Step 3: Apply Registration

Call `h2t-project-register` with confirmed parameters:

```bash
h2t-project-register \
  --id "{id}" --domain "{domain}" --type "{type}" \
  --label "{label}" --task-tracker "{tracker}" \
  --cwd "$(pwd)" --config-root "$HOME/.h2t/config" \
  [--github "{github}"]
```

Show the result JSON `actions` and `next_steps` to user.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running detection manually | Hook already ran detect_project.py. Use INIT_DATA |
| Writing YAML manually | Call apply_registration.py. It handles backups and comment preservation |
| Skipping domain question when needs_input | User MUST confirm domain before apply |
| Resolving tracker before domain is known | Tracker depends on domain. Wait for domain first |
