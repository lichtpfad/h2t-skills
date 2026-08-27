---
title: "Lesson lifecycle: three levels, two axes"
status: "draft"
owner: "lichtpfad"
date: "2026-08-27"
milestone: ""
issue: 447
---

# Lesson lifecycle: three levels, two axes

Design only. Nothing here is built. Decisions were settled in a brainstorm on 2026-08-27;
this records them so they survive compaction, and records what was measured so the same
ground is not re-explored.

**Issue:** #447 (wire practice_harvest as the rule-promotion mechanism)
**Related:** #439 (standards into the pack — the base level below), #445 (what carries
state between machines), #442 (a writer with no reader)

## Problem

A lesson learned in one repository is invisible in the next. On 2026-08-27 the same class
of defect — a half-finished migration, an assertion attached to the wrong representation —
was found seven times in one session, and the knowledge that would have prevented each
one existed already, in a file next to the decision rather than on its path.

There is no mechanism that notices repetition. `lib/practice_harvest/` was written to be
that mechanism and ran once, 2026-07-10.

## Constraint: ideality

The operator's frame is TRIZ: the function is performed, the mechanism does not exist.
Concretely, for this design:

- **No new skills.** Both halves attach to something already invoked.
- **No new stores.** Anything derivable is derived, not saved.
- **No discipline.** A step that has to be remembered is a step that stops, which is
  exactly what happened in July.

## Three levels

| level | location | carrier | what lands here |
|---|---|---|---|
| birth | `.claude/rules/*.md` in a repo | that repo's git | a lesson tied to one project |
| promotion | `~/.h2t/config/rules/*.md` | `lichtpfad/config` git | recurred across projects |
| base | pack `references/standards/` | pack release | what the author publishes |

The base is what a stranger receives: a seed, not a rule set to obey. Their own layer
grows above it from their own practice. This is why the layered shape was chosen over
shipping a copy they edit — see "Rejected" below.

## Two axes

Recurrence measured on one axis alone fails at both ends: a stranger with one project
never reaches a cross-project threshold, and the author's own count depends on which
checkouts happen to exist on the machine.

- **Cross-project.** A practice present in N>=2 registered repositories is a candidate for
  the user layer. Source of the repository list: `~/.h2t/config/repo-mapping.yaml`
  (31 entries, already read by the session-start hook). This is what `practice_harvest`
  already computes.
- **Within-project.** A correction the operator made in conversation is a candidate for
  that project's `.claude/rules/`. This axis exists so the loop turns for someone who has
  one repository, and because it is the axis that fires first: the seven cases on
  2026-08-27 came from one session, not three projects.

## Two phases

The split already exists in `lib/practice_harvest/` and in `llm-kb-template`'s
`docs/pipeline-principles.md`, which states it as a hard rule: "scripts are pure
bookkeeping; every LLM call goes through the agent's Agent/Workflow tools". What is
missing is that the cheap half never runs.

**Phase A — deterministic, rides `handoff`.** Python, no model, milliseconds:

- filter the session transcript to `type == "user"` text blocks;
- `git log` over `.claude/rules/` for churn.

**Phase B — interpretive, weekly or on demand.** Reads only Phase A's output and proposes.

## Measurements that shaped this

Each of these closed an option. They are recorded because re-measuring them costs more
than reading them.

**Transcripts are cheap to reduce.** `~/.claude/projects/<path-slug>/<uuid>.jsonl`, one JSON
object per event. Measured on this machine: 14 projects, 188 MB. In one session, 1331
lines — 161 `tool_use`, 343 assistant blocks, and **5** `user::text`. The operator's own
messages are ~1.5% of the file, so the interpretive phase reads almost nothing.

**Tool errors are not the signal.** Across 15 sessions of this project: 38 `is_error`
results, 37 of them unique. Exactly one string repeats, and it is `Exit code 1`.

**And the signal is not there in principle, not just in this sample.** None of the seven
defects found on 2026-08-27 produced a tool error. The blind test printed `4 passed`. The
surrogate bug exited 0. A dead `monkeypatch` sat in a green suite for months. A lesson is
born where everything looked healthy and was wrong — the scanner must look for the
operator correcting the output, not for a failing tool.

**`file-history-snapshot` is not a source either.** `trackedFileBackups` was empty for the
whole session, because edits went through Bash rather than the Edit tool.

**Promotion is an outward mutation.** By `.claude/rules/gates.md` it proposes and waits;
it never writes into the user's configuration unasked. If the answer never comes, nothing
is lost — which is the test that rule gives for whether a gate belongs.

## Rejected, with the reason

**Routing lessons into `agentic-kb`.** The chain already ran end to end:
`practice_harvest` produced 40 findings over 2026-06-10…07-10 across three repositories,
those seeded `agentic-kb/data/seed-registry.json`, and the judge council scored them —
`verification-gates` 1 PASS of 9, `autonomous-run` 0 of 4, `subagent-orchestration` 0 of 2.
**One claim out of fifteen survived**, and the pipeline stopped there on 2026-07-11.

The council was right by its own rules. `llm-kb-template`'s trust model is convergence of
independent sources: `single_source -> HYPOTHESIS`, and its README states the purpose as
stopping "one blog said so" from becoming an architectural fact. A practice found in three
of the author's own repositories has one source — the author, repeated. It can never be
`replicated`. The repository description already carries the finding in its own title:
*recurrence = signal not truth*.

What the council cannot weigh is the other kind of evidence. The rule added to
`.claude/rules/verification.md` on 2026-08-27 was not read in three places; it was
measured — revert the fix, observe red, restore. That is an experiment with a positive
control, not a citation. On the convergence scale it is a single source and scores lowest;
on reproducibility it scores highest.

So: `agentic-kb` keeps external methodology knowledge under its current council. Practice
measured in one's own session goes to the standards layer under a different criterion —
a reproducible measurement, not converging sources. One input, two channels, and
`practice_harvest` already distinguishes them: `lineage_sources` says whether three hits
are three repositories of one author or three independent ones.

**Amending the council with a reproducibility lens** was the alternative and was rejected
on cost: `llm-kb-template` is not a draft, three knowledge bases are instantiated from it
(`agentic-kb`, `quant-kb`, `research-kb`), and changing its trust model for one case
touches all three.

**Shipping standards as a copy the stranger edits** was rejected because it has no
promotion target: eight files they edit by hand, no layer, and the author's improvements
never reach them.

## Open

- What surfaces a Phase B proposal, exactly: a briefing section, or something narrower.
- Whether within-project correction detection is affordable at the cadence chosen, given
  it is the interpretive half.
- `~/.h2t/config` currently drifts — 5 modified and 6 untracked files uncommitted as of
  2026-08-27. Promotion writes there, so the carrier has to be reliable first (#447).
