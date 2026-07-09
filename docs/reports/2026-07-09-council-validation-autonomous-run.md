# Council validation — autonomous-run orchestrator (2026-07-09)

Finish-gate for `h2t-core:autonomous-run` (branch `feat/autonomous-run-orchestrator`),
per `.claude/rules/autonomous-execution.md`. Three distinct lenses.

## Verdicts

| Lens | Reviewer | Verdict |
|---|---|---|
| Correctness / runtime | codex (embedded, read-only, high) | **no P1** — integration coherent; 3 P2 folded |
| Safety / sealed-validator | Opus judge A | **SOUND** — 2 disclosed-limitation P2 + 1 robustness nit |
| Resume / two-track + North-Star | Opus judge B | **BLOCKERS (1 P1)** → **RESOLVED** (below) |

## Codex (correctness) — no P1

M1/M2 Python gated individually (no open P1). Final holistic pass confirmed SKILL launch
procedure matches the real scripts, references carry the protocol faithfully, and the rule
reconciliation is coherent. 3 P2 folded: `runbook_schema.RUN_FIELDS` qualified in SKILL;
plan-gate clarified as codex (council optional pre-start, mandatory at finish); e2e
applicability (`applies`) vs completion (`DONE`) distinguished.

## Lens A — safety / sealed validator: SOUND

The validator is a sound **drift-guard** for its stated (non-adversarial) threat model:
duplicate-heading rejection, empty-body rejection, per-section marker binding, checkbox
pipeline completeness, and token-residue all close the realistic accidental-bypass paths.
`render()` calls `validate_or_raise` before returning, so no invalid runbook is ever
written. The deny-by-default allow-list is airtight by construction (explicit
"escalate everything else"; "add a new dependency" is separately named, so the one overlap
cannot smuggle it).

Non-blocking (accepted):
- [P2] line-scoped marker matching can retain a bold label while dropping the actionable
  line — exactly the "reduces, not eliminates" limitation the docstring discloses.
- [P2] `render()` seals the generator path; post-weave on-disk edits rely on the skill
  re-invoking the CLI validator (spec § Architecture step 3, procedural).
- Nit: token-residue over-matched a shell `>>` in `venv_test` (fail-closed false-positive).
  **Fixed** — check narrowed to `<<\w+>>` (commit `4e35c3c`); verified by generating a
  runbook with `venv_test="pytest x >> log"` (passes).

## Lens B — resume / North-Star: BLOCKER → RESOLVED

- [P1] Spec § Resume-trigger **mechanism-1** (handoff records the active runbook path,
  session-start surfaces it) was unimplemented — handoff/session-start had zero runbook
  references. Without it an overnight run crossing compaction could not auto-resume,
  degrading the unattended North Star.

**Resolution (commit `4e35c3c`):**
- `runbook_state.py` gained `is_active()` + a CLI (`runbook_state.py <path>` → unchecked
  steps / `(complete)`).
- `handoff` Step 4a: detects the newest `*-runbook.md` with an unchecked `- [ ] **step**`
  and records `runbook:{path}` + a `autonomous-run resume {path}` handoff checkbox.
- `session-start` Step 3: surfaces `Незавершённый автономный прогон … → autonomous-run
  resume <path>`.

**Verified end-to-end:** generated a real runbook → CLI listed all 9 unchecked steps →
the exact grep detection the two skills use (`^- \[ \] \*\*`) matched 9 lines → ACTIVE.
mechanism-2 (`autonomous-run resume <path>`) was already correct; mechanism-1 auto-discovery
now works.

Lens B non-blocker P2 (recorded, not fixed): `subagent-driven-dev` re-entry delegates fine-
grained task state to the plan file's per-task checkboxes (resumed by
`superpowers:subagent-driven-development`); this linkage is not documented in SKILL/template.
Follow-up doc note, not a correctness break.

## Overall

**SOUND after blocker resolution.** All safety invariants hold under the honest drift-guard
scope; resume (both mechanisms) works; North-Star shape (thin launcher+protocol, durable
self-contained artifact, TodoWrite mirror) is delivered. Suite: 30 pass (skill + handoff),
84 pass (incl. `tests/core`). Ready for PR; leave open for operator review (no auto-merge).
