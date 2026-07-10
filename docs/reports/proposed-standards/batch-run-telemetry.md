# Log Full Run and Per-Item Telemetry for Every Batch or Mass Run

**Proposed home:** `C:/dev/docs/standards/batch-run-telemetry.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
Any batch or mass run must produce a structured telemetry log that records: provenance (what inputs were used and from where), per-item verdict with reason, which gates were applied, and any tracebacks. The run must be fully observable and auditable after the fact without re-running. Storing only a summary is insufficient — item-level granularity is required so individual failures are diagnosable and the run can be reproduced or challenged.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/batch-telemetry.md`

## Notes for operator
Single-lineage but high domain-independence — applies to any batch process (research harvests, data ingestion, model benchmarks, bulk file ops). Liftable on domain-independence grounds. Pair with fail-closed-fail-loud.md for the full batch safety contract.
