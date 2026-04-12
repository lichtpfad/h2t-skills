---
name: milestone-closure
description: This skill should be used when all issues in a GitHub milestone are closed and the phase is complete. Triggers on "close milestone", "milestone done", "phase complete", "закрыть milestone", or when the last issue in a milestone is closed.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Milestone Closure

Checklist for closing a development phase milestone. Ensures documentation, tests, and GitHub state are all consistent.

## When to Use

- All issues in a milestone are closed
- Phase work is complete and merged to main
- User says "close milestone" or "phase X complete"

## Procedure

### Step 1: Verify All Issues Closed

```bash
gh api repos/{owner}/{repo}/milestones/{number} --jq '{title, open_issues, closed_issues}'
```

**STOP if open_issues > 0.** List remaining issues and ask user what to do (close, move to next milestone, or defer).

### Step 2: Run Pre-Merge Check

Invoke `h2t-dev:pre-merge-check` if not already run. All gates must pass.

### Step 3: Write Phase Report

Create: `docs/reports/{plan-name}-report.md`

Report contains:
1. Link to plan and PR(s)
2. What was implemented (by task, with issue numbers)
3. Key architectural decisions made during the phase
4. List of changed files (summarized by area)
5. Candidates for next phase
6. Test coverage added

### Step 4: Update Project Docs

1. **roadmap.md:** Move phase from active to "Completed Phases" table
2. **CLAUDE.md:** Add phase to completed phases table with plan + report links

### Step 5: Close Milestone on GitHub

```bash
gh api repos/{owner}/{repo}/milestones/{number} -X PATCH -f state=closed
```

### Step 6: Session Handoff Note

Post a summary comment on the milestone (if supported) or on the last closed issue:

```bash
gh issue comment {last-issue-number} --body "Milestone closed: {milestone-title}
Report: docs/reports/{report-name}.md
All {closed_issues} issues resolved."
```

## Checklist Summary

- [ ] All milestone issues = closed
- [ ] `h2t-dev:pre-merge-check` = all gates pass
- [ ] Phase report written to `docs/reports/`
- [ ] `docs/roadmap.md` updated (phase → completed)
- [ ] `CLAUDE.md` updated (completed phases table)
- [ ] GitHub milestone state = closed
- [ ] Handoff comment posted

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Closing milestone with open issues | ALWAYS check open_issues count first |
| Forgetting the report | Report is MANDATORY per project rules (see CLAUDE.md) |
| Not updating roadmap.md | Roadmap must reflect current state |
| Skipping pre-merge check | Even if "everything works", run the gates |
