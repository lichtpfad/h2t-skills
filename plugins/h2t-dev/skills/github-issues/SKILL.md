---
name: h2t-dev:github-issues
description: This skill should be used when creating or updating GitHub issues. It enforces consistent issue structure with Context/What/Why/Part-of sections, correct labels (domain, phase, priority), and milestone assignment. Triggers on "create issue", "add to backlog", "github issue".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# GitHub Issue Template

## Issue Body Structure

Every issue MUST follow this structure:

```markdown
## Context

Where this decision came from (council, ADR, user request, bug report).
Reference source documents.

## What

Concrete description of what changes or gets built.
Include code snippets, schema examples, API signatures where relevant.

## Why

Product value. Why this matters for users or agents.
1-2 sentences max.

## Part of

- Phase X.Y — [Phase name] (#parent-issue if exists)
- ADR: `docs/adr-NNN-*.md` (if applicable)

## Depends on

- #N (issue title) — only if true dependency exists
```

## Labels (required)

**Canonical source:** bundled in `h2t-dev:docs-sync-labels` — see `references/labels-schema.md` in that skill for the full table. Load on demand: `${CLAUDE_PLUGIN_ROOT}/../docs-sync-labels/references/labels-schema.md`

Every issue MUST carry labels from at least these namespaces:

| Namespace | Required | Examples |
|-----------|----------|----------|
| `type:` | yes | `type:bug`, `type:feature`, `type:enhancement`, `type:refactor`, `type:docs`, `type:chore` |
| `priority:` | yes | `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3` |
| `domain:` | yes | `domain:skills`, `domain:infra`, `domain:docs`, `domain:content`, `domain:research` |
| `phase:` | optional | `phase:design`, `phase:implementation`, `phase:review` |
| `status:` | optional | `status:triage`, `status:blocked`, `status:wontfix`, `status:superseded` |

**Rules:**
- Always lowercase (`priority:p1`, never `priority:P1`)
- Check canonical `labels.json` for the full list before inventing new ones
- Sync a new label to all repos via `/docs-sync-labels` after adding it to canonical

## Milestone Assignment

| Phase | Milestone |
|-------|-----------|
| Phase 5 | `Phase 5: Knowledge Model + Context Engine` |
| Phase 6 | `Phase 6: Safe Copilot` |
| Phase 7 | `Phase 7: Power UX` |

Issues without a matching milestone: omit `--milestone`.

## gh CLI Pattern

```bash
gh issue create \
  --title "Short imperative title (<70 chars)" \
  --label "type:enhancement,priority:p1,domain:skills,phase:design" \
  --milestone "Phase 5: Knowledge Model + Context Engine" \
  --body "$(cat <<'EOF'
## Context
...
## What
...
## Why
...
## Part of
...
## Depends on
...
EOF
)"
```

## References

Load on demand when you need full naming/commit conventions:

- `${CLAUDE_PLUGIN_ROOT}/skills/github-issues/references/git-naming-conventions.md` — issue title format, commit types, branch naming, milestone format

## Common Mistakes

- Missing priority label (every issue needs one)
- Writing "What" without "Why" (context gets lost)
- Forgetting `--milestone` for Phase 5/6/7 issues
- Title too long or too vague
- Creating duplicate of existing issue (always check `gh issue list` first)

## Graph Integration

### Query (optional — if issue structure, labels, or milestones are unclear)

```bash
SKILL_GRAPH_DIR="${SKILL_GRAPH_DIR:-C:/dev/claude-agent-skills/lib}"
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli query \
  --context "github issues: structure, labels, milestones, gh cli usage" \
  --skill "github-issues") 2>/dev/null || true
```

If results contain relevant patterns or lessons, apply them before proceeding.

### Add Lesson (after resolving an error or unexpected behavior)

```bash
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli add-lesson \
  --skill "github-issues" \
  --trigger "<what broke — e.g. label not found, milestone mismatch>" \
  --resolution "<what fixed it>" \
  --session-id "$SESSION_NAME") 2>/dev/null || true
```
