---
name: h2t-dev:docs-lint
description: >-
  Use when checking docs compliance, linting documentation, verifying standards,
  or auditing documentation structure and navigation across h2t repos.
  Modes: audit (default), plan, fix-safe, fix-index, doctor --json.
  Use --root PATH for repos outside C:/dev (e.g. C:/work/rejuve).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# docs-lint

Run documentation health check across h2t repos.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
```

## Modes

Check is ordered: navigation → naming → structure → metadata.
**Do not stop after frontmatter issues** if navigation or naming findings exist.

### audit (default): show all findings

```bash
# Current repo (auto-detect from cwd):
$H2T_PYTHON "$LINT" audit

# Explicit path (for repos outside C:/dev):
$H2T_PYTHON "$LINT" audit --root C:/work/rejuve

# Named repo:
$H2T_PYTHON "$LINT" audit --root C:/dev/h2t-skills
```

### plan: human-readable cleanup plan

```bash
$H2T_PYTHON "$LINT" plan --root C:/work/rejuve
```

No writes. Shows orphans, naming fixes, structure issues in priority order.

### fix-safe: apply only safe mechanical fixes

```bash
# All safe fixes (create missing dirs, add missing frontmatter):
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve

# Frontmatter only:
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve --only frontmatter

# Dirs only:
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve --only dirs
```

**Safe = create dirs, add frontmatter. NOT safe = rename, move, delete, rewrite README.**

### fix-index: rebuild docs/README.md navigation

```bash
# Dry run (always run first):
$H2T_PYTHON "$LINT" fix-index --root C:/work/rejuve

# Apply (writes README.md atomically):
$H2T_PYTHON "$LINT" fix-index --root C:/work/rejuve --apply
```

Uses `<!-- h2t-index-start -->` / `<!-- h2t-index-end -->` markers.
First run on README without markers appends section (dry-run) — requires `--apply` to write.
Manual content outside markers is preserved.

### doctor --json: machine-readable report

```bash
$H2T_PYTHON "$LINT" doctor --root C:/work/rejuve --json
```

Outputs `h2t_lifecycle_report/v0.1` JSON to stdout.
Use for hooks, CI, and agent pipelines.

## Legacy Multi-Repo Mode (still works)

```bash
# Check specific repos:
$H2T_PYTHON "$LINT" h2t-graphs h2t-skills

# Check all repos:
$H2T_PYTHON "$LINT" --all

# Fix missing dirs (deprecated → use fix-safe):
$H2T_PYTHON "$LINT" --fix h2t-graphs   # emits deprecation warning
```

## Hook Usage

```bash
# In hooks — must complete within H2T_LINT_HOOK_TIMEOUT (default 8s):
H2T_LINT_HOOK_TIMEOUT=8 $H2T_PYTHON "$LINT" doctor --root . --json > .h2t-lint-cache.json
```

## Output

Show full output to user. If findings > 0:
1. Report navigation/orphan findings first
2. Then naming issues with proposed renames
3. Then structure issues
4. Frontmatter issues last
5. Suggest `fix-safe` for auto-fixable items

**Do not suggest renaming or moving files in `fix-safe` — those require plan + user confirmation.**

## References

Load on demand when needed:

- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/naming-conventions.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md`
