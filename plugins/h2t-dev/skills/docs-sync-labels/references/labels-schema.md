# Canonical Labels Schema (namespaced-v1)

Source of truth: `data/labels.json` (bundled). Sync to repos via `/h2t-dev:docs-sync-labels`.

## Rules
- Always lowercase (`priority:p1`, never `priority:P1`)
- Every issue MUST have: `type:*`, `priority:*`, `domain:*`
- Never invent new labels without adding to `data/labels.json` first

## type:
| Label | Description |
|-------|-------------|
| `type:bug` | Something is broken |
| `type:feature` | New functionality |
| `type:enhancement` | Improvement to existing |
| `type:refactor` | Code without behavior change |
| `type:docs` | Documentation |
| `type:chore` | CI, deps, config |

## priority:
| Label | Description |
|-------|-------------|
| `priority:p0` | Critical / blocking |
| `priority:p1` | Important |
| `priority:p2` | Next sprint |
| `priority:p3` | Backlog |

## domain:
| Label | Description |
|-------|-------------|
| `domain:skills` | Skill development and fixes |
| `domain:infra` | Infrastructure, frameworks, shared libs |
| `domain:docs` | Documentation standards and tooling |
| `domain:content` | Content production, courses, assets |
| `domain:research` | Research, experiments, prototypes |

## phase: (optional)
`phase:design` · `phase:implementation` · `phase:review`

## status: (optional)
`status:triage` · `status:blocked` · `status:wontfix` · `status:superseded`
