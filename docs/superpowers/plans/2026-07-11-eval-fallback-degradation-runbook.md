---
title: "Autonomous run — Eval fallback degradation"
status: "draft"
date: "2026-07-11"
milestone: ""
issue: ""
---
# Autonomous run — Eval fallback degradation

> **Durable spine (autonomous run, 2026-07-11).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-07-11-eval-fallback-degradation-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/eval-fallback-impl`
- Spec: `docs/superpowers/specs/2026-07-11-eval-fallback-degradation.md`
- Issue: #289
- Tests: `C:/dev/h2t-skills/.venv/Scripts/pytest`
- e2e applicability: applies (CLI smoke: h2t-ops evals status --json, Task5 Step5 + full suite Task7)

## Pipeline steps

- [x] **write-spec** — DONE pre-run: `docs/superpowers/specs/2026-07-11-eval-fallback-degradation.md` exists (merged via #303)
- [x] **review-spec** — DONE pre-run: spec iterated + reviewed across commits 6ba6d48..128b996, merged #303 (no open [P1])
- [x] **write-plan** — DONE pre-run: `docs/superpowers/plans/2026-07-11-eval-fallback-degradation.md` exists (merged #303)
- [x] **plan-gate** — DONE 2026-07-11: codex-rescue read-only pass. Found 2 confirmed [P1] + 1 [P2] (all verified by me); 1 codex [P2] refuted. Fixes folded into execution (see Decision-log). Plan file (merged #303) unchanged; deviations documented.
- [x] **subagent-driven-dev** — DONE 2026-07-11: all 7 TDD tasks executed (red→green→commit each). Plan-gate fixes folded in. Final scoped suite 1675 passed / 0 fail; ruff@latest clean on changed files. Commits 48b4f3e..f00a263.
- [x] **gates** — DONE 2026-07-11 council finish-gate = **SOUND**. codex final: NO [P1] (1 P2 docstring, fixed 05ee948). Opus Lens-A (correctness): SOUND, P2s out-of-scope (close(None) TypeError — no live caller; docstring nuance). Opus Lens-B (integration/regression): SOUND — traced all SkillEval callers (gather.py:130, writer.py:230, lib/cli/main.py:102), only corpus reader is read-only status.py; off-by-default = clean stop, no downstream misbehave; vendored parity byte-identical; connector reachable e2e. Zero [P1] across 3 lenses. pre-merge-check next.
- [x] **e2e** — DONE 2026-07-11: `python -m h2t_ops.cli evals status --json` returns valid envelope (mode=off, sdk_available=true, token_present=false, session_count real); human form + `connectors`/`doctor` list evals without error (Lens-B verified). pre-merge-check: Security PASS / Tests 1096 PASS / Build PASS (v3.2.13) / Plan 7/7 → READY.
- [x] **PR** — DONE 2026-07-11: pushed feat/eval-fallback-impl; opened PR #304 (https://github.com/lichtpfad/h2t-skills/pull/304). NOT merged (merge to main = hard-stop, operator decision).
- [x] **handoff** — DONE 2026-07-11: run complete through PR #304; session record written. All pipeline steps checked; no resume needed.

## Gates

- Codex review-gate after each milestone/checkpoint AND at the end (embedded content,
  read-only). GATE FAIL if any `[P1]`.
- Council finish-gate at the end (codex + >=2 Opus lenses) -> SOUND / blockers.
- pre-merge-check before PR.
- `N_gate_attempts` = 2. One attempt = one fix edit + one gate/test re-run.

## Decision-protocol

Auto-resolve ONLY allow-listed, reversible decisions (library/API call shape; formatting/
naming within conventions; test-fixture values; doc wording): research best-practice ->
pick -> append to Decision-log -> continue. Escalate everything else.

Hard-stops (stop -> eligible WIP-commit -> handoff; never auto-resolve):
- **Irreversible / destructive** (delete/force-push, merge to main, external publish/send,
  deleting/modifying pre-existing untracked files).
- **Money / budget** (paid runs, token budget over limit, council/codex beyond cost-gate).
- **Scope / architecture change** (deviation from approved spec, new invariant, redefined goal).
- **Gate not fixable in** `N_gate_attempts`.

## Execution principles

Verify branch before every commit; `git mv`/`git rm` only; never delete/modify pre-existing
untracked files (creating this run's own artifacts is allowed). One command per Bash call.
Frequent small commits. Codex subagents one-at-a-time, never parallel.

## Blocker / fail-safe protocol

Record the blocker + what was tried -> eligible WIP-commit (stage only intentional files,
never `git add -A`, never commit a red suite as green, message `WIP:` + what was left) ->
`h2t-core:handoff`. Never force a broken merge or a false-green.

## Decision-log

- 2026-07-11 pre-flight (advisor): **Task4 status.py deviation** — plan's `get_status`
  calls bare `_sdk_available()` imported into the status module, which `monkeypatch.setattr(sess, "_sdk_available", …)`
  does NOT reach → `test_status_off_when_no_sdk_or_token` fails on `sdk_available is False`
  (h2t_evals IS importable in this venv, verified). Fix: status.py uses
  `import lib.eval.session as sess` and calls `sess._sdk_available()` / `sess.resolve_mode()`.
  Bounded to Task4 impl; makes the plan's own declared tests pass. Allow-listed (call-shape).
- 2026-07-11 pre-flight: **Branch** — plan-referenced `feat/eval-fallback-degradation`
  already exists as a stale ancestor-of-main pointer (pre-#303). Used `feat/eval-fallback-impl`
  off main instead; did not touch the stale branch.
- 2026-07-11 pre-flight: contracts verified before Task5 — `ConnectorSpec(name,help,client,register)`,
  `discover()` auto-finds subpackages via CONNECTOR attr (no registration list), CLI is `h2t_ops.cli`.
- 2026-07-11 handoff note (BREAKING): after merge, machines without SDK+token flip eval
  telemetry to `off` (local JSON writes stop) unless `H2T_EVALS_MODE=local` is set. Intended.
- 2026-07-11 PLAN-GATE (codex-rescue, verified by me):
  - **[P1] Task5 CLI unreachable** — `h2t_ops/cli.py:182` dispatches connectors only if
    `argv[0] in _MIGRATED` (line 18 set); "evals" absent → `h2t-ops evals status` falls to
    legacy `_legacy()`, Task5 Step5 smoke fails (unit tests stay green — real e2e gap). FIX:
    add `"evals"` to `_MIGRATED` in cli.py as an extra step in Task 5. Confirmed by reading cli.py.
  - **[P1] Task4 monkeypatch miss** — (as above) status.py must call `sess._sdk_available()` /
    `sess.resolve_mode()` module-qualified. Confirmed.
  - **[P2→apply] Task4 session_count over-count** — plan's `root.rglob("*.json")` counts any
    json under evals root; sessions live at `<root>/<skill>/sessions/*.json`. Not a test-fail
    (test has 1 file) but mislabels count. FIX: use `root.glob("*/sessions/*.json")`. Applied in Task4.
  - **[P2 refuted] ConnectorSpec client typing** — codex claimed a function is passed; plan
    passes a STRING `"lib.eval.status:get_status"` (like drive). No action.
- 2026-07-11 Task6 deviation: `plugins/h2t-core/CHANGELOG.md` did NOT exist (plan assumed
  bump_plugin.py updates it; it only touches plugin.json + marketplace.json). Created the
  CHANGELOG following h2t-dev convention with the 3.2.13 BREAKING entry.
- 2026-07-11 Task7: **bare `pytest` from root crashes collection** (INTERNALERROR) —
  pre-existing, NOT a regression: `plugins/h2t-core/skills/init-project/scripts/apply_registration.py`
  calls `sys.exit(1)` at import when `ruamel.yaml` is absent (it is, in local .venv). The
  real gate is CI-scoped (`.github/workflows/evals.yml`): `pytest lib/`, `pytest tests/core
  tests/connectors`, `pytest plugins/h2t-core/skills/autonomous-run/scripts`. Ran
  `pytest lib/ tests/ plugins/h2t-core/skills/autonomous-run/scripts` → 1675 passed / 0 fail.
- 2026-07-11 Task7: ruff not installed in .venv and not a CI gate; repo carries ~200
  pre-existing ruff@latest findings. Verified my changed files clean under ruff@latest
  (fixed net-new E402 + a few pre-existing F401/F541 in files I was already editing).
- 2026-07-11 FINISH-GATE (advisor) — **Task3 enforcement gap fixed**: parity guard was at
  `tests/` root; CI (`evals.yml`) runs `pytest lib/`, `pytest tests/core tests/connectors`,
  autonomous-run scripts — none collect bare `tests/`, so the guard was DEAD in CI (my local
  `pytest lib/ tests/` was wider than the gate → false confidence). `git mv` into `tests/core`
  (CI-covered) + fixed ROOT `parents[1]→parents[2]` for the deeper location. Near-miss: the
  first commit staged the rename before the depth edit, committing parents[1] (would FileNotFound
  in CI); caught and fixed in follow-up commit 63ac4d3. Verified: `pytest tests/core tests/connectors`
  = 984 passed incl. parity. Restores drift enforcement (project_lib_gather_drift class).
- 2026-07-11 verified `Refs #289` is correct tracking issue (#289 OPEN: "Integrate skill
  telemetry with h2t-evals — push analytics + cost control").
