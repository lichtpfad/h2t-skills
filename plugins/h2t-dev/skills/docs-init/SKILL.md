---
name: docs-init
description: >
  This skill should be used when the user asks to "init docs", "setup docs structure",
  "scaffold documentation", "initialize docs for repo", or wants to create the standard
  docs/ layout in an h2t repo.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# docs-init

Scaffold standard docs/ structure for an h2t repo. Reads projects.yaml for conditional directories.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
INIT="${CLAUDE_PLUGIN_ROOT}/skills/docs-init/scripts/init.py"
```

## Pipeline

1. Run dry-run to show what would be created:
```bash
$H2T_PYTHON "$INIT" <repo_name>
```

2. Show the output to the user and ask for confirmation.

3. If confirmed, apply:
```bash
$H2T_PYTHON "$INIT" <repo_name> --apply --commit
```

## Notes

- All operations are idempotent — safe to run multiple times
- Reads `C:/dev/h2t-landings/projects.yaml` for conditional dirs (if yaml available)
- Default dry-run is safe; `--apply` writes files, `--commit` auto-commits
