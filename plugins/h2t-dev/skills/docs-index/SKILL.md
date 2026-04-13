---
name: h2t-dev:docs-index
description: "This skill should be used when the user asks to \"update docs index\", \"regenerate README\", \"index docs\", \"docs overview\", or wants to rebuild docs/README.md with current ADRs, specs, and reports."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# docs-index

Generate or update `docs/README.md` with a current index of ADRs, specs, plans, and reports.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
INDEX="${CLAUDE_PLUGIN_ROOT}/skills/docs-index/scripts/index.py"
```

## Pipeline

1. Preview what will be generated (dry-run):
```bash
$H2T_PYTHON "$INDEX"
```

2. Show output to user and ask for confirmation.

3. If confirmed, write and commit:
```bash
$H2T_PYTHON "$INDEX" --apply --commit
```

## Notes

- Auto-detects current repo from cwd
- Pass repo name explicitly: `$H2T_PYTHON "$INDEX" h2t-graphs`
- Reads frontmatter for title/status/date if present, falls back to filename
- Overwrites `docs/README.md` — preserves manually added sections under `## Notes` or `## Team`
