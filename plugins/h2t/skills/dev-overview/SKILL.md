---
name: dev-overview
description: "Cross-project dev dashboard: progress toward goals, activity status, open issues. Weekly review and planning tool. Triggers: 'dev overview', 'project overview', 'all projects', 'weekly review', 'где я нахожусь по проектам', 'h2t:dev-overview'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Dev Overview

Cross-project dashboard showing progress toward goals and movement across all active repos.
**Not a session tool** — use `h2t:dev-session-start` for that. This is a weekly/on-demand review.

## Procedure

### Step 1: Discover Active Repos

Find repos with session history:

```bash
ls ~/.dor/sessions/*/*/ 2>/dev/null | xargs -I{} basename {} | sort -u
```

Also check `context/domains.yaml` if in DOR repo — it lists all tracked projects with GitHub links.

Collect: repo name → GitHub owner/repo mapping.
Skip repos with no GitHub remote or no sessions in last 90 days.

### Step 2: For Each Repo — Fetch GitHub State

Run in parallel for each repo:

```bash
# Milestones
gh api repos/{owner}/{repo}/milestones \
  --jq '.[] | select(.state=="open") | {title, open: .open_issues, closed: .closed_issues}'

# Open issues (current milestone)
gh issue list --repo {owner}/{repo} \
  --milestone "<current>" --state open \
  --json number,title,labels --limit 20

# Last commit
gh api repos/{owner}/{repo}/commits \
  --jq '.[0] | {sha: .sha[:7], date: .commit.committer.date, msg: .commit.message | split("\n")[0]}'
```

"Current milestone" = the one with most open issues.

### Step 3: Last Session Date

For each repo, find the most recent session file:

```bash
ls -t ~/.dor/sessions/*/{repo}/*.md 2>/dev/null | head -1
```

Extract date from filename or `## Meta → Date` field.

### Step 4: Classify Activity

| Class | Condition |
|-------|-----------|
| 🟢 Active | Last session ≤ 3 days ago |
| 🟡 Slow | Last session 4–14 days ago |
| 🔴 Stalled | Last session > 14 days ago OR no sessions |

### Step 5: Build Progress Bar

```
progress = closed_issues / (open_issues + closed_issues)
bar = "█" * round(progress * 10) + "░" * (10 - round(progress * 10))
```

### Step 6: Present Dashboard

```markdown
## Dev Overview — {DATE}

### 🟢 Active
{repo}   {bar}  {milestone} ({closed}/{total})   last: {N}d ago
  └─ Open: #{n} {title}, #{n} {title}...

### 🟡 Slow
{repo}   {bar}  {milestone} ({closed}/{total})   last: {N}d ago
  └─ Open: #{n} {title}...

### 🔴 Stalled
{repo}   {bar}  {milestone} ({closed}/{total})   last: {N}d ago
  └─ Open: #{n} {title}...

### 📊 Summary
- Total open issues: {N} across {M} repos
- Most progress: {repo} ({%}% milestone complete)
- Needs attention: {repo} (stalled {N} days)
```

**Rules:**
- Max 3 open issues shown per repo inline. Full list available on request.
- If repo has no open milestone — show total open issues count instead.
- If repo has no GitHub (local only) — skip GitHub columns, show sessions only.
- Sort within each class by: most open issues first (highest leverage).

### Step 7: Offer Next Action

After presenting dashboard, ask:

```
Хочешь:
1. Развернуть полный список issues по {repo}?
2. Запустить /h2t:dev-session-start для {most-active-repo}?
3. Посмотреть последний handoff по {stalled-repo}?
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Show all repos including archived | Only repos with sessions in last 90 days |
| Fetch repos sequentially | Run all GitHub API calls in parallel |
| Show handoff "What Remains" as tasks | Use GitHub open issues only |
| Omit repos with no milestone | Show total open issues instead |
