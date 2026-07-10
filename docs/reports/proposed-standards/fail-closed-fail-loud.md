# Fail-Closed / Fail-Loud: Never Emit a False GO, Degenerate Input Yields INCONCLUSIVE

**Proposed home:** `C:/dev/docs/standards/fail-closed-fail-loud.md` (NEW)
**Track:** process · **Recurrence:** 2 lineage(s) · **Domain-independence:** high

## TL;DR
Any pipeline or batch process must follow fail-closed semantics: a degenerate or insufficient input produces INCONCLUSIVE, never a false affirmative (GO/PASS/TRADEABLE). A single broken item logs the error with precise cause and skips, but must not crash the run or silently degrade to a vague "permission blocked." Fail-loud means the stated cause is specific — every failure names the step, input, and reason. This applies to research pipelines, validation gates, data ingestion, and autonomous runs equally.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike, rejuve
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/batch-telemetry.md`
  - `C:/work/rejuve/.claude/rules/research-execution.md`

## Notes for operator
Ready to lift. The INCONCLUSIVE-not-KILL framing is the core portable rule; the specific verdict labels (KILL, TRADEABLE) are domain examples from crypto and can be generalized. Companion to the batch-telemetry standard.
