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
3. **Materialize TodoWrite.** Create a formal Task list mirroring the runbook's
   pipeline steps.
4. **Hand off.** Execution proceeds by following the runbook's checkboxed steps,
   invoking constituent skills per step. The skill does not conduct step-by-step; the
   artifact is the source of truth.

### Generation: hybrid (chosen)

- A **deterministic Python script** stamps the fixed skeleton: gate section,
  decision-protocol, fail-safe boundary, execution-principles, and the pipeline-step
  checkboxes. This is `pytest`-covered (template renders; required sections present;
  fail-safe section is always emitted). Mirrors the `docs-lint new plan/spec` pattern.
- The **model** weaves in the run-specific content the script cannot know:
  "where things are" (branch/spec/issue/venv), and step-specific detail derived from
  the spec.

Rationale: the safety-critical, invariant parts are deterministic and testable; the
spec-specific parts are model-filled where determinism is impossible.

## Components

| File | Role |
|---|---|
| `plugins/h2t-core/skills/autonomous-run/SKILL.md` | Trigger, launch procedure, hand-off rules, two-track state model |
| `.../references/runbook-template.md` | Durable-spine skeleton (artifact schema below) |
| `.../references/decision-protocol.md` | research→decide→log + the 4 fail-safe hard-stops; portable, stamped into artifact |
| `.../references/gates.md` | Canonical codex review-gate + council finish-gate definitions |
| `.../scripts/new_runbook.py` | Deterministic skeleton generator (hybrid, tested) |
| `.../scripts/test_new_runbook.py` | pytest coverage for the generator |

Related existing surfaces to reconcile (not owned by this skill, but pointed at it):

- `h2t-skills/.claude/rules/autonomous-execution.md` — expand the existing thin rule to
  reference `references/` as the canonical protocol source.
- `crypto-regime-spike-*/.claude/rules/execution-protocols.md` — becomes a thin
  per-repo pointer to `references/gates.md` (no longer the canonical copy).

## Runbook artifact schema (generated, all inline)

Written to `docs/superpowers/plans/YYYY-MM-DD-<slug>-runbook.md`:

1. **Durable-spine header** — authorization statement + "fresh session resumes from
   here" + "on ANY blocker → handoff".
2. **Where things are** — branch, spec path, issue, venv + test command.
3. **Pipeline steps** — ordered checkboxes:
   write-spec → review-spec → write-plan → **plan-gate** → subagent-driven-dev →
   gates → e2e → PR → handoff.
4. **Gates** — codex review-gate (per checkpoint + final), council finish-gate,
   pre-merge-check; gate commands inline.
5. **Decision-protocol** — research→decide→log; the 4 fail-safe hard-stops.
6. **Execution principles / do-not-violate** — git discipline (verify branch before
   every commit, `git mv`/`git rm` only, never touch untracked), one-command-per-Bash,
   frequent small commits, subagent rules (codex one-at-a-time, never parallel).
7. **Blocker / fail-safe protocol** — record blocker + what was tried → WIP-commit
   (verify branch first) → handoff. Never force a broken merge or a false-green.
8. **Decision-log** — append-only; auto-resolved defaults are recorded here (durable,
   not in the handoff).

## Two-track state model

- Durable artifact checkboxes (§ schema 3) = **source of truth**.
- TodoWrite/Task list = **live mirror**, kept in lockstep during a session.
- On resume (fresh session after compaction): read the artifact, rebuild the TodoWrite
  list from the still-unchecked steps. TodoWrite is ephemeral; the artifact is durable.

## Decision-protocol

For every blocking decision the agent hits while the operator is away:

1. **Classify.** Genuine operator-choice vs. researchable default-shaped decision.
2. **Default-shaped** (reversible, no scope/strategy/money impact): invoke
   `h2t-ops:research` for best-practice → pick → append the choice + rationale to the
   **Decision-log** → continue.
3. **Fail-safe hard-stops** (any of the following → stop → WIP-commit (verify branch)
   → handoff; never auto-resolve):
   - **Irreversible / destructive** — delete / force-push, merge to main, external
     publish/send, touching untracked files.
   - **Money / budget** — paid runs, token budget over limit, council/codex beyond the
     expected cost-gate.
   - **Scope / architecture change** — deviation from the approved spec, a new
     invariant, a redefined goal.
   - **Gate not fixable in N attempts** — codex P1 not closing, tests red after
     repeated fixes; do not loop.

Base formulation: Anthropic's Opus-4.8 autonomy clause (minor/reversible → decide and
note; scope-change/destructive → ask), extended with the research step.

## Testing

- `scripts/new_runbook.py`: `pytest` asserts the generated skeleton renders, contains
  all required sections (§ schema 1–8), and **always** emits the fail-safe section and
  the 4 hard-stops (safety invariant — must never be omissible).
- Skill body (`SKILL.md`) has no runtime code; correctness is exercised via the
  generator tests plus a manual smoke run.

## Open questions

None outstanding — entry point (post-brainstorm), fail-safe boundary (all 4 categories),
generation strategy (hybrid), placement (Core), and the TodoWrite requirement are all
resolved above.

## Self-review

- **Placeholder scan:** no TBD/TODO; open-questions section explicitly empty.
- **Consistency:** artifact schema (§ schema) matches the pipeline steps in Scope and
  the decision-protocol; two-track state model is consistent with the durable-artifact
  requirement.
- **Scope:** single skill + generator + references + one rule edit — focused enough for
  one implementation plan.
- **Ambiguity:** "hard-stop" is enumerated (4 categories); "default-shaped" is defined
  by exclusion (reversible, no scope/money/strategy impact).
