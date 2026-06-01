# h2t-dev Plugin

Documentation and tooling skills for h2t platform. Includes standards compliance, repo scaffolding, cleanup, and label synchronization.

## Documentation Skills

| Skill | Purpose | Key args |
|-------|---------|----------|
| `docs-lint` | Check docs standards compliance | `[repo...]`, `--fix`, `--no-pymarkdown` |
| `docs-init` | Scaffold docs/ structure | `<repo>`, `--apply`, `--commit` |
| `docs-cleanup` | Archive stale plans and implemented specs | `[repo]`, `--apply`, `--milestone N` |
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

### docs-init

Scaffolds standard docs/ structure in a repo. Reads `projects.yaml` for conditional dirs.
Always idempotent — skips existing files.

**Usage:**
```bash
docs-init h2t-graphs        # Dry-run scaffold
docs-init h2t-graphs --apply # Create dirs and files
docs-init h2t-graphs --commit # Apply + commit
```

### docs-cleanup

After milestone closure: finds plans >30 days old and specs with `status: implemented`,
archives them via `git mv` to `docs/archive/`. Commit message: `docs: archive M{N} documents`.

**Usage:**
```bash
docs-cleanup                    # Dry-run on all repos
docs-cleanup h2t-graphs         # Dry-run on specific repo
docs-cleanup h2t-graphs --apply # Move files and stage
docs-cleanup --milestone 5      # Archive only M5 docs
```

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

- **gh-memory** — GitHub Issues persistent memory
- **github-issues** — Create and update issues
- **milestone-closure** — Close GitHub milestones with closure.py backend; uses docs-lint plan before cleanup decisions and docs-lint fix-index after approved cleanup. Standalone docs-index is deprecated as a user-facing flow.
- **pre-merge-check** — Validate PR readiness
