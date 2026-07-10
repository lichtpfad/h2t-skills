# Proposed additions to `C:/dev/docs/standards/naming-conventions.md`

## Use stable roadmap-slot numbers for plans; keep number out of the filename
- **Evidence:** lineages quant-kb · recurrence 1 · domain-indep medium
- **Source:** `C:/dev/quant-kb/.claude/rules/plan-naming.md`
- **What to add:** Plan numbers (Plan N) are stable roadmap slot identifiers, not sequential counters. The number must not appear in the filename (filenames use `YYYY-MM-DD-<slug>.md`). A single roadmap table — kept as the source of truth (e.g., in the repo README or a dedicated roadmap file) — maps each slot number to the plan filename and the corresponding GitHub issue. This prevents renumbering cascades when plans are inserted or reordered.
