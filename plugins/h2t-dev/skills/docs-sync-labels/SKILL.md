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

## Variables

```bash
RUN="uv run --no-project python"

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    _DEV_ROOT="$CLAUDE_PLUGIN_ROOT"
else
    _DEV_ROOT=$(ls -dt "$HOME/.claude/plugins/cache/lichtpfad/h2t-dev"/[0-9]* 2>/dev/null | head -1)
fi
SYNC_LABELS="$_DEV_ROOT/skills/docs-sync-labels/scripts/sync_labels.py"
```

## Steps

### 1. Identify target repos

- If the user named specific repos, use those.
- Otherwise the script defaults to all 16 repos from `REPO_MANIFEST` (defined in `lib/docs/common.py`).

### 2. Dry-run preview

Run without `--apply` to preview every label that would be created/updated:

```bash
$RUN "$SYNC_LABELS"                    # all repos
$RUN "$SYNC_LABELS" h2t-ai h2t-skills  # specific repos
```

Output shows `label-name (category)` per repo. No GitHub API calls are made.

### 3. Apply

After confirming the dry-run output looks correct, run with `--apply`:

```bash
$RUN "$SYNC_LABELS" --apply                    # all repos
$RUN "$SYNC_LABELS" h2t-ai h2t-skills --apply  # specific repos
```

The script calls `gh label create --force` for each label. `--force` updates existing labels.
Exit 0 on success; exit 1 if any label failed.

### 4. Confirm

Report count of repos synced and whether any errors occurred.

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `labels.json not found` | Bundled `references/standards/labels.json` missing | Restore it from the plugin, or point `H2T_DEV_ROOT` at your own `docs/standards/` |
| `gh CLI not found` | `gh` not on PATH or wrong path in `docs/common.py` | Install `gh` or fix `GH` constant |
| `FAIL: <label>` per label | GitHub API error (auth, rate-limit, repo not found) | Check `gh auth status`, verify repo name in `lichtpfad` org |
| Script import error | `lib/docs/common.py` not found | Run from within the plugin cache or set `CLAUDE_PLUGIN_ROOT` |
