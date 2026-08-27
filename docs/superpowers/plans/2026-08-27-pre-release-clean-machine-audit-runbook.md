# Autonomous run — Pre-release audit: the tree against a machine that is not the author's

> **Durable spine (autonomous run, 2026-08-27).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-08-27-pre-release-clean-machine-audit-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `audit/pre-release-clean-machine`
- Spec: `(none — brief is issue #431)`
- Issue: #431
- Tests: `.venv/bin/pytest tests/ lib/ -q`
- e2e applicability: applies — the installer on a clean HOME is exactly an externally-observable surface unit tests never exercise

## Pipeline steps

**This run measures; it does not refactor.** Findings land as a report plus issues. The only
authorized mutation outside this run's own artifacts is merging PR #430 once green — the
operator authorized that before leaving. Everything else is a hard-stop.

The canonical step names are kept so the artifact stays valid and resumable; the audit phases
sit inside `subagent-driven-dev`, which is where this run's work actually is.

- [x] **write-spec** — skill: `n/a — brief is issue #431` · input: `operator brief` · done: issue #431 filed with the seven scoped questions · failure: escalate · re-entry: idempotent: re-read issue
- [n/a] **review-spec** — NOT RUN, deliberately (Decision-log, 2026-08-27): a paid gate is a
  named hard-stop and the operator authorized an audit, not spend · skill: `codex review (embedded)` · input: `#431` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `this runbook` · input: `#431` · done: audit phases enumerated below · failure: escalate · re-entry: idempotent: overwrite plan
- [n/a] **plan-gate** — NOT RUN, same decision and same reason · skill: `codex review (embedded)` · input: `this runbook` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `audit phases A-J below` · input: `whole tree` · done: every phase has a recorded measurement · failure: record and continue; escalate only on hard-stop · re-entry: continue from first unchecked phase
- [x] **gates** — skill: `pre-merge-check` · input: `report + runbook` · done: suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: `synthetic HOME with no ~/.h2t` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->record · re-entry: idempotent: fresh HOME each run
- [x] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `runbook + report` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [x] **handoff** — skill: `h2t-core:handoff` · input: `run state` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

### Audit phases (inside subagent-driven-dev)

- [x] **A. inventory** — every skill, script and entry point enumerated; what claims to be runnable vs what is
- [x] **B. language** — every agent-facing text checked for non-English; file:line list
- [x] **C. hardcode** — absolute paths, usernames, machine names, assumed directories, per file
- [x] **D. clean-machine** — installer + all 9 entry points under a synthetic HOME; each failure classified loud / silent / misleading
- [x] **E. cross-test** — every test directory + every script's `--help`; a script that cannot run gets its reason recorded
- [x] **F. instructions** — SKILL.md frontmatter, triggers and references judged for an agent with no prior context; unstated assumptions listed
- [x] **G. duplicates** — overlapping-function skill pairs, with the evidence
- [x] **H. connectors-vs-api** — each connector against its provider API; gaps marked deliberate or missing
- [x] **I. architecture-review** — `claude-code-guide` agent on skill architecture, loading cost and trigger design (operator explicitly requested this agent)
- [x] **K. codex-compat** — cross-compatibility with OpenAI Codex: what here assumes the Claude Code harness (Skill tool, hooks, plugin cache) and what runs anywhere; AGENTS.md vs CLAUDE.md; whether the CLIs are harness-independent
- [x] **J. extras** — the run's own list of pre-publication checks, each backed by a measurement

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

- (append-only; auto-resolved defaults recorded here)
- **2026-08-27, operator, before leaving:** "важно ничего не поломать" — the run is
  read-only beyond its own artifacts. No fixes ship tonight, including obviously-correct
  ones. A finding is a finding; the morning decides what to do with it.
- **2026-08-27, operator:** deliverable is a morning-ready work plan **plus the state of
  both machines** — this Mac and AUTOMATA. The report must say what each machine is in,
  not only what the repository is in.
- **2026-08-27, operator:** skills are to be English-only; the response language comes from
  the user's own settings, not from the skill text. Recorded as target state for phase B —
  measured, not fixed tonight.
- **2026-08-27, run:** codex review-gate and council finish-gate are NOT run. Both cost
  money (a named hard-stop) and the operator authorized an audit, not spend. The run also
  produces no behavioural change for them to gate. Flagged here so the morning can disagree.
- **2026-08-27, operator:** `claude-code-guide` agent explicitly requested for the
  architecture phase; that is the only subagent this run spawns.

## Run outcome (2026-08-27)

Reports: `docs/reports/2026-08-27-pre-release-audit.md` (~760 lines) and
`docs/reports/2026-08-27-pre-release-audit-windows.md` (119 lines, by the AUTOMATA agent).
PR: #437.

Issues filed: #432 (secrets location), #433 (dead `/h2t:*` hints), #434 (author paths),
#435 (LICENSE / .gitignore), #436 (English-only skills). Corrected in place: #428 (18→14),
#429 (10→4).

**D / e2e**: complete on both platforms. The Windows half arrived at 01:32 as
`docs/reports/2026-08-27-pre-release-audit-windows.md`, committed to this branch by the AUTOMATA
agent itself (f7093e0). Its answer: the quiet failures reproduce identically on Windows, and
connectors honour the exit-code contract (rc 3 for missing keys). It also recorded two limits
on its own measurement — the toolchain was not isolated, and captured output bypassed the
console codepage, so #428 is untouched by it.

Gates: suite 2089 passed / 7 skipped, ruff clean. Codex review-gate and council finish-gate
deliberately not run — see Decision-log.

Nothing in the repository changed except this runbook, the report, and PR #430 (merged under
prior authorization).

## Run closed (2026-08-27)

Closed after the morning session verified the outputs by state, not by checkbox: PR #430 and
#437 merged, both reports in `main`, all eleven audit phases recorded. The two gates above
stayed open in the checklist while the Decision-log already said they would not run — so the
artifact kept advertising itself as resumable for a day after the work had landed. A decision
recorded only in prose does not reach the mechanism that reads the boxes.

The findings this run filed were fixed in the session that followed and shipped in `main` at
9168c13: #432/#448 (secrets location), #433 (dead `/h2t:*` hints), #434 (author paths),
#435 (LICENSE / .gitignore), #439/#450 (standards path), #453 (the lone surrogate the Windows
half of the audit made visible). #431 closed.
