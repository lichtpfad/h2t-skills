# Log Full Telemetry for Every Batch Run

**Proposed home:** `C:/dev/docs/standards/batch-run-telemetry.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
Every batch or mass-run must emit per-item telemetry: provenance, verdict + reason, gate outcomes, and tracebacks on failure. The log must be sufficient to reproduce, audit, and debug the run without re-running it. Telemetry is not optional; a silent batch run is not a valid deliverable.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/batch-telemetry.md`

## Notes for operator
Single-lineage (recurrence 1), but domain-independence is high and the rule is specific and portable. Pairs with fail-closed-fail-loud.md. Ready to lift; consider merging both into a single `batch-run-discipline.md` standard file.
