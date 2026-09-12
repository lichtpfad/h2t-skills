---
name: github-issues
description: This skill should be used when creating or updating GitHub issues. The issue contract itself lives in the repository's issue forms; this skill covers what the forms cannot — sizing, labels, milestones, duplicate check, and the gh command shape. Triggers on "create issue", "add to backlog", "github issue".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# GitHub issues

## The body structure is not defined here

It lives in the target repository's issue forms — read them before creating anything:

- `.github/ISSUE_TEMPLATE/task.yml` — a unit of work
- `.github/ISSUE_TEMPLATE/decision.yml` — an irreversible choice: named options with consequences for a human to pick, never a finished document to approve

The forms' field labels ARE the required section headings. Do not restate them in this skill,
in a repo CLAUDE.md, or in a plan: one contract, one home.

## The CLI bypasses the form — mirror it by hand

`gh issue create` does not apply issue forms; they bind only in the browser. The `issue-fields`
workflow therefore checks every new issue for the form's section headings and for labels from
`type:` / `priority:` / `domain:`, and marks it `status:needs-fields` until the contract is complete.
When creating from the terminal, write the body with the same `###` headings the form produces.

## Sizing — decide this before writing the body

- **One issue = one checkable acceptance criterion.** Two independent criteria → two issues.
  No criterion at all → it is not an issue: it is a decision or a research case.
- **An issue must fit one agent session.** Work that outlives a session goes into a plan under
  `docs/superpowers/plans/` and the issue becomes one of its steps. If context was compacted
  while the task ran, the task was too big — regardless of any estimate made up front.
- **Budget:** intent ~300 tokens, the whole body ~1500 (~4 KB). A body far above that usually means
  a decision or a plan was swallowed into the task; move it to `decision.yml` or to a plan.
- **An irreversible decision is not an issue.** Domain unit and its key, the source-of-truth map,
  storage choice, lifecycle and failure semantics, an external contract — these get `decision.yml`
  first, and the work issue links to the resulting ADR.

## Labels (required)

**Canonical source:** bundled in `h2t-dev:docs-sync-labels` — see `references/labels-schema.md` in that
skill for the full table. Load on demand: `$(h2t-dev root)/skills/docs-sync-labels/references/labels-schema.md`

| Namespace | Required | Examples |
|-----------|----------|----------|
| `type:` | yes | `type:bug`, `type:feature`, `type:enhancement`, `type:refactor`, `type:docs`, `type:chore`, `type:decision` |
| `priority:` | yes | `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3` |
| `domain:` | yes | `domain:skills`, `domain:infra`, `domain:docs`, `domain:content`, `domain:research` |
| `phase:` | optional | `phase:design`, `phase:implementation`, `phase:review` |
| `status:` | optional | `status:triage`, `status:blocked`, `status:wontfix`, `status:superseded` |

Always lowercase. Check canonical `labels.json` before inventing a new one, and sync it to all repos
via `/docs-sync-labels` after adding it.

## Milestone

| Phase | Milestone |
|-------|-----------|
| Phase 5 | `Phase 5: Knowledge Model + Context Engine` |
| Phase 6 | `Phase 6: Safe Copilot` |
| Phase 7 | `Phase 7: Power UX` |

No matching phase → omit `--milestone`.

## gh pattern

Check for a duplicate first, then create with the body in a file:

```bash
gh issue list --repo <owner>/<repo> --search "<keywords>" --state all --limit 10
gh issue create --repo <owner>/<repo> \
  --title "<type>: short imperative title (<70 chars)" \
  --label "type:bug,priority:p2,domain:skills" \
  --body-file <path in the session scratchpad>
```

Never `--body "$(cat <<'EOF' … EOF)"`. A compound command always needs manual approval, and the
user-level CLAUDE.md forbids heredoc inside a Bash call. Write the body to a scratchpad file and
pass `--body-file`.

## Closing

An issue closes by a commit carrying `fixes #N` / `closes #N`, never by a comment saying it is done.

## References

- `$(h2t-dev root)/references/standards/git-naming-conventions.md` — issue title format, commit types,
  branch naming, milestone format

## Common mistakes

- Restating the form's fields here or in a repo doc instead of linking to the form
- Creating an issue for work that needs an irreversible decision first
- Missing a `priority:` label, or a label in the wrong case
- A title that names an activity instead of the outcome
- Creating a duplicate — always run `gh issue list --search` first
