# Gate Rules

A gate may guard a **new outward mutation** — changing the user's configuration or
repository, sending, deleting, spending. It may never stand between work the session has
already produced and its persistence.

Both kinds write to storage the user owns, so "does it write?" does not separate them. What
separates them is whether the write creates a change or merely saves something that already
exists.

Handoff asked for a session name after composing a full summary: two merged PRs, five codex
rounds, 25 tests, a live-API disproof. The user was asleep. Nothing was written, and the
summary went with it (2026-08-23, fixed in #391). A wrong name costs one rename; an
unanswered question costs the session.

Where a value is missing, derive it, write, and say what you derived. Ask afterwards.

The invariant is enforced by review. `tests/core/test_handoff_no_prewrite_gate.py` is a
tripwire for the two phrasings that have actually appeared — it cannot prove the rule.

## Telling the two apart

`init-project` also asks before it writes, and that is correct: its write *is* the outward
action — entries in `~/.h2t/config/repo-mapping.yaml` and `domains.yaml`, and
`.claude/project-id` inside the user's repository. Nothing is lost if the answer never comes.

`handoff` is the other shape: the record is the work. The question stood between something
that existed only in the session and the only place it could survive.

Ask which one is true before adding a gate: *if the user never answers, what is lost?*
