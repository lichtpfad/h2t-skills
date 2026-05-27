---
title: "Connector API P0 Release Evidence"
status: "accepted"
date: "2026-05-28"
milestone: "skills-release"
---

# Connector API P0 Release Evidence

Scope: final skills-release evidence after the connector API coverage backlog
closed.

## Summary

Connector API P0 is complete for the current release gate. Issues #212-#231
closed through six PRs merged into `main`.

| PR | Branch | Scope | Issues |
| --- | --- | --- | --- |
| #233 | `codex-p0-e2e-harness` | Opt-in connector E2E harness | None |
| #234 | `codex-p0-drive-api` | Drive upload upsert, trash/delete, metadata, Docs create/read/write improvements | #212-#218 |
| #235 | `codex-p0-gmail-api` | Gmail reply, forward, label create/delete | #219, #221, #225 |
| #236 | `codex-p0-notion-api` | Notion DB row create/update, archive, append/replace content | #220, #223, #227 |
| #237 | `codex-p0-telegram-api` | Telegram send-file, forward-message, delete-message | #222, #226, #229 |
| #238 | `codex-p0-calendar-meetgeek-api` | Calendar create-calendar/instances; MeetGeek action-items/date filters | #224, #228, #230, #231 |

`origin/main` head at verification time: `6cb7275 feat(calendar+meetgeek): add P0 API coverage (#238)`.

## Safety Review

The release-blocking review findings were fixed before merge:

| Surface | Risk | Final guard |
| --- | --- | --- |
| Drive upload | `--parent-id` claimed to replace `--folder`, but parser required `--folder` | Dispatch validates exactly one of `--folder` or `--parent-id` |
| Notion replace content | Failed block deletion could be swallowed before append | `replace_page_content_safe()` is fail-fast; append only runs after all deletes succeed |
| Telegram send/forward | File send and forward had no CLI guard | `send-file` requires `--confirm-send`; `forward-message` requires `--confirm-forward`; delete keeps `--confirm` |

Provider write/destructive live E2E remains manual-only unless explicitly
approved per command and resource. Automated E2E is opt-in and does not send,
forward, delete, archive, or create provider resources without explicit operator
consent.

## Verification

Commands run from `C:/dev/h2t-skills/.worktrees/pre-release-audit` on
2026-05-28.

| Command | Result | Notes |
| --- | --- | --- |
| `gh issue list --repo lichtpfad/h2t-skills --milestone skills-release --state open --limit 50` | PASS | Only #190 remained open |
| `gh pr checks 233..238 --repo lichtpfad/h2t-skills` | PASS | All six PRs had green `h2t-evals validate-repo` and `lib/ unit tests` before merge |
| `uv.exe run pytest tests/connectors tests/e2e/test_connector_api_coverage.py -q` | PASS | `799 passed in 6.53s`; E2E harness stayed opt-in/no-live-side-effects |
| `uv.exe run h2t-ops --help` | PASS | CLI includes `connectors`, `deploy`, `doctor`, Calendar, Drive, Gmail, MeetGeek, Notion, Research, Telegram |
| `uv.exe run h2t-ops connectors` | PASS | Seven connectors listed |
| `uv.exe run h2t-ops doctor --json` | PASS with known format nuance | Command exits 0 and reports CLI path, connectors, and credential presence; output is human text despite `--json` |
| `uv.exe run pytest -q` | NON-BLOCKING LOCAL ENV GAP | Full repo collection exits through `plugins/h2t-core/skills/init-project/scripts/apply_registration.py` because `ruamel.yaml` is absent from the local test env |

The full-repo `pytest -q` issue is not a connector P0 regression: the merged PR
CI path is green, connector tests pass, and the failure occurs during collection
of a h2t-core init-project script dependency outside the connector release
surface.

## Release Gate

Current skills-release status:

- Connector API P0: PASS.
- Research release substrate: PASS.
- Deploy skill/CLI: PASS.
- docs-lint enhancement: PASS.
- Pre-release audit #190: PASS after this report and
  `docs/reports/2026-05-27-skills-pre-release-audit.md` are merged.

Remaining accepted follow-up, not release-blocking:

- Legacy Telegram semantic workflows (`digest`, `tasks`, `research`,
  `students`, `sync`) are intentionally outside connector runtime. Recreate as
  portable workflow/POS work only if still needed.
- Full-repo test collection should be cleaned up separately by declaring
  `ruamel.yaml` in the correct dev dependency surface or making the script test
  skip gracefully when optional dependencies are missing.

## Verdict

`skills-release` can close after PR #232 lands with this evidence. No connector
API P0 issue remains open.
