---
name: autonomous-run
description: Launch or resume an autonomous, unattended plan-execution run after brainstorm is complete. Generates a durable, self-contained runbook artifact, materializes a TodoWrite mirror of the pipeline, and carries the decision + gate protocols through to handoff. Use for "работай сам", "автономно", "overnight", "выполни план сам", "autonomous run", "resume runbook".
compatibility: "Claude Code. Requires the codex CLI — both gates call it, the per-checkpoint
  review and the final council, and both cost money. Runbook scripts run through uv, so no
  interpreter has to be installed."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# autonomous-run

> Launcher + protocol for autonomous plan-execution runs. This skill does NOT re-implement
> the constituent skills — it generates a durable runbook artifact, tracks two-track state,
> and hands off per step. Full design: `docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md`.

## When to use

Post-brainstorm. The operator finishes the interactive brainstorm (the agent has no remaining
questions), then triggers the run. This skill owns everything from **spec-write onward**:
write-spec → review-spec → write-plan → plan-gate → subagent-driven-dev → gates → e2e → PR →
handoff. Brainstorm itself stays interactive with the operator.

## Launch

1. **Preconditions.** Resolve and record: branch, venv + test command, issue, spec (exists, or
   write it as the first pipeline step).
2. **Classify e2e applicability** (spec § Conditional e2e): does the task expose an
   externally-observable behavioral surface unit tests don't exercise end-to-end?
   → applicability at launch is `applies` / `N/A (no integration surface)` /
   `BLOCKED-DEFERRED (<reason>)`. Record it. (Completion of the e2e step later is `DONE`,
   or stays `N/A` / `BLOCKED-DEFERRED` — applicability ≠ completion.)
3. **Generate** the durable runbook artifact with `scripts/new_runbook.create_runbook(...)`:
   `docs/superpowers/plans/<date>-<slug>-runbook.md`. Fields (`runbook_schema.RUN_FIELDS`:
   title, today, runbook_path, branch, spec_path, issue, venv_test, e2e_state) come from the
   run's "where things are". Generation calls the sealed validator on emit — a runbook that
   fails validation is never written.
4. **Materialize TodoWrite** mirroring the runbook's pipeline steps.
5. **Hand off.** Follow the runbook's checkboxed steps in order, invoking the constituent skill
   named in each step's per-step contract. This skill does not conduct step-by-step — the
   artifact is the source of truth.

## Protocols (portable references)

- **Decisions:** `references/decision-protocol.md` — auto-resolve allow-list (deny-by-default) +
  the 4 hard-stops. Escalate anything not on the allow-list.
- **Gates:** `references/gates.md` — codex review-gate (per checkpoint + final), council
  finish-gate, pre-merge-check, `N_gate_attempts` = 2.
- **On a hard-stop or unresolvable blocker → `h2t-core:handoff`** (record blocker + eligible
  WIP-commit first). Not on a default-shaped decision — those are auto-resolved.

## Resume & state (two-track)

On `autonomous-run resume <path>`:

1. Read the artifact (durable source of truth).
2. `runbook_state.unchecked_steps()` → rebuild the TodoWrite mirror from the unchecked
   pipeline steps only; discard any stale in-session TodoWrite.
3. A step whose done-criterion is already satisfied (PR exists, tests green) is checked
   without re-running.
4. Continue from the first unchecked step, following its per-step contract.

**Update ordering (one-way):** on step completion, write the artifact checkbox FIRST
(durable source of truth), then mark the TodoWrite item. The reverse is forbidden — it can
mark a step done in the live mirror while the durable record still shows it pending, so a
non-idempotent step could be skipped or double-run depending on which track is trusted.
