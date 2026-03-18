---
name: github-issues
description: Use when creating or updating GitHub issues. Enforces consistent issue structure with Context/What/Why/Part-of sections, correct labels (domain, phase, priority), and milestone assignment. Triggers on "create issue", "add to backlog", "github issue"., 'h2t:github-issues'
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

Every issue MUST have exactly 3 label types:

| Type | Options |
|------|---------|
| **domain:** | `domain:canvas`, `domain:knowledge`, `domain:context`, `domain:copilot`, `domain:subnetwork`, `domain:workspace`, `domain:validation` |
| **phase:** | `phase:5` through `phase:10` |
| **priority:** | `priority:P0` (Critical), `priority:P1` (High), `priority:P2` (Medium), `priority:P3` (Low/Future) |

Additional labels: `enhancement`, `bug`, `infra`, `icebox`, `superseded`

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
  --label "enhancement,phase:5,priority:P1,domain:context" \
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

## Common Mistakes

- Missing priority label (every issue needs one)
- Writing "What" without "Why" (context gets lost)
- Forgetting `--milestone` for Phase 5/6/7 issues
- Title too long or too vague
- Creating duplicate of existing issue (always check `gh issue list` first)
