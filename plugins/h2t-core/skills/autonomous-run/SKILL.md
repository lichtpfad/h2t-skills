---
name: autonomous-run
description: Launch or resume an autonomous, unattended plan-execution run after brainstorm is complete. Generates a durable, self-contained runbook artifact, materializes a TodoWrite mirror of the pipeline, and carries the decision + gate protocols through to handoff. Use for "работай сам", "автономно", "overnight", "выполни план сам", "autonomous run", "resume runbook".
---

# autonomous-run

> Launcher + protocol for autonomous plan-execution runs. This skill does NOT re-implement
> the constituent skills — it generates a durable runbook artifact, tracks two-track state,
> and hands off per step. Full design: `docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md`.

<!-- Launch procedure (preconditions → generate → sealed-validate → materialize TodoWrite
     → hand off) is added in M3. -->

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
