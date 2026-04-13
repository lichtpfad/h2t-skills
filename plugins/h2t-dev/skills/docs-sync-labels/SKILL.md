---
name: docs-sync-labels
description: >
  This skill should be used when the user asks to "sync labels", "update github labels",
  "add missing labels", "sync canonical labels", or wants to ensure all h2t repos have
  the standard label set from labels.json.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# docs-sync-labels

Sync canonical GitHub labels from bundled `labels.json` to h2t repos.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
SYNC="${CLAUDE_PLUGIN_ROOT}/skills/docs-sync-labels/scripts/sync_labels.py"
```

## Usage

Dry-run (show what would be synced):
```bash
$H2T_PYTHON "$SYNC" h2t-graphs
```

Sync all repos:
```bash
$H2T_PYTHON "$SYNC" --apply
```

Sync specific repo:
```bash
$H2T_PYTHON "$SYNC" h2t-graphs --apply
```

## Notes

- Uses bundled `data/labels.json` (canonical source, copy of C:/dev/docs/standards/labels.json)
- Only additive sync — never deletes custom labels
- Requires gh CLI authenticated (`gh auth status`)
