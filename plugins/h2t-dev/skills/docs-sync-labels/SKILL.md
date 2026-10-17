---
name: docs-sync-labels
description: Sync canonical GitHub labels (from references/standards/labels.json) to all h2t repos via gh CLI. Triggers on "sync labels", "update labels", "apply labels to repos", "docs-sync-labels".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

Sync canonical labels defined in `references/standards/labels.json` to GitHub repos under the `lichtpfad` org using the `gh` CLI.

**Default behaviour:** dry-run (preview only). Use `--apply` to actually write labels.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` and follow it before going on.
   `result.reason` names the case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

The sync is the `h2t-docs-sync-labels` command; the label set it applies ships with it.

## Steps

### 1. Identify target repos

- If the user named specific repos, use those.
- Otherwise the script defaults to all 16 repos from `REPO_MANIFEST` (defined in the package, `h2t_ops/tools/docs/common.py`).

### 2. Dry-run preview

Run without `--apply` to preview every label that would be created/updated:

```bash
h2t-docs-sync-labels                    # all repos
h2t-docs-sync-labels h2t-ai h2t-skills  # specific repos
```

Output shows `label-name (category)` per repo. No GitHub API calls are made.

### 3. Apply

After confirming the dry-run output looks correct, run with `--apply`:

```bash
h2t-docs-sync-labels --apply                    # all repos
h2t-docs-sync-labels h2t-ai h2t-skills --apply  # specific repos
```

The script calls `gh label create --force` for each label. `--force` updates existing labels.
Exit 0 on success; exit 1 if any label failed.

### 4. Confirm

Report count of repos synced and whether any errors occurred.

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `labels.json not found` | The package's bundled standards are missing `labels.json` | Reinstall the CLI, or point `H2T_DEV_ROOT` at your own `docs/standards/` |
| `gh CLI not found` | `gh` not on PATH or wrong path in `docs/common.py` | Install `gh` or fix `GH` constant |
| `FAIL: <label>` per label | GitHub API error (auth, rate-limit, repo not found) | Check `gh auth status`, verify repo name in `lichtpfad` org |
| `h2t-docs-sync-labels: command not found` | The CLI is not installed or not on PATH | Follow the version check at the top of this skill |
