---
title: "h2t-ops Research Fetch Ladder Closure Plan"
status: "draft"
owner: "lichtpfad"
date: "2026-05-24"
issue: "lichtpfad/h2t-skills#98"
spec: "docs/superpowers/specs/2026-05-24-h2t-ops-research-fetch-ladder-closure-design.md"
related:
  - "lichtpfad/h2t-skills#97"
  - "lichtpfad/h2t-skills#99"
  - "lichtpfad/h2t-skills#105"
  - "lichtpfad/h2t-skills#136"
---

# h2t-ops Research Fetch Ladder Closure Plan

## Objective

Close `#98` as a fetch-ladder contract and evidence issue, not as a broad new
implementation epic.

The current assumption is that the baseline runtime already exists in
`plugins/h2t-ops/skills/research/scripts/fetch_url.py`, and the remaining work
is to verify it against the closure spec, capture real smoke evidence, and
separate future work into `#105`, `#99`, and `#136`.

## Scope

In scope:

- verify implemented contract against the new `#98` closure spec;
- confirm `direct + jina` baseline behavior;
- confirm honest handling of `DEGRADED`, `FAILED`, and content gates;
- capture at least one real blocked-source smoke result;
- sync issue narrative so `#98` is clearly closure-ready;
- close `#98` if evidence matches the spec.

Out of scope:

- new browser provider implementation;
- AllTouchDesigner adapter/parser work (`#105`);
- author/channel resolution (`#99`);
- full research connector migration (`#136`).

## Work plan

### T0. Baseline audit

Goal:
confirm that the code and tests already cover the contract frozen by the spec.

Actions:

- read `fetch_url.py` and `test_fetch_url.py` against the new spec;
- map existing tests to closure requirements:
  - direct success/failure
  - Jina fallback
  - login/paywall gates
  - shell/short-body degradation
  - redirect-collapse detection
  - JSON envelope behavior
  - sidecar behavior
  - UTF-8 output
  - stub-provider non-execution
- list any real contract gaps.

Deliverable:

- pass/fail checklist in working notes or issue comment draft.

No commit.

### T1. Contract gap fixups

Goal:
patch only real mismatches between runtime and closure spec.

Possible fixes:

- JSON envelope inconsistency on failed runs;
- sidecar/write-path mismatch;
- unclear stub-provider skip behavior;
- contract drift between tests and runtime;
- missing docstrings or comments only if they block maintainability.

Guardrails:

- no broad refactor;
- no connector migration into `h2t_ops/connectors/research`;
- no new provider implementations.

Deliverable:

- narrow code/test/doc fix commit(s), only if needed.

### T2. Real smoke evidence

Goal:
produce closure evidence on real URLs.

Minimum smoke set:

1. one blocked-source URL that resolves honestly as `OK` or `DEGRADED`;
2. one URL that is honestly classified as gated or failed;
3. one proof that fallback/provider telemetry is visible.

Preferred examples:

- AllTouchDesigner historical URLs from `#98` / `#105`;
- one known public control URL if needed;
- one gated/login/paywall example if available and safe.

Evidence to capture:

- command used;
- status;
- provider used;
- content type / content gate;
- notable telemetry attempts;
- whether result is merge-worthy evidence or still future-work evidence.

Deliverable:

- issue comment text or report snippet with concrete outcomes.

No merge blocked by recovery rate. The criterion is honest classification.

### T3. Issue and roadmap sync

Goal:
make the repo state explicit so future work stops treating `#98` as greenfield.

Actions:

- add a closure summary comment to `#98`:
  - link the new spec;
  - state `direct + jina` closure baseline;
  - state what is intentionally deferred;
  - link downstream follow-ups `#105`, `#99`, `#136`;
  - include smoke evidence summary.
- if needed, update roadmap wording so `#98` is clearly research backlog done or
  closure-ready rather than open-ended design debt.

Deliverable:

- issue comment;
- optional roadmap doc update.

### T4. Close or reclassify

Goal:
finish the issue cleanly.

Closure rule:

- close `#98` if T0 and T2 confirm the spec is materially satisfied;
- otherwise leave it open only with a sharply reduced remainder, not as a vague
  umbrella.

If not fully closable:

- rewrite issue body/comment to say exactly what remains;
- spin remaining work into the correct child issue if needed.

Deliverable:

- `#98` closed, or narrowed to one residual blocker.

## Acceptance

- closure spec is committed and linked;
- runtime contract is verified against the spec;
- smoke evidence exists on real URLs;
- deferred work is pushed to `#105`, `#99`, or `#136`;
- `#98` is either closed or reduced to a single concrete blocker.
