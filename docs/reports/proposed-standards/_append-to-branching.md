# Proposed additions to `C:/dev/docs/standards/branching.md`

## Verify active branch before every commit (concurrent-chat hazard)
- **Evidence:** lineages crypto-regime-spike, h2t-skills · recurrence 2 · domain-indep high
- **Source:** `C:/dev/crypto-regime-spike/.claude/rules/git.md`, `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/feedback_concurrent_chat_branch_hazard.md`
- **What to add:** Run `git branch --show-current` (or equivalent) before every commit. A parallel chat session or subagent can move HEAD while the current session is mid-task. If the branch does not match the expected working branch, stop, surface the conflict to the operator, and do not commit.

## Isolate destructive / bulk-rewrite operations on a dedicated branch
- **Evidence:** lineages quant-kb · recurrence 1 · domain-indep high
- **Source:** `C:/dev/quant-kb/.claude/rules/destructive-ops.md`
- **What to add:** Run destructive operations (bulk rename, corpus mutation, mass-delete) on an isolated branch. Before committing, gate with an empirical diff: `git diff --stat` + visual inspection of 2–3 representative files + lint pass. Never commit an unverified corpus mutation directly to the working branch.
