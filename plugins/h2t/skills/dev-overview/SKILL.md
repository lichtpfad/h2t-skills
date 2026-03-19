---
name: dev-overview
description: "Cross-project dev dashboard: progress toward goals, activity status, open issues. Weekly review and planning tool. Triggers: 'dev overview', 'project overview', 'all projects', 'weekly review', 'где я нахожусь по проектам', 'h2t:dev-overview'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.1.0
---

# Dev Overview

Cross-project dashboard showing progress toward goals and movement across all active repos.
**Not a session tool** — use `h2t:dev-session-start` for that. This is a weekly/on-demand review.

## Data Sources

| Source | Purpose |
|--------|---------|
| `context/domains.yaml` | **Primary** — authoritative repo list (`github:` / `github_repos:` fields) |
| `~/.dor/sessions/*/` | **Secondary** — last focused date per repo (activity classification only) |

Planning lives in GitHub. Sessions track when *you* last worked on something.

## Procedure

### Step 1: Collect Repo List (GitHub-first)

Three-tier fallback — stop at the first tier that yields results:

**Tier 1 — domains.yaml** (if in DOR repo or DOR_ROOT is set):
```
Read context/domains.yaml
For each domain → for each project:
  if project has `github:` field      → add that single repo
  if project has `github_repos:` list → add all repos in the list
Result: deduplicated list of "owner/repo" strings
```

**Tier 2 — sessions** (if domains.yaml unavailable):
```bash
ls ~/.dor/sessions/*/*/ 2>/dev/null | xargs -I{} basename {} | sort -u
```
Then map folder names to GitHub remotes:
```bash
git -C ~/Projects/{repo} remote get-url origin 2>/dev/null
```
Skip repos with no GitHub remote.

**Tier 3 — gh repo list** (if no sessions either):
```bash
gh repo list lichtpfad --no-archived --source --json name,nameWithOwner --limit 100
```
Use `--source` to exclude forks. Filter out repos with 0 open issues and no commits in 90 days.

### Step 2: For Each Repo — Fetch GitHub State (parallel)

Run all API calls in parallel:

```bash
# Open milestones with issue counts
gh api repos/{owner}/{repo}/milestones \
  --jq '.[] | select(.state=="open") | {title, open: .open_issues, closed: .closed_issues}'

# Open issues
gh issue list --repo {owner}/{repo} \
  --state open --json number,title,labels --limit 20

# Last commit
gh api repos/{owner}/{repo}/commits \
  --jq '.[0] | {sha: .sha[:7], date: .commit.committer.date, msg: (.commit.message | split("\n")[0])}'
```

"Current milestone" = the open milestone with the most open issues.

### Step 3: Last Session Date (secondary)

For each repo name, find the most recent session file **across all machines**:

```bash
ls -t ~/.dor/sessions/*/{repo}/*.md 2>/dev/null | head -1
```

Extract date from filename (format: `YYYY-MM-DD` in filename).
If currently in an active session for this repo → treat as 0 days ago.

### Step 4: Classify Activity

Activity = last session date (when you focused), not last commit.

| Class | Condition |
|-------|-----------|
| 🟢 Active | Last session ≤ 3 days ago |
| 🟡 Slow | Last session 4–14 days ago |
| 🔴 Stalled | Last session > 14 days ago OR no sessions ever |

### Step 5: Build Progress Bar

```
progress = closed_issues / (open_issues + closed_issues)
bar = "█" * round(progress * 10) + "░" * (10 - round(progress * 10))
```

If no open milestone → show total open issues count, no bar.

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
- Sort within each class by: most open issues first (highest leverage).
- For repos from `github_repos:` list — show domain label in parentheses, e.g. "h2t-ai (hou2touch)".

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
| Read only mac/ sessions for repo discovery | Use domains.yaml github: fields as primary source |
| Read only mac/ sessions for activity | Use `~/.dor/sessions/*/` — all machines |
| Show handoff "What Remains" as tasks | Use GitHub open issues only |
| Fetch repos sequentially | Run all GitHub API calls in parallel |
| Omit repos with no milestone | Show total open issues count instead |
| Miss repos in github_repos: lists | Expand all lists, not just github: scalar fields |
