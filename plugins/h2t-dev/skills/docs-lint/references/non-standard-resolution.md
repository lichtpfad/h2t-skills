# Non-Standard Path Resolution Reference

Use when evaluating dirs/files not in the standard project template (Dimension 8).

---

## Decision Tree

```
Found non-standard path
        │
        ▼
   Needed? (git activity last 30d + content size)
   git log --oneline --since="30 days ago" -- <path>
       / \
     Yes   No → DELETE (confirm; skip for archived stage)
     │
     ▼
  Covered by standard template for detected project_type?
      / \
    Yes   No
    │          │
    ▼          ▼
 Misplaced   Project-specific?
 → MOVE          / \
   (pre-checks) Yes   No → ADD PROJECT TYPE (PR proposal)
                │
                ▼
           EXCEPTION → .h2t/docs-lint.yaml
```

---

## MOVE pre-checks

Before confirming any `git mv`:

```bash
# 1. Reference search
grep -r "<path>" . --include="*.py" --include="*.md" -l 2>/dev/null | head -20

# 2. Generated file check
git check-ignore -v "<path>" 2>/dev/null

# 3. Symlink check
test -L "<path>" && echo "SYMLINK — do not git mv"

# 4. Submodule check
git submodule status 2>/dev/null | grep "<path>"
```

Only proceed after user confirms and all checks pass.

---

## EXCEPTION format

Write to `.h2t/docs-lint.yaml`:

```yaml
exceptions:
  - path: benchmark_results/
    reason: "TD perf data, updated live"
    type: operational_data   # operational_data|archive|generated|tool_output|external
    reviewed: 2026-06-06     # today's date — re-confirm every 90 days
```

---

## ADD PROJECT TYPE

1. Document the pattern in the conversation
2. Propose extension to `plugins/h2t-dev/lib/docs/project_types.py`
3. Open GitHub issue: `skills: add project type <name>` with label `type:feature`
4. Do NOT edit `project_types.py` directly — requires PR + review

---

## Project type autodetect precedence

1. `.h2t/docs-lint.yaml` `project_type` field
2. `CLAUDE.md` first 50 lines — keyword scan
3. `pyproject.toml` + `plugins/` dir → `plugin-pack`
4. `pyproject.toml` without `plugins/` → `standalone-tool`
5. `package.json` → `frontend-tool`
6. Default → `unknown`
```
