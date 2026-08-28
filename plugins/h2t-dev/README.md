# h2t-dev Plugin

Documentation and tooling skills for h2t platform. Includes standards compliance, repo scaffolding, cleanup, and label synchronization.

## Documentation Skills

| Skill | Purpose | Key args |
|-------|---------|----------|
| `docs-lint` | Check docs standards compliance | `[repo...]`, `--fix`, `--no-pymarkdown` |
| `docs-sync-labels` | Sync canonical GitHub labels | `[repo...]`, `--apply` |

All skills default to **dry-run** — safe to run anytime. Pass `--apply` to make real changes.

### docs-lint

Checks all 16 h2t repos for:
- Required dirs (`docs/superpowers/specs`, `docs/superpowers/plans`, `docs/adr`, `docs/reports`)
- Required files (`.pymarkdown.yaml`, `.vale.ini`, `.claude/rules/documentation.md`)
- Frontmatter validity (specs require `title`, `status`, `owner`, `date`)
- ADR naming (4-digit prefix)
- `projects.yaml` flag cross-checks

**Usage:**
```bash
docs-lint audit --root .           # Show docs health findings
docs-lint plan --root .            # Show cleanup plan
docs-lint fix-safe --root .        # Apply safe mechanical fixes only
docs-lint fix-index --root .       # Dry-run README/navigation rebuild
docs-lint doctor --root . --json   # Machine-readable report
```

### docs-init — not a command, and not a skill

`scripts/docs-init/init.py` scaffolds the standard `docs/` structure and reads
`projects.yaml` for conditional directories. It has no entry point of its own and no
`SKILL.md`: `bc335d8` demoted it out of `skills/` deliberately, absorbing it into
`h2t-core:scaffold-project`, which calls it directly.

The only supported way in is creating a project:

```
/h2t-core:scaffold-project
```

This README documented `docs-init <repo> --apply` as a command for four months after that
demotion. There was never such a command — not in `[project.scripts]`, not on PATH (#458).


### docs-sync-labels

Syncs 18 canonical labels (type, priority, domain, status) from bundled `labels.json` to GitHub repos.
Only additive — never deletes custom labels.

**Usage:**
```bash
docs-sync-labels                    # Dry-run on all repos
docs-sync-labels h2t-graphs h2t-ai # Check specific repos
docs-sync-labels h2t-graphs --apply # Create missing labels
```

## Other Skills

- **github-issues** — Create and update issues
- **milestone-closure** — Close GitHub milestones with closure.py backend; uses docs-lint plan before cleanup decisions and docs-lint fix-index after approved cleanup. Standalone docs-index is deprecated as a user-facing flow.
- **pre-merge-check** — Validate PR readiness
