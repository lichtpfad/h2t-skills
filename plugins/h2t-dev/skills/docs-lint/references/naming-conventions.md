---
title: Naming Conventions
date: 2026-04-13
---
# Naming Conventions

Standards for file and directory naming across all H2T platform repositories.

## File Naming

| Type | Pattern | Example |
| --- | --- | --- |
| ADR | `NNNN-kebab-case-verb-noun.md` | `0001-use-postgresql-for-storage.md` |
| Superpowers spec | `YYYY-MM-DD-kebab-case-design.md` | `2026-04-12-source-management-api-design.md` |
| Superpowers plan | `YYYY-MM-DD-kebab-case.md` | `2026-04-12-source-management-api.md` |
| Research | `YYYY-MM-DD-kebab-case.md` | `2026-03-18-knowledge-graphs-education.md` |
| Report | `mN-kebab-case-report.md` | `m8-ground-truth-improvement-loop-report.md` |
| Product doc | `kebab-case.md` | `positioning.md`, `mvp-scope.md` |
| Client doc | `kebab-case.md` | `quickstart.md`, `api-guide.md` |
| Marketing doc | `kebab-case.md` | `use-cases.md`, `positioning.md` |
| Architecture doc | `kebab-case.md` | `system-design.md`, `data-flow.md` |
| Guide | `kebab-case.md` | `getting-started.md`, `best-practices.md` |

## Directory Naming

- All lowercase
- kebab-case
- No underscores in directory names
- Max 2 levels of nesting within `docs/` (except `superpowers/specs/` and `superpowers/plans/`)

## ADR Numbering

- Sequential 4-digit: `0001`, `0002`, `0003`
- Gaps allowed -- never renumber existing ADRs (breaks cross-references, PR history)
- If a gap exists, explain in `index.md` (e.g., "003: skipped -- draft withdrawn")
- Present-tense verbs: `use-`, `adopt-`, `implement-`, `choose-`

## General Rules

- Max 50 characters for file names (excluding extension)
- Only alphanumeric, hyphens. No spaces, underscores, special characters
- All file names lowercase
- Date format: ISO 8601 (`YYYY-MM-DD`)
