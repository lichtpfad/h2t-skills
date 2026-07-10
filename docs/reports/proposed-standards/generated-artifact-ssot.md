# Treat Generated Deliverables as Regenerable Artifacts, Never Hand-Edit Them

**Proposed home:** `C:/dev/docs/standards/generated-artifact-ssot.md` (NEW)
**Track:** process · **Recurrence:** 2 lineage(s) · **Domain-independence:** medium

## TL;DR
Generated HTML, PDFs, and report files are artifacts of a markdown or data source — they must never be hand-edited directly. Always regenerate from the source. Before declaring a deliverable published, run a stale-check to confirm the live artifact matches the current source.

## Evidence (where it was harvested)
- Lineages: rejuve, claudeworking
- Source files:
  - `C:/work/rejuve/.claude/rules/deploy-landings.md`
  - `C:/work/rejuve/.claude/rules/audience-dashboard.md`

## Notes for operator
Domain-independence is medium (most relevant for publishing/landing workflows). Ready to lift. Operator may want to generalize to cover any generated file (JSON corpus, HTML, PDF) or keep scope narrow to web deliverables.
