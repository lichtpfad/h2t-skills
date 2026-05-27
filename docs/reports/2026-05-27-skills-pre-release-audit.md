---
title: "Skills Pre-release Audit"
status: "draft"
date: "2026-05-27"
milestone: "skills-release"
---

# Skills Pre-release Audit

Issue: #190

Scope: read-only audit of active split plugins against the retired legacy
`plugins/h2t` skill sources. This report does not modify runtime behavior.

## Executive Summary

The split plugin pack is structurally releasable after the active connector API
P0 work (#212-#231) lands. The legacy `h2t` plugin is no longer an active
marketplace plugin and has no `.claude-plugin/plugin.json`; its remaining
`SKILL.md` files function as archive/rollback source.

No critical legacy provider read/write capability appears silently lost for
Calendar, Gmail, Notion, Daily Brief, or Voice Eval. Telegram is the only notable
semantic loss: legacy Telegram included digest/tasks/research/students workflows,
while the current active `h2t-ops:connectors` surface intentionally keeps only
provider I/O and routes workflow interpretation to future portable/POS layers.

## Legacy Skill Mapping

| Legacy skill | Current equivalent | Status | Notes |
| --- | --- | --- | --- |
| `plugins/h2t/skills/calendar` | `h2t-ops:connectors` + `references/calendar.md` | OK, pending P0 gaps | Active surface is richer than legacy: calendars, list windows, search, get, create, update, RSVP, move, delete, freebusy. P0 plan adds create-calendar and recurring instances. |
| `plugins/h2t/skills/gmail` | `h2t-ops:connectors` + `references/gmail.md` | OK, pending P0 gaps | Active surface covers list/read/search/send/draft/labels/attachments/thread/trash/delete guardrails. P0 plan adds reply, forward, label create/delete. |
| `plugins/h2t/skills/notion` | `h2t-ops:connectors` + `references/notion.md` | OK, pending P0 gaps | Active surface covers get/blocks/search/get-database/workspace graph/find-databases/create/update/sync/comments. P0 plan adds DB row CRUD, archive, append/replace content. |
| `plugins/h2t/skills/telegram` | `h2t-ops:connectors` + `references/telegram.md` | Degraded by design | Provider I/O is covered or in P0 plan. Legacy workflows `saved/digest/tasks/research/students/sync` are intentionally not connector operations and need a separate workflow/POS follow-up if still desired. |
| `plugins/h2t/skills/daily-brief` | `h2t-ops:daily-brief` | OK | Active skill preserves the briefing workflow but adds POS boundary language and uses connector commands rather than legacy sibling scripts. |
| `plugins/h2t/skills/voice-eval` | `h2t-creative:voice-eval` | OK / duplicate archive | Current active skill is effectively the same capability in the correct creative plugin. Legacy copy is archive duplication. |

## Duplicate / Deprecated Entries

| Item | Classification | Recommendation |
| --- | --- | --- |
| `plugins/h2t/skills/*` | Archive duplicates | Keep only if the retired legacy plugin remains intentionally archived; do not include `plugins/h2t` in marketplace packaging. |
| `h2t-dev:gh-memory` | Deprecated active skill file | Release risk if deprecated skills are still discoverable. Either exclude from packaging or keep `status: deprecated` and ensure active plugin description does not route users to it. |
| `voice-eval` legacy vs `h2t-creative:voice-eval` | Duplicate archive | No action if legacy plugin is not packaged. |
| `daily-brief` legacy vs `h2t-ops:daily-brief` | Duplicate archive | No action if legacy plugin is not packaged. |

## Placement Audit

| Skill | Current plugin | Verdict |
| --- | --- | --- |
| `h2t-core:session-start`, `handoff`, `setup`, `agent-profile`, `init-project`, `scaffold-project`, `project-audit`, `dev-overview` | `h2t-core` | Correct: session/project lifecycle and context infrastructure. |
| `h2t-core:snap` | `h2t-core` | Acceptable: agent runtime utility. Could move to `h2t-tools` later, but no active `h2t-tools` plugin is present in this repo. |
| `h2t-ops:connectors`, `research`, `daily-brief`, `deploy` | `h2t-ops` | Correct: provider I/O and operational workflows. |
| `h2t-dev:docs-lint`, `github-issues`, `pre-merge-check`, `milestone-closure` | `h2t-dev` | Correct: development workflow. |
| `h2t-dev:gh-memory` | `h2t-dev` | Deprecated; ensure it is not prominent in release docs. |
| `h2t-creative:*` | `h2t-creative` | Correct: creative generation/design/voice. |
| `h2t-arch:*` | `h2t-arch` | Correct: architecture/diagram/node research. |
| `h2t-edu:*` | `h2t-edu` | Correct: education/transcript workflows. |

## Release Blockers

1. Connector API P0 plan must land: #212-#231.
2. Deprecated `h2t-dev:gh-memory` must be confirmed excluded from routing/release docs or explicitly accepted as deprecated.
3. Decide whether legacy Telegram workflow loss is acceptable for this release.

## Follow-up Recommendations

### Required Before Release

- Complete connector API coverage P0 (#212-#231).
- Verify marketplace/package build excludes retired `plugins/h2t` legacy plugin.
- Verify deprecated skills are either hidden from active routing or clearly marked.

### Suggested Follow-up Issue

Create a non-P0 follow-up if Telegram workflows are still valuable:

```markdown
Title: telegram workflows: extract legacy digest/tasks/research/students into portable workflow layer

Context:
Legacy `plugins/h2t/skills/telegram` included workflow commands that read
Telegram and wrote vault/Notion artifacts. The active `h2t-ops:connectors`
surface intentionally keeps Telegram as provider I/O only.

What:
Design and implement a portable workflow/POS-layer replacement for:
- saved messages -> learning artifact
- digest
- task extraction
- research channel extraction
- student group task extraction

Why:
Avoid silently losing useful legacy workflows while preserving the connector/POS
boundary.

Part of:
skills-release follow-up / POS workflow backlog.
```

## Release Recommendation

Do not release until #212-#231 land. After that, this audit does not identify a
second connector-blocking loss. The only product decision is Telegram workflows:
either accept their removal from the connector release or create a separate
workflow/POS follow-up before announcing parity with the old monolith.
