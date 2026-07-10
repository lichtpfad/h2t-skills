# Never Hand-Edit Generated Artifacts — Regenerate from Source, Gate for Staleness

**Proposed home:** `C:/dev/docs/standards/generated-artifact-source-discipline.md` (NEW)
**Track:** process · **Recurrence:** 2 lineage(s) · **Domain-independence:** medium

## TL;DR
Generated deliverables (HTML, compiled docs, derived data files) are artifacts of a source — markdown files, JSON corpora, or build scripts. Never hand-edit a generated artifact; any change goes into the source and triggers a clean regeneration. Before declaring a deliverable published or complete, run a stale-check: compare the live artifact against what a fresh build from the current source produces. A mismatch means the artifact is out of date and must be regenerated, not patched.

## Evidence (where it was harvested)
- Lineages: rejuve, claudeworking
- Source files:
  - `C:/work/rejuve/.claude/rules/deploy-landings.md`
  - `C:/work/rejuve/.claude/rules/audience-dashboard.md`

## Notes for operator
Medium domain-independence — most concrete in web/HTML pipeline contexts, but the principle applies broadly (any compiled/generated output). May need a brief generalization note when lifting. Closely related to the SSoT-JSON standard (ssot-json-deterministic-build.md).
