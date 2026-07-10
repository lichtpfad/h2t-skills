# SSoT-JSON Corpus to Deterministic Build with Acceptance and Freshness Gates

**Proposed home:** `C:/dev/docs/standards/ssot-json-deterministic-build.md` (NEW)
**Track:** technical · **Recurrence:** 2 lineage(s) · **Domain-independence:** high

## TL;DR
Data-driven projects must organize around a single source-of-truth JSON corpus (or equivalent structured source). All derived artifacts — HTML, reports, exports — are generated deterministically from that corpus by committed scripts, never hand-edited. The pipeline includes: a schema-validation gate on the corpus, an acceptance gate on the generated output, and a freshness gate (stale-check comparing live artifact against a clean build). Numbers and facts reach any deliverable only by flowing through the corpus → build chain.

## Evidence (where it was harvested)
- Lineages: claudeworking, rejuve
- Source files:
  - `C:/work/claudeworking/docs/superpowers/plans/2026-07-04-grants-phase2-cards-and-explorer.md`
  - `C:/work/rejuve/docs/superpowers/plans/2026-07-04-target-audience-dashboard.md`
  - `C:/work/rejuve/docs/superpowers/plans/2026-06-16-flow-map-as-is-to-be.md`

## Notes for operator
Ready to lift. Overlaps thematically with the truth/meaning-layer split (which is marked skip — already covered). This standard is narrower and more actionable: it is about the build pipeline contract, not just the conceptual split. Companion to generated-artifact-source-discipline.md.
