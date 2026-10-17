---
name: milestone-closure
description: This skill should be used when all issues in a GitHub milestone are closed and the phase is complete. Triggers on "close milestone", "milestone done", "phase complete", "закрыть milestone", or when the last issue in a milestone is closed.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Milestone Closure

Close a GitHub milestone as a Lifecycle OS phase boundary.

This skill is a thin orchestrator. Deterministic state is gathered by
`h2t-milestone-closure`.

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
   `reason: path` it is a command for the user to decide on. `result.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Procedure

### Step 1: Identify milestone

Ask the user for the milestone title or GitHub milestone API number if it is not
already explicit.

### Step 2: Dry-run closure report

```bash
h2t-milestone-closure --repo-root "$(pwd)" --milestone "{milestone}" --json
```

Read the JSON:

- If `status == "blocked"`: show open-issue count and stop.
- If `status == "error"`: show error and stop.
- If `docs_lint.status != "ok"`: summarize docs-lint plan and ask what to do.

### Step 3: Documentation gate

Run docs cleanup manually through unified docs-lint:

```bash
h2t-docs-lint plan --root "$(pwd)" --json
h2t-docs-lint fix-index --root "$(pwd)"
```

`fix-index` without `--apply` is dry-run. Ask before using `--apply`.

Do not call standalone `docs-index`. It is no longer user-facing.
Do not archive, move, delete, or rename files without explicit user approval.

### Step 4: Close milestone only with confirmation

Ask the user to confirm the exact milestone title.

```bash
h2t-milestone-closure --repo-root "$(pwd)" --milestone "{milestone}" --close --confirm-title "{exact title}" --json
```

If `status == "partial"`: the GitHub API PATCH failed — show `close_result.stderr` from the report and stop. Do not treat partial as success.

### Step 5: Report outcome

Show:

- report JSON path from `refs`;
- milestone status;
- docs-lint summary;
- `next_open_items` from real GitHub state if available.

## Checklist

- [ ] Dry-run closure report generated
- [ ] Open issue count is zero or explicitly handled
- [ ] docs-lint plan reviewed
- [ ] docs-lint fix-index dry-run reviewed
- [ ] Any write/destructive step explicitly confirmed
- [ ] GitHub milestone closed only after exact-title confirmation
- [ ] Next open items reviewed from closure report
