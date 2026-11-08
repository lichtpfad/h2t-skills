---
name: docs-sync-labels
description: Sync canonical GitHub labels (from references/standards/labels.json) to all h2t repos via gh CLI. Triggers on "sync labels", "update labels", "apply labels to repos", "docs-sync-labels".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

Sync canonical labels defined in `references/standards/labels.json` to GitHub repos using the `gh` CLI. The owner is never assumed: name `owner/repo`, or set `H2T_GITHUB_OWNER` (or `github.owner` in `user.yaml`) to use bare repo names.

**Default behaviour:** dry-run (preview only). Use `--apply` to actually write labels.

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

The sync is the `h2t-docs-sync-labels` command; the label set it applies ships with it.

## Steps

### 1. Identify target repos

- If the user named specific repos, use those as `owner/repo`. A bare name needs `github.owner`; without it the command exits 3 and names the setting.
- Otherwise the script defaults to the repos in your repo mapping, as bare names under `github.owner`. An empty mapping exits 3: register repos, or pass `owner/repo`.

### 2. Dry-run preview

Run without `--apply` to preview every label that would be created/updated:

```bash
h2t-docs-sync-labels                          # the repos in your repo mapping
h2t-docs-sync-labels <owner>/<repo> <owner>/<repo>  # specific repos
```

Output shows `label-name (category)` per repo. No GitHub API calls are made.

### 3. Apply

After confirming the dry-run output looks correct, run with `--apply`:

```bash
h2t-docs-sync-labels --apply                          # the repos in your repo mapping
h2t-docs-sync-labels <owner>/<repo> <owner>/<repo> --apply  # specific repos
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
| `FAIL: <label>` per label | GitHub API error (auth, rate-limit, repo not found) | Check `gh auth status`, verify the `owner/repo` you passed |
| `h2t-docs-sync-labels: command not found` | The CLI is not installed or not on PATH | Follow the version check at the top of this skill |
