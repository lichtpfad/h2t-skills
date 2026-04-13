---
name: h2t-dev:docs-lint
description: "This skill should be used when the user asks to \"check docs\", \"lint documentation\", \"verify standards\", \"docs compliance\", \"are docs up to standard\", or wants to audit documentation structure and frontmatter across h2t repos."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# docs-lint

Run documentation standards compliance check across h2t repos.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
```

## Usage

Check current repo (auto-detected from cwd):
```bash
$H2T_PYTHON "$LINT"
```

Check specific repo(s):
```bash
$H2T_PYTHON "$LINT" h2t-graphs h2t-skills
```

Check all 16 repos:
```bash
$H2T_PYTHON "$LINT" --all
```

Fix missing dirs:
```bash
$H2T_PYTHON "$LINT" --fix h2t-graphs
```

Fix missing frontmatter (auto-generates from heading/filename/git):
```bash
$H2T_PYTHON "$LINT" --fix-frontmatter
```

Skip pymarkdownlnt:
```bash
$H2T_PYTHON "$LINT" --no-pymarkdown h2t-graphs
```

## Output

Show the full lint output to the user. If there are failures, summarize what needs fixing and suggest the `--fix` flag for missing dirs.
