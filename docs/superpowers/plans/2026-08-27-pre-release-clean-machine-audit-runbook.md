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
- [ ] **review-spec** — skill: `codex review (embedded)` · input: `#431` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `this runbook` · input: `#431` · done: audit phases enumerated below · failure: escalate · re-entry: idempotent: overwrite plan
- [ ] **plan-gate** — skill: `codex review (embedded)` · input: `this runbook` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [ ] **subagent-driven-dev** — skill: `audit phases A-J below` · input: `whole tree` · done: every phase has a recorded measurement · failure: record and continue; escalate only on hard-stop · re-entry: continue from first unchecked phase
- [ ] **gates** — skill: `pre-merge-check` · input: `report + runbook` · done: suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [ ] **e2e** — skill: `real entrypoint run` · input: `synthetic HOME with no ~/.h2t` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->record · re-entry: idempotent: fresh HOME each run
- [ ] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `runbook + report` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [ ] **handoff** — skill: `h2t-core:handoff` · input: `run state` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

### Audit phases (inside subagent-driven-dev)

- [ ] **A. inventory** — every skill, script and entry point enumerated; what claims to be runnable vs what is
- [ ] **B. language** — every agent-facing text checked for non-English; file:line list
- [ ] **C. hardcode** — absolute paths, usernames, machine names, assumed directories, per file
- [ ] **D. clean-machine** — installer + all 9 entry points under a synthetic HOME; each failure classified loud / silent / misleading
- [ ] **E. cross-test** — every test directory + every script's `--help`; a script that cannot run gets its reason recorded
- [ ] **F. instructions** — SKILL.md frontmatter, triggers and references judged for an agent with no prior context; unstated assumptions listed
- [ ] **G. duplicates** — overlapping-function skill pairs, with the evidence
- [ ] **H. connectors-vs-api** — each connector against its provider API; gaps marked deliberate or missing
- [ ] **I. architecture-review** — `claude-code-guide` agent on skill architecture, loading cost and trigger design (operator explicitly requested this agent)
- [ ] **K. codex-compat** — cross-compatibility with OpenAI Codex: what here assumes the Claude Code harness (Skill tool, hooks, plugin cache) and what runs anywhere; AGENTS.md vs CLAUDE.md; whether the CLIs are harness-independent
- [ ] **J. extras** — the run's own list of pre-publication checks, each backed by a measurement

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
