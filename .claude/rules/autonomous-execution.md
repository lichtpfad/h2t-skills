# Autonomous Plan Execution

Scope: autonomous / unattended execution of a multi-step plan only (overnight, "run the plan
yourself"). NOT for interactive work or small fixes.

1. Plan gate before starting: a **codex pass** over the plan (mandatory; a judge council is
   optional, for high risk). Execute only if the gate passes (no `[P1]`).
2. Codex validation after every non-trivial gate.
3. A final implementation **council** at the end (codex + ≥2 Opus lenses → SOUND).
4. Broken → fix → handoff.

Council and codex cost real money — the cost gate from CLAUDE.md still applies; this rule
does not authorise multi-agent work on trivial tasks.

## Canonical protocol source

The complete, portable definitions of the gates and of the decision protocol (allow-list +
hard stops) live in the `h2t-core:autonomous-run` skill and are stamped into a durable
runbook artifact on every run:

- Gates (codex review gate + council finish gate + pre-merge-check, `N_gate_attempts`):
  `plugins/h2t-core/skills/autonomous-run/references/gates.md`
- Decision protocol (auto-resolve allow-list, deny by default + 4 hard stops):
  `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md`

Points 1–4 above are a summary; where they disagree with `references/`, the references are
the source of truth. Start or resume an autonomous run through the `h2t-core:autonomous-run`
skill (it generates the runbook, keeps two-track state, and carries the run to handoff).
