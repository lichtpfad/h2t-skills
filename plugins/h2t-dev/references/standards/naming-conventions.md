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

## Feature Decomposition Vocabulary

When a feature is too large for one plan, it is split into ordered segments. Use **one
canonical term per granularity level** — do not invent per-repo labels (`slice1`, `SP-N`,
`Phase`, `Part`, `follow-on`). Ad-hoc increment labels are the single biggest naming drift
across repos.

### Granularity ladder

| Level | Term | Meaning | Size |
| --- | --- | --- | --- |
| Feature | **Epic** | The whole large feature, spanning multiple increments; tracked as a GitHub epic issue | multi-increment |
| Segment | **Increment N** | An independently-deliverable, ordered chunk of an epic that meets the Definition of Done; each has its own plan doc | ~1 sprint |
| Story | **(Vertical) Slice** | A thin end-to-end deliverable within an increment, cutting through all layers (UI → logic → persistence), deployable and testable on its own | ≤ ~2 days |
| Step | **Task** | A single implementation step within a slice | minutes–hours |

Grounding: "Increment" is the [Scrum Guide](https://scrumguides.org/scrum-guide.html)'s term
for a Definition-of-Done deliverable per sprint; "vertical slice" is the standard Agile/CD
decomposition shape — a thin, end-to-end, deployable cut through all layers
([MinimumCD](https://beyond.minimumcd.org/docs/migrate-to-cd/foundations/work-decomposition/)).

### Foreign-methodology aliases — recognize, do not adopt

External sources name these levels differently. Map them to the ladder; do **not** propagate
the foreign word into h2t plans/issues (mixing methodologies is what causes the drift).

| External term | Origin | Maps to |
| --- | --- | --- |
| `scope` (pl. scopes) | Shape Up (Basecamp) | Increment / Slice |
| `work package` | PMBOK / WBS | Slice / Task |
| `Program Increment (PI)` | SAFe | Epic-to-Increment grouping |

### Increment labels stay out of filenames (roadmap table = SSOT)

- A plan filename is `YYYY-MM-DD-<slug>.md` where `<slug>` describes the **work**, never the
  increment index. Do **not** bake labels into names (`…-slice1-…`, `…-adr0009-…`, `…-phase2-…`).
- The increment number is a **stable roadmap-slot identifier, not a sequential counter** —
  inserting or reordering increments must not trigger a rename cascade.
- One **roadmap table** — SSOT in the repo `docs/README.md` or `docs/roadmap.md` — maps each
  increment (Epic → Increment N) to its plan filename and its GitHub issue.

> Lineages: quant-kb (roadmap-slot numbering), crypto-regime-spike (increment-label drift),
> agentic-kb epic (A1/A2/A3) — recurrence 3, domain-independent. Promoted 2026-07-11.

## General Rules

- Max 50 characters for file names (excluding extension)
- Only alphanumeric, hyphens. No spaces, underscores, special characters
- All file names lowercase
- Date format: ISO 8601 (`YYYY-MM-DD`)
