---
title: Linting Rules
date: "2026-04-13"
---
# Linting Rules

Platform constraint: no Node.js. All tooling is Python-based or standalone binaries.

## Tools

| Tool | Purpose | Config |
|------|---------|--------|
| pymarkdownlnt | Markdown structure (headings, lists, links) | `.pymarkdown.yaml` per repo |
| Vale | Prose quality (grammar, tone, clarity) | `.vale.ini` per repo |
| validate-frontmatter.py | YAML frontmatter against required fields | `scripts/validate-frontmatter.py` |
| validate-links.py | Internal link integrity | `scripts/validate-links.py` |

Frontmatter and structure validation ship with the pack: run the `h2t-dev:docs-lint`
skill (`audit`, `doctor`, `fix-safe`). Link integrity and prose tools are per repo.

## pymarkdownlnt

Place `.pymarkdown.yaml` in repo root:

```yaml
plugins:
  md013:
    enabled: false        # Line length (disabled — let editor wrap)
  md033:
    enabled: false        # Inline HTML (needed for diagrams)
  md041:
    enabled: false        # First line h1 (frontmatter comes first)
```

Install: `pip install pymarkdownlnt` (in active venv only).

Run: `pymarkdown scan docs/`

## Vale

Place `.vale.ini` in repo root:

```ini
StylesPath = .vale/styles
MinAlertLevel = warning

[docs/**/*.md]
BasedOnStyles = Vale
```

Vale is a standalone binary — download from https://vale.sh, no Node.js required.

## Frontmatter Validation

Required fields per directory:

| Directory | Required fields |
|-----------|----------------|
| `docs/superpowers/specs/` | `title`, `status`, `owner`, `date` |
| `docs/adr/` | `title`, `status`, `date` |
| `docs/superpowers/plans/` | none (auto-generated) |
| all other `docs/` | optional |

Valid `status` values:
- specs: `draft`, `ready`, `approved`, `implemented`
- ADRs: `proposed`, `accepted`, `deprecated`, `superseded`

Script: `scripts/validate-frontmatter.py` (see spec for implementation).

Run: `python scripts/validate-frontmatter.py docs/`

## Running All Checks

```bash
pymarkdown scan docs/
python scripts/validate-frontmatter.py docs/
python scripts/validate-links.py docs/
```

No CI enforcement is required for Phase 4 (by 2026-04-28). Manual runs before milestone closure are sufficient.
