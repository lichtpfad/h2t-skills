# Proposed additions to `C:/dev/docs/standards/branching.md`

Harvested practices that belong in the existing standard rather than a new one.

## Verify active branch before every commit

- **Evidence:** lineages crypto-regime-spike, h2t-skills · recurrence 2 · domain-indep high
- **Source:** `C:/dev/crypto-regime-spike/.claude/rules/git.md`, `C:/Users/stani/.claude/projects/C--dev-h2t-skills/memory/feedback_concurrent_chat_branch_hazard.md`
- **What to add:** Always run `git branch --show-current` immediately before staging and committing. A concurrent chat session or a parallel subagent can move HEAD under you without warning. If the active branch is not the expected one, stop and surface the conflict to the operator rather than committing to the wrong branch.

## Isolate destructive/bulk-rewrite operations on a separate branch, gate with empirical diff before committing

- **Evidence:** lineages quant-kb, crypto-regime-spike · recurrence 2 · domain-indep high
- **Source:** `C:/dev/quant-kb/.claude/rules/destructive-ops.md`, `C:/dev/crypto-regime-spike/.claude/rules/data-junction-cleanup.md`
- **What to add:** Any bulk rewrite, corpus mutation, or destructive refactor must be executed on an isolated branch. Before committing, run `git diff --stat`, eyeball 2–3 representative changed files, and pass lint. Never commit an unverified corpus mutation. If any gate fails, reset the branch rather than force-committing.
