---
name: docs-cleanup
description: >
  This skill should be used when the user asks to "archive docs", "cleanup docs",
  "close milestone docs", "archive stale plans", or wants to move implemented specs
  and old plans to archive after a milestone.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# docs-cleanup

Find and archive stale plans and implemented specs in an h2t repo.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
CLEANUP="${CLAUDE_PLUGIN_ROOT}/skills/docs-cleanup/scripts/cleanup.py"
```

## Pipeline

1. Show what would be archived (dry-run):
```bash
$H2T_PYTHON "$CLEANUP" <repo_name>
```

2. Show the output to the user and ask for confirmation.

3. If confirmed, apply with milestone number:
```bash
$H2T_PYTHON "$CLEANUP" <repo_name> --apply --milestone <N>
```

4. Optional: clean artifacts:
```bash
$H2T_PYTHON "$CLEANUP" <repo_name> --apply --milestone <N> --clean-artifacts
```

## Rules

- Never deletes docs — only `git mv` to `docs/archive/`
- Commit message format: `docs: archive M{N} documents`
- Updates `docs/README.md` with archive section after moving
