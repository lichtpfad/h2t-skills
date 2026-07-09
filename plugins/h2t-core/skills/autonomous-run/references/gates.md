# Gates (autonomous-run)

Canonical, portable gate definitions the generator stamps into every runbook artifact.
Referenced by `.claude/rules/autonomous-execution.md`. Promoted from the crypto-regime-spike
`execution-protocols.md` (which becomes a thin pointer here).

## Codex review-gate

Run a codex review as a mandatory gate:

- after **each milestone / checkpoint** of the plan, AND
- **at the end**, before any completion claim.

Codex catches classes of defect that pass implementer→spec→quality review (id-key collisions,
broken invariants, tautological tests). On a box where codex cannot spawn subprocesses, run it
with **embedded content** (`codex exec -` reading the diff/files from stdin, `-s read-only`,
`model_reasoning_effort="high"`) and instruct it not to run commands or read files. **GATE FAIL
if any `[P1]`.** Fix every `[P1]` before proceeding.

`N_gate_attempts` = **2**. One attempt = one fix edit + one gate re-run on the same finding.
If a `[P1]` is not closed within `N_gate_attempts`, escalate (hard-stop → handoff); do not loop.

## Council finish-gate

At the end of an autonomous run, convene a **council** of distinct lenses before handoff:

- **codex** (correctness / runtime) +
- **≥2 Opus** judges with non-duplicating lenses (e.g. statistical/logic soundness; invariant /
  stability / North-Star alignment).

Each returns **SOUND / blockers**. Resolve blockers before declaring complete. Write the verdict
to `docs/reports/<date>-council-validation-<slug>.md`. This is the final gate, on top of the
per-checkpoint codex review-gate.

## pre-merge-check

Run `pre-merge-check` (security / tests / build) before opening the PR. Full suite green; exit 0
is authoritative.
