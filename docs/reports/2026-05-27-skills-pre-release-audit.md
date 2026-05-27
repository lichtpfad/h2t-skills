---
title: "Skills Pre-release Audit"
status: "accepted"
date: "2026-05-27"
milestone: "skills-release"
---

# Skills Pre-release Audit

Issue: #190

Scope: read-only audit of active split plugins against the retired legacy
`plugins/h2t` skill sources. This report does not modify runtime behavior.

## Executive Summary

The split plugin pack is structurally releasable. The connector API P0 work
(#212-#231) has landed in `main` through PRs #233-#238. The legacy `h2t` plugin is no longer an active
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
| `plugins/h2t/skills/calendar` | `h2t-ops:connectors` + `references/calendar.md` | OK | Active surface is richer than legacy: calendars, list windows, search, get, create, update, RSVP, move, delete, freebusy, create-calendar, recurring instances. |
| `plugins/h2t/skills/gmail` | `h2t-ops:connectors` + `references/gmail.md` | OK | Active surface covers list/read/search/send/draft/labels/attachments/thread/trash/delete guardrails, reply, forward, label create/delete. |
| `plugins/h2t/skills/notion` | `h2t-ops:connectors` + `references/notion.md` | OK | Active surface covers get/blocks/search/get-database/workspace graph/find-databases/create/update/sync/comments, DB row create/update, archive, append/replace content. |
| `plugins/h2t/skills/telegram` | `h2t-ops:connectors` + `references/telegram.md` | Provider I/O OK; workflows degraded by design | Provider I/O is covered, including send-file, forward-message, and guarded delete-message. Legacy workflows `saved/digest/tasks/research/students/sync` are intentionally not connector operations and need a separate workflow/POS follow-up if still desired. |
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

No remaining release blocker was found in this audit after connector API P0
landed.

Release decisions accepted:

1. Connector API P0 plan landed: #212-#231 are closed.
2. Deprecated `h2t-dev:gh-memory` is accepted as deprecated and must not be
   promoted in release docs.
3. Legacy Telegram workflow loss is accepted for connector release because those
   flows cross into interpretation/POS workflow territory.

## Follow-up Recommendations

### Required Before Release

- Merge this audit/evidence PR.
- Verify marketplace/package build excludes retired `plugins/h2t` legacy plugin.
- Keep deprecated skills either hidden from active routing or clearly marked.

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

Release can proceed after this audit/evidence PR lands. The audit does not
identify a connector-blocking loss. The only accepted product delta is Telegram
workflows: do not announce full semantic parity with the old monolith unless
those workflows are recreated later as portable workflow/POS features.
