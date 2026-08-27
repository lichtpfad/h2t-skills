---
title: ADR Process
date: 2026-04-13
---

# ADR Process

Architectural Decision Records (ADRs) in MADR format for all H2T repositories.

## Frontmatter Schema

Required frontmatter for every ADR:

```yaml
---
title: ADR-NNNN Title
status: proposed | accepted | deprecated | superseded
date: YYYY-MM-DD
superseded_by: NNNN  # only if status is superseded
---
```

## MADR Template

```markdown
---
title: ADR-NNNN Title
status: proposed | accepted | deprecated | superseded
date: YYYY-MM-DD
---

# ADR-NNNN: {Title}

## Context

What is the issue driving this decision?

## Decision

We will {action}.

## Rationale

Why this decision over alternatives?

## Consequences

### Positive
- ...

### Negative
- ...

## Alternatives Considered

Brief overview of rejected alternatives.

## Related ADRs

- ADR-NNNN: ...
```

## Numbering

- Sequential 4-digit: `0001`, `0002`, `0003`
- **Gaps allowed** — never renumber existing ADRs (breaks cross-references, PR history)
- If a gap exists, explain in `index.md` (e.g., "0003: skipped -- draft withdrawn")
- File naming: `NNNN-kebab-case-verb-noun.md`
- Present-tense verbs: `use-`, `adopt-`, `implement-`, `choose-`
- Example: `0001-use-postgresql-for-storage.md`

## Lifecycle

1. **Proposed** -- written, awaiting review
2. **Accepted** -- approved, in effect
3. **Deprecated** -- no longer relevant (keep file, update status)
4. **Superseded** -- replaced by another ADR (add `superseded_by` field)

Never delete ADR files. Update `status` in frontmatter instead.

## index.md Generation

`docs/adr/index.md` is generated from ADR frontmatter. The pack does not ship a
generator for it — supply your own, or maintain the index by hand.

The index lists all ADRs with number, title, status, and date. Gaps must be documented with an explanation row.

Example index format:

```markdown
# ADR Index

| # | Title | Status | Date |
|---|-------|--------|------|
| 0001 | [ADR-0001 Use PostgreSQL for storage](0001-use-postgresql-for-storage.md) | accepted | 2026-01-10 |
| 0002 | [ADR-0002 Adopt MADR format](0002-adopt-madr-format.md) | accepted | 2026-02-01 |
| 0003 | skipped -- draft withdrawn | — | — |
| 0004 | [ADR-0004 ...](0004-....md) | proposed | 2026-04-13 |
```
