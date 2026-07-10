# Proposed additions to `C:/dev/docs/standards/naming-conventions.md`

Harvested practices that belong in the existing standard rather than a new one.

## Roadmap plan-slot numbering: Plan N is a stable slot, not a counter; keep number out of filename; maintain a single roadmap table as source of truth

- **Evidence:** lineages quant-kb · recurrence 1 · domain-indep medium
- **Source:** `C:/dev/quant-kb/.claude/rules/plan-naming.md`
- **What to add:** When a project uses numbered plans (Plan 1, Plan 2, …), the number is a stable roadmap slot identifier — it must not increment whenever a plan is revised or replaced. The slot number must not appear in the filename (to avoid filename churn on revision). Maintain a single roadmap table (e.g. `docs/roadmap.md`) as the authoritative source of truth for the slot → issue → file mapping. New plans get the next vacant slot number; a cancelled plan's slot is retired, not reused.
