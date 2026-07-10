# Council / Multi-Judge Dual-Model Adjudication as a Finish-Gate

**Proposed home:** `C:/dev/docs/standards/council-multi-judge-adjudication.md` (NEW)
**Track:** technical · **Recurrence:** 3 lineage(s) · **Domain-independence:** high

## TL;DR
High-stakes completions (autonomous runs, KB promotions, major pipeline changes) require a finish-gate structured as a council: at minimum Codex (correctness lens) plus two independent Opus passes (architectural and adversarial lenses). Judges must not read each other's verdicts before writing their own. Where judges diverge, a reconcile pass names the winning argument and its constraint. The final verdict is SOUND only when all lenses pass or reconciliation resolves. A single-model self-review is not a council and does not satisfy this gate.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike, quant-kb, rejuve
- Source files:
  - `C:/dev/crypto-regime-spike/docs/superpowers/plans/2026-07-08-archetype-e-council-blocker-fixes.md`
  - `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-quant-kb-vendor-council-2026-07-10.md`
  - `C:/work/rejuve/docs/superpowers/plans/2026-07-03-jtbd-segmentation.md`

## Notes for operator
Ready to lift — 3 lineages across distinct domains, high domain-independence. The reconcile-on-divergence clause is important and should be preserved. The autonomous-run skill (h2t-core:autonomous-run) already encodes this gate; this standard makes it portable beyond that skill.
