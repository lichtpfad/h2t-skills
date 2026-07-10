# Proposed additions to `C:/dev/docs/standards/research-pipeline-runbook.md`

Harvested practices that belong in the existing standard rather than a new one.

## Shared gate-kernel with per-repo adapters; fixture conformance runner (fixture success is not workflow success)

- **Evidence:** lineages rejuve · recurrence 1 · domain-indep high
- **Source:** `C:/work/rejuve/docs/superpowers/plans/2026-06-06-research-pipeline-v2.md`
- **What to add:** The pipeline's safety and validation sections (gate logic, verdict emission, telemetry schema) belong in a shared gate-kernel that all repos import. Per-repo adapters wrap only source-specific I/O; they must not reimplement the gate logic (see also validation-scripts-call-real-gate.md). When running the fixture conformance suite, a fixture that passes in isolation but does not call the shared gate kernel proves nothing about the real pipeline — fixture success is not workflow success.

## Retrieval-first orchestration of external deep-research/agent APIs (wrap, don't reinvent; own only bounds, schema, and synthesis)

- **Evidence:** lineages h2t-skills · recurrence 1 · domain-indep medium
- **Source:** `C:/dev/h2t-skills/docs/superpowers/specs/2026-07-08-exa-research-capability.md`
- **What to add:** When integrating an external research or agent API (e.g. Exa, Perplexity, any deep-research endpoint), the integration must be retrieval-first: wrap the external API rather than reinventing its retrieval logic. The local layer owns only: input normalization and bounds, output schema validation, final synthesis, and cost/telemetry audit. Any logic that duplicates what the external API already does is a maintenance liability. The connector should be thin; richness comes from how results are synthesized, not from how they are fetched.

## Cheaper-tier gate chain: each pre-gate must be cheaper than the next and must gate it; hard-STOP at phase boundaries

- **Evidence:** lineages crypto-regime-spike · recurrence 1 · domain-indep high
- **Source:** `C:/dev/crypto-regime-spike/docs/superpowers/plans/2026-06-10-oi-macro-regime-test.md`
- **What to add:** In a multi-stage research or validation pipeline, order gates so that each pre-gate is cheaper (in cost and time) than the gate it conditions. A cheap state-audit gate must pass before an expensive existence-check runs; existence must pass before a costly model-inference gate runs. At each phase boundary, enforce a hard-STOP: downstream verdicts are forbidden until the upstream gate passes. This prevents wasting compute on inputs that a cheap earlier gate would have rejected.
