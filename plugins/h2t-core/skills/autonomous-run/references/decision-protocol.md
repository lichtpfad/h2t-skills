# Decision protocol (autonomous-run)

Canonical, portable copy of the decision discipline the generator stamps into every runbook
artifact. Referenced by `.claude/rules/autonomous-execution.md`.

For every blocking decision the agent hits while the operator is away:

## 1. Classify

Genuine operator-choice / risky **vs.** an allow-listed default-shaped decision.

## 2. Auto-resolve — allow-list only (deny-by-default)

Auto-resolution fires **only** for this enumerated set of low-risk, reversible categories —
never "anything that isn't a hard-stop":

- choosing a library/API call shape or signature among documented options,
- formatting / naming / code-style within existing conventions,
- test-fixture values and non-behavioral test wording,
- documentation / comment wording.

For an allow-listed decision: invoke `h2t-ops:research` for best-practice → pick → append the
choice + rationale to the runbook **Decision-log** → continue.

## 3. Escalate everything else

Stop → eligible WIP-commit (verify branch first) → `h2t-core:handoff`. **Never auto-resolve.**
This explicitly includes anything outside the allow-list — security, privacy, legal/licensing,
data-loss risk, public-API behavior change, schema/data migration, adding a new dependency,
performance-budget changes, external-service side effects — **and** the four named hard-stops:

- **Irreversible / destructive** — delete / force-push, merge to main, external publish/send,
  deleting/modifying pre-existing untracked files.
- **Money / budget** — paid runs, token budget over limit, council/codex beyond the expected
  cost-gate.
- **Scope / architecture change** — deviation from the approved spec, a new invariant, a
  redefined goal.
- **Gate not fixable in** `N_gate_attempts` (default 2) — a gate whose `[P1]` is still open
  after N distinct fix attempts on the same finding, or a test suite still red after N fix
  cycles. One *attempt* = one fix edit + one re-run of the gate/test. Do not loop past N.

The allow-list is deliberately narrow. Widening it is an operator decision, not something a
run infers. Base: Anthropic's Opus-4.8 autonomy clause (minor/reversible → decide and note;
scope-change/destructive → ask), tightened to an explicit allow-list plus the research step.
