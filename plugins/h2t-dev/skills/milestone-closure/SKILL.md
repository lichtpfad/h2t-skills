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
`skills/milestone-closure/scripts/closure.py`.

## Variables

```bash
RUN="uv run --no-project --with pyyaml python"
CLOSURE="$(h2t-dev root)/skills/milestone-closure/scripts/closure.py"
```

## Procedure

### Step 1: Identify milestone

Ask the user for the milestone title or GitHub milestone API number if it is not
already explicit.

### Step 2: Dry-run closure report

```bash
$RUN "$CLOSURE" --repo-root "$(pwd)" --milestone "{milestone}" --json
```

Read the JSON:

- If `status == "blocked"`: show open-issue count and stop.
- If `status == "error"`: show error and stop.
- If `docs_lint.status != "ok"`: summarize docs-lint plan and ask what to do.

### Step 3: Documentation gate

Run docs cleanup manually through unified docs-lint:

```bash
$RUN "$(h2t-dev root)/skills/docs-lint/scripts/lint.py" plan --root "$(pwd)"
$RUN "$(h2t-dev root)/skills/docs-lint/scripts/lint.py" fix-index --root "$(pwd)"
```

`fix-index` without `--apply` is dry-run. Ask before using `--apply`.

Do not call standalone `docs-index`. It is no longer user-facing.
Do not archive, move, delete, or rename files without explicit user approval.

### Step 4: Close milestone only with confirmation

Ask the user to confirm the exact milestone title.

```bash
$RUN "$CLOSURE" --repo-root "$(pwd)" --milestone "{milestone}" --close --confirm-title "{exact title}" --json
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
