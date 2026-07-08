---
title: "Autonomous run orchestrator"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-09"
milestone: ""
---

# Autonomous run orchestrator

## Problem

Autonomous, unattended plan-execution runs (overnight / "выполни план сам") have
been done ad hoc via per-repo runbooks (e.g. `crypto-regime-spike-d` archetype-D/E)
and per-repo rules (`execution-protocols.md`). Those runs performed well, but the
reusable structure lives nowhere: each run re-derives the durable-spine skeleton,
the gate policy, and the blocker discipline by hand. There is no machine-wide,
version-controlled capability to launch such a run consistently.

Two recurring failure modes motivate this:

1. **Context loss.** A long autonomous run crosses context compaction / a fresh
   session. Progress state held only in-conversation is lost.
2. **Spurious blocking.** The agent stops to ask the operator questions that, by the
   time a working plan exists, no longer have a real choice — the answer is a
   researchable best-practice default, not an operator decision.

## Goal

A reusable **launcher + protocol** skill, `h2t-core:autonomous-run`, that:

- generates a **durable runbook artifact** for a specific run (survives compaction;
  a fresh session resumes from it),
- materializes a **formal TodoWrite/Task list** mirroring the run's pipeline steps
  (live progress track),
- carries the reusable **decision-protocol** (research→decide→log with a fail-safe
  escalation boundary) and **gate definitions** as portable references,
- hands execution to existing constituent skills (writing-plans,
  subagent-driven-development, gates, finishing-a-development-branch, handoff).

Non-goal: the skill is **not** a fat orchestrator that re-implements the constituent
skills. Its minimal delta is `generate + protocol + trigger`. Execution state lives
in the durable artifact, not in the skill.

## Scope / boundary

- **Entry point:** post-brainstorm. The operator finishes the interactive brainstorm
  (agent has no remaining questions), then triggers the run. The orchestrator owns
  everything from **spec-write onward**: write-spec → self-review spec → write-plan →
  plan-gate → subagent-driven implementation → gates → e2e → PR → handoff.
- **Out of scope:** brainstorm itself (interactive, stays with the operator); the
  constituent skills' internals; the gate mechanics (codex/council) which remain a
  project rule.
- **Placement:** `plugins/h2t-core/skills/autonomous-run/`. `h2t-core` is enabled in
  every base agent-profile (dev/pos/ops/creative/dcc/product/marketing/mixed) plus the
  `minimal` overlay, so a Core skill is de-facto always-on across all repos while
  staying version-controlled in `h2t-skills` — strictly better than `~/.claude/skills/`
  for the "available everywhere + git-tracked" requirement.

## Architecture

Launch flow, on trigger:

1. **Preconditions.** Resolve and record: branch, venv + test command, issue, spec
   (exists, or write it as the first pipeline step).
2. **Generate** the durable runbook artifact from spec + issue + template. Gate
   commands, decision-protocol, and fail-safe boundary are stamped **inline** so the
   artifact is self-contained (a fresh session needs only the artifact, not the skill).
3. **Validate generation (sealed).** Immediately after generation — and again after any
   model weaving (§ Generation) — a validator re-parses the produced artifact and
   asserts the fail-safe section, the 4 hard-stops, and every required schema section
   are present verbatim. If any is missing or altered, generation fails loudly and the
   run does not start. This makes the safety text non-omissible in practice, not just at
   template time (codex-round-1 P1).
4. **Materialize TodoWrite.** Create a formal Task list mirroring the runbook's
   pipeline steps.
5. **Hand off.** Execution proceeds by following the runbook's checkboxed steps,
   invoking constituent skills per the **per-step execution contract** (below). The
   skill does not conduct step-by-step; the artifact is the source of truth.

### Resume trigger (fresh-session re-entry)

"Fresh session resumes from here" requires an explicit re-entry path — a new session
will not discover the artifact on its own (codex-round-1 P1). Two mechanisms, both
recorded so re-entry is deterministic:

- **Handoff writes the runbook path.** `h2t-core:handoff` records the active runbook
  artifact path in the session record; `h2t-core:session-start` surfaces it, so the
  next session is pointed at the artifact.
- **Explicit resume trigger.** The operator (or an unattended re-launch) invokes the
  skill with the runbook path: `autonomous-run resume <path>`. The skill reads the
  artifact, rebuilds the TodoWrite mirror from the unchecked steps (§ Two-track state
  model), and continues from the first unchecked step.

### Generation: hybrid (chosen)

- A **deterministic Python script** stamps the fixed skeleton: gate section,
  decision-protocol, fail-safe boundary, execution-principles, and the pipeline-step
  checkboxes (with the per-step contract columns). `pytest`-covered (template renders;
  required sections present; fail-safe always emitted). Mirrors `docs-lint new plan/spec`.
- The **model** weaves in the run-specific content the script cannot know:
  "where things are" (branch/spec/issue/venv) and the `input` paths of each step. The
  model MUST NOT edit or remove stamped safety text (fail-safe, gates, hard-stops); the
  step-3 validator enforces this **after** weaving.

Rationale: the safety-critical, invariant parts are deterministic and testable; the
spec-specific parts are model-filled where determinism is impossible. The
post-generation validator seals the split so weaving cannot silently drop safety text.

## Per-step execution contract

Across context compaction, "invoke skill X" as natural-language intent is not a
resumable contract (codex-round-1 P1). Each pipeline step in the artifact is written as
a structured row with five fields, so a fresh session can re-enter any step
deterministically:

| Field | Meaning |
|---|---|
| **skill** | exact constituent skill / command to invoke (e.g. `superpowers:writing-plans`) |
| **input** | artifact(s) the step consumes (spec path, plan path, issue) |
| **done-criterion** | observable condition that marks the checkbox done (file exists, tests green, PR opened) |
| **failure-path** | what to do on failure (retry with counter, gate, or escalate — links to fail-safe) |
| **re-entry** | how to resume this step mid-flight after interruption (idempotent restart vs continue) |

The generator stamps skill / done-criterion / failure-path / re-entry for the fixed
pipeline; the model fills `input` paths from the run's "where things are".

## Conditional end-to-end (e2e) step

Not every task has an end-to-end surface, but some do — and they are exactly the tasks
where unit-green is a false-green (this point was not covered in the initial design).
Some tasks expose a real integration/behavioral path (e.g. archetype-D/E registered real
frames and ran them through `run_frame` for real fail-closed verdicts); many don't (a
pure library, refactor, or docs change). The pipeline therefore carries **e2e as a
conditional step**:

- **Applicability decision (recorded).** At plan time the run classifies the task: does
  the spec define an externally-observable behavioral surface that unit tests do not
  exercise end-to-end? The decision + reason is written into the runbook (Where things
  are / Decision-log) so a fresh session does not re-litigate it.
- **When e2e applies:** the step exercises the real path end-to-end (register the real
  inputs, run the real entrypoint); its done-criterion is a real run producing the
  expected or fail-closed output — not merely green unit tests. An INCONCLUSIVE /
  fail-closed verdict is an **acceptable** e2e outcome **only when the step's objective
  is wiring-validation** (machinery wired + fail-closed path exercised, as in E's
  INCONCLUSIVE); when the objective is a specific behavioral result, INCONCLUSIVE
  **fails** the e2e step (codex-round-2 P2).
- **Three terminal states, never a silent skip (codex-round-2 P2):**
  - `e2e: DONE` — ran, done-criterion met.
  - `e2e: N/A (no integration surface)` — the task has no externally-observable
    behavioral path; checked off without a run.
  - `e2e: BLOCKED/DEFERRED (<reason>)` — an integration surface exists but is not
    runnable in the current environment (missing service, GPU, credential, data). This
    is **not** N/A: record the reason and route to handoff or an explicit operator gate;
    do not check it off as passed.
  The generator stamps the e2e step unconditionally; the skill/model assigns one of the
  three states from the spec — it is never silently dropped.

For this orchestrator's own build (§ Implementation phasing), e2e **applies**: the M1
generator + validator have a real end-to-end path — generate a runbook from a real spec,
then assert the produced artifact passes the sealed validator.

## Components

| File | Role |
|---|---|
| `plugins/h2t-core/skills/autonomous-run/SKILL.md` | Trigger, launch + resume procedure, hand-off rules, two-track state model |
| `.../references/runbook-template.md` | Durable-spine skeleton (artifact schema below) |
| `.../references/decision-protocol.md` | research→decide→log allow-list + the 4 fail-safe hard-stops; portable, stamped into artifact |
| `.../references/gates.md` | Canonical codex review-gate + council finish-gate definitions |
| `.../scripts/new_runbook.py` | Deterministic skeleton generator (hybrid) |
| `.../scripts/validate_runbook.py` | Post-generation sealed-safety validator (re-parses the produced artifact) |
| `.../scripts/test_*.py` | pytest coverage for generator + validator |

Related existing surfaces to reconcile (not owned by this skill, but pointed at it):

- `h2t-skills/.claude/rules/autonomous-execution.md` — expand the existing thin rule to
  reference `references/` as the canonical protocol source.
- `crypto-regime-spike-*/.claude/rules/execution-protocols.md` — becomes a thin
  per-repo pointer to `references/gates.md` (no longer the canonical copy).

## Runbook artifact schema (generated, all inline)

Written to `docs/superpowers/plans/YYYY-MM-DD-<slug>-runbook.md`:

1. **Durable-spine header** — authorization statement + a **resume line** (the exact
   `autonomous-run resume <this-path>` command) + "on a hard-stop or unresolvable
   blocker → handoff" (note: not *any* blocker — default-shaped decisions are
   auto-resolved, § Decision-protocol).
2. **Where things are** — branch, spec path, issue, venv + test command.
3. **Pipeline steps** — ordered checkboxes, each carrying the § Per-step execution
   contract fields: write-spec → review-spec → write-plan → **plan-gate** →
   subagent-driven-dev → gates → **e2e (conditional, § Conditional end-to-end)** →
   PR → handoff.
4. **Gates** — codex review-gate (per checkpoint + final), council finish-gate,
   pre-merge-check; gate commands inline. `N_gate_attempts` (default **2**) defined here.
5. **Decision-protocol** — research→decide→log allow-list; the 4 fail-safe hard-stops.
6. **Execution principles / do-not-violate** — git discipline (verify branch before
   every commit, `git mv`/`git rm` only, never delete/modify **pre-existing** untracked
   files — creating the run's own artifacts is allowed), one-command-per-Bash, frequent
   small commits, subagent rules (codex one-at-a-time, never parallel).
7. **Blocker / fail-safe protocol** — record blocker + what was tried → **eligible**
   WIP-commit → handoff. WIP-commit eligibility: stage only intentional files (never
   `git add -A`), never commit a red test suite as green, message prefix `WIP:` + what
   was left. Never force a broken merge or a false-green.
8. **Decision-log** — append-only; auto-resolved defaults recorded here (durable, not in
   the handoff).

## Two-track state model

- Durable artifact checkboxes (§ schema 3) = **source of truth**.
- TodoWrite/Task list = **live mirror**, derived from the artifact.
- **Update ordering (one-way, codex-round-1 P1):** on step completion, write the
  artifact checkbox **first** (durable source of truth), then mark the TodoWrite item.
  A crash after the artifact write but before the TodoWrite update is harmless — on
  resume the mirror is rebuilt from the artifact, so "artifact leads TodoWrite" is
  exactly the recoverable state. The reverse ordering (TodoWrite first) is forbidden: it
  can mark a step done in the live mirror while the durable record still shows it
  pending, so a non-idempotent step could be skipped or double-run depending on which
  track is trusted.
- **Reconciliation on resume:** the artifact is authoritative. Rebuild the TodoWrite
  list from the artifact's unchecked steps; discard any stale in-session TodoWrite. A
  step whose done-criterion is already satisfied (e.g. the PR exists) is checked without
  re-running.

## Decision-protocol

For every blocking decision the agent hits while the operator is away:

1. **Classify.** Genuine operator-choice / risky vs. an **allow-listed** default-shaped
   decision.
2. **Auto-resolve — allow-list only (codex-round-1 P1).** Auto-resolution fires **only**
   for an enumerated set of low-risk, reversible categories, not "anything not a
   hard-stop":
   - choosing a library/API call shape or signature among documented options,
   - formatting / naming / code-style within existing conventions,
   - test-fixture values and non-behavioral test wording,
   - documentation / comment wording.
   For an allow-listed decision: invoke `h2t-ops:research` for best-practice → pick →
   append the choice + rationale to the **Decision-log** → continue.
3. **Escalate everything else (stop → eligible WIP-commit → handoff; never auto-resolve).**
   This explicitly includes the enumerated hard-stops **and** anything outside the
   allow-list — security, privacy, legal/licensing, data-loss risk, public-API behavior
   change, schema/data migration, adding a new dependency, performance-budget changes,
   and external-service side effects. The 4 named hard-stop categories:
   - **Irreversible / destructive** — delete / force-push, merge to main, external
     publish/send, deleting/modifying pre-existing untracked files.
   - **Money / budget** — paid runs, token budget over limit, council/codex beyond the
     expected cost-gate.
   - **Scope / architecture change** — deviation from the approved spec, a new
     invariant, a redefined goal.
   - **Gate not fixable in `N_gate_attempts`** (default **2**) — a gate whose `[P1]` is
     still open after N distinct fix attempts on the same finding, or a test suite still
     red after N fix cycles. One *attempt* = one fix edit + one re-run of the gate/test.
     Do not loop past N.

Design note: the allow-list is deliberately narrow (deny-by-default). Widening it is an
operator decision, not something the run should infer. Base formulation: Anthropic's
Opus-4.8 autonomy clause (minor/reversible → decide and note; scope-change/destructive
→ ask), tightened to an explicit allow-list plus the research step.

## Testing

- `scripts/new_runbook.py`: `pytest` asserts the generated skeleton renders and contains
  all required sections (§ schema 1–8) with the per-step contract fields populated.
- `scripts/validate_runbook.py`: `pytest` asserts the validator **rejects** an artifact
  with the fail-safe section, any hard-stop, or a required schema section removed or
  altered — the safety invariant is provably non-omissible after model weaving, not just
  at template time.
- Skill body (`SKILL.md`) has no runtime code; the launch + resume + reconciliation
  procedures are exercised via a manual smoke run recorded in the plan.

## Implementation phasing

The spec is one coherent design but spans several independently-buildable pieces; the
implementation plan should phase it (codex-round-1 P2) so each phase gates the next:

- **M1 — generator + schema + sealed validator.** `new_runbook.py`, the runbook
  template (schema §1–8 with per-step contract), `validate_runbook.py`, and their tests.
  Deliverable: a runbook file can be generated and provably contains the safety text.
- **M2 — resume + two-track state.** The resume trigger, artifact↔TodoWrite ordering
  and reconciliation, handoff/session-start path recording.
- **M3 — orchestration + protocol wiring.** `SKILL.md` launch/hand-off, the
  decision-protocol allow-list, and the rule reconciliation
  (`autonomous-execution.md` → references; crypto `execution-protocols.md` → pointer).

## Open questions

None outstanding — entry point (post-brainstorm), fail-safe boundary (all 4 categories),
generation strategy (hybrid), placement (Core), the TodoWrite requirement, and the
codex-round-1 findings (resume trigger, per-step contract, state ordering, N definition,
allow-list classifier, sealed generation) are all resolved above.

## codex-round-1 findings applied

6 P1 + 4 P2 from the codex spec review folded in: **P1** resume trigger (§ Resume
trigger), per-step contract (§ Per-step execution contract), two-track race →
update-ordering + reconciliation (§ Two-track state model), `N_gate_attempts` defined
(§ schema 4 / § Decision-protocol), decision classifier narrowed to a deny-by-default
allow-list (§ Decision-protocol), sealed generation via post-gen validator (§ Architecture
step 3, § Testing); **P2** "blocker" redefined (hard-stop/unresolvable, not *any*),
untracked-file exception for own artifacts, WIP-commit eligibility checklist, scope
phased into M1–M3 (§ Implementation phasing).

**codex-round-2 (PASS — no P1).** All 6 round-1 P1s verified resolved. 3 P2 folded:
two-track update-ordering wording corrected (§ Two-track state model); e2e gains a
third terminal state `BLOCKED/DEFERRED` so an unrunnable integration surface is never
silently marked N/A (§ Conditional end-to-end); INCONCLUSIVE acceptable only when the
e2e objective is wiring-validation (§ Conditional end-to-end).

## Self-review

- **Placeholder scan:** no TBD/TODO; open-questions section explicitly empty.
- **Consistency:** artifact schema matches the pipeline steps in Scope, the per-step
  contract, and the decision-protocol; two-track ordering is consistent with the
  durable-artifact source-of-truth rule; "blocker → handoff" wording reconciled with the
  auto-resolve path.
- **Scope:** larger than a trivial skill, so phased into M1–M3; each phase is a coherent
  plan unit that gates the next.
- **Ambiguity:** "hard-stop" enumerated (4 categories); auto-resolution is an explicit
  allow-list (deny-by-default), not defined by exclusion; `N_gate_attempts` and "attempt"
  defined.
