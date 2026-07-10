# Fail-Closed / Fail-Loud: Never Emit a False GO

**Proposed home:** `C:/dev/docs/standards/fail-closed-fail-loud.md` (NEW)
**Track:** process · **Recurrence:** 2 lineage(s) · **Domain-independence:** high

## TL;DR
Automated agents and gates must never emit a false GO. Degenerate or missing input produces INCONCLUSIVE, not KILL. One broken item in a batch logs the error, skips the item, and continues — it does not crash the run. Failure messages must state the precise cause (e.g., "quota exceeded on Exa API"), not vague descriptions like "permission blocked."

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike, rejuve
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/batch-telemetry.md`
  - `C:/work/rejuve/.claude/rules/research-execution.md`

## Notes for operator
Ready to lift as-is. Pairs naturally with the batch-telemetry standard (log-full-run-telemetry). Consider placing them in the same file or cross-referencing.
