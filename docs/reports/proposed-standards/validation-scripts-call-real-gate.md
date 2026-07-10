# Validation Scripts Must Call the Real Production Gate Code, Not Reimplementations

**Proposed home:** `C:/dev/docs/standards/validation-scripts-call-real-gate.md` (NEW)
**Track:** technical · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
Acceptance-gate scripts and test harnesses must import and invoke the actual production gate code — they are not permitted to reimplement the gate logic inline. Bookkeeping (counting, formatting, reporting) lives in the script; interpretation of results lives in the agent or operator. This contract ensures that a passing acceptance script guarantees the production path passes, rather than guaranteeing that a copy of the production path passes. Fixture success is not workflow success: a fixture that passes without calling the real gate proves nothing about the real pipeline.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike
- Source files:
  - `C:/dev/crypto-regime-spike/docs/superpowers/specs/2026-06-16-pipeline-validation-spec.md`
  - `C:/Users/stani/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-validation-library-2026-06-16.md`

## Notes for operator
Single-lineage but high domain-independence — this anti-pattern (reimplementing a gate in a test) is ubiquitous. Ready to lift. The "fixture success is not workflow success" aphorism should be preserved verbatim in the standard.
