# Documentation Rules

Full standards: C:/dev/docs/standards/ (read before creating docs, issues, ADRs).

## Critical Inline Rules

### Rules Language (MUST follow)
`.claude/rules/*.md` are written in English — the rule text, its examples, and its rationale.
Agents read these files verbatim; a mixed-language rule set makes them harder to quote,
diff, and share across repos.

### Issue Titles (MUST follow)
Format: `{repo-short}: [MN] verb noun`
- repo-short = repo name without `h2t-` prefix (e.g., `graphs`, `ai`, `transcription`)
- [MN] = milestone tag (e.g., [M3], [v0.6]) — required if issue has a milestone
- Imperative mood: Add, Fix, Refactor (not Added, Fixes)
- Example: `graphs: [v0.6] Add health check endpoint`
- Backlog (no milestone): `graphs: Fix typo in README`

### Commit Messages
Format: `<type>: <description>` (feat, fix, docs, refactor, test, chore, perf)

### ADR Format
MADR in `docs/adr/NNNN-kebab-case.md` (4-digit, gaps allowed)

### Docs Structure
Required: `docs/superpowers/{specs,plans}/`, `docs/adr/`, `docs/reports/`

### Creating plan/spec/adr files (MUST)
Do **not** hand-write frontmatter. Generate the file with the correct dated name
and required fields:
`docs-lint` is a plugin skill script, not a command on PATH — see
`.claude/rules/linting.md`. Substitute `LINT` below:

```
LINT="plugins/h2t-dev/skills/docs-lint/scripts/lint.py"   # from this checkout
.venv/bin/python "$LINT" new plan <slug> [--milestone M3]   # docs/superpowers/plans/YYYY-MM-DD-<slug>.md
.venv/bin/python "$LINT" new spec <slug> [--milestone M3]   # docs/superpowers/specs/YYYY-MM-DD-<slug>.md
.venv/bin/python "$LINT" new adr  <slug>                     # docs/adr/NNNN-<slug>.md
```
If a file already exists without frontmatter, backfill it deterministically:
`.venv/bin/python "$LINT" fix-safe --only=frontmatter`.

## Full Standards References
- Directory structure: C:/dev/docs/standards/documentation-structure.md
- Naming: C:/dev/docs/standards/naming-conventions.md
- Git conventions: C:/dev/docs/standards/git-naming-conventions.md
- ADR process: C:/dev/docs/standards/adr-process.md
- Linting: C:/dev/docs/standards/linting.md

## Repo-Specific Rules
