---
title: "h2t-ops Connectors Skill Surface Implementation Plan"
status: "draft"
date: "2026-05-23"
milestone: ""
---
# h2t-ops Connectors Skill Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace six h2t-ops provider connector skills with one short `h2t-ops:connectors` navigator skill plus lazy connector references, while keeping `research` and `daily-brief` separate.

**Architecture:** Add a new navigator skill under `plugins/h2t-ops/skills/connectors/` with a portable Claude/Codex-compatible core, connector references, and one shared issue policy. Keep old per-connector skills during the first smoke gate, then remove them only after navigator routing passes representative tests. Do not move h2t-ops into h2t-core and do not change provider connector runtime code. Updating the h2t-core runtime skill index hook is allowed only to replace retired per-connector skill names with `h2t-ops:connectors`.

**Tech Stack:** Claude Code plugin skills, Markdown references, Python/pytest surface tests, `h2t-ops` CLI smoke commands, GitHub issue workflow.

---

## File Structure

### New Files

- `plugins/h2t-ops/skills/connectors/SKILL.md`
  - Short router for Calendar, Gmail, Drive, Notion, Telegram, and MeetGeek provider I/O.
  - Inline safety boundary, mini-index, reference-loading rules, issue capture workflow.
  - Under 200 lines.

- `plugins/h2t-ops/skills/connectors/references/calendar.md`
  - Calendar intent map, safety matrix, commands, auth notes, common failures.

- `plugins/h2t-ops/skills/connectors/references/gmail.md`
  - Gmail intent map, read/write safety, commands, auth notes, common failures.

- `plugins/h2t-ops/skills/connectors/references/drive.md`
  - Drive intent map, upload-folder guidance, commands, auth notes, common failures.

- `plugins/h2t-ops/skills/connectors/references/notion.md`
  - Notion intent map, workspace graph and embedded DB commands, write safety.

- `plugins/h2t-ops/skills/connectors/references/telegram.md`
  - Telegram provider I/O map and explicit workflow exclusions.

- `plugins/h2t-ops/skills/connectors/references/meetgeek.md`
  - MeetGeek meeting/transcript command map and recovery boundary notes.

- `plugins/h2t-ops/skills/connectors/references/issue-policy.md`
  - Shared connector bug/feature issue policy and privacy checklist.

- `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py`
  - Surface tests for file presence, line budgets, non-scope boundaries, issue policy, and final skill inventory.

### Modified Files

- `plugins/h2t-ops/.claude-plugin/plugin.json`
  - Patch bump after final surface change.

- `.claude-plugin/marketplace.json`
  - Patch bump for h2t-ops after final surface change.

- `docs/h2t-ops-roadmap.md`
  - Update #161 status after smoke and deletion.

### Retired Skill Entrypoints After Smoke Gate

Delete only the visible connector `SKILL.md` entrypoints after Task 5 live
navigator smoke passes. Keep legacy scripts/tests that are still callable from
the CLI or other workflows.

- `plugins/h2t-ops/skills/calendar/SKILL.md`
- `plugins/h2t-ops/skills/drive/SKILL.md`
- `plugins/h2t-ops/skills/gmail/SKILL.md`
- `plugins/h2t-ops/skills/meetgeek/SKILL.md`
- `plugins/h2t-ops/skills/notion/SKILL.md`
- `plugins/h2t-ops/skills/telegram/SKILL.md`

Keep:

- `plugins/h2t-ops/skills/connectors/`
- `plugins/h2t-ops/skills/research/`
- `plugins/h2t-ops/skills/daily-brief/`

---

### Task 0: Baseline Inventory And CLI Help Smoke

**Files:**
- Read: `plugins/h2t-ops/skills/*/SKILL.md`
- Read: `plugins/h2t-ops/.claude-plugin/plugin.json`
- Read: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Confirm current h2t-ops skill inventory**

Run:

```powershell
Get-ChildItem plugins/h2t-ops/skills -Directory |
  Select-Object -ExpandProperty Name
```

Expected output includes exactly these active skill directories before #161:

```text
calendar
daily-brief
drive
gmail
meetgeek
notion
research
telegram
```

- [ ] **Step 2: Count current skill lines**

Run:

```powershell
Get-ChildItem plugins/h2t-ops/skills -Directory | ForEach-Object {
  $skill = Join-Path $_.FullName 'SKILL.md'
  if (Test-Path $skill) {
    $lines = (Get-Content $skill | Measure-Object -Line).Lines
    [PSCustomObject]@{Skill=$_.Name; Lines=$lines}
  }
} | Format-Table -AutoSize
```

Expected: line counts are printed for `calendar`, `drive`, `gmail`, `meetgeek`, `notion`, `telegram`, `research`, and `daily-brief`.

- [ ] **Step 3: Verify CLI help stays lazy and credential-free**

Run:

```powershell
uv.exe run h2t-ops --help
uv.exe run h2t-ops connectors
uv.exe run h2t-ops calendar --help
uv.exe run h2t-ops gmail --help
uv.exe run h2t-ops drive --help
uv.exe run h2t-ops notion --help
uv.exe run h2t-ops telegram --help
uv.exe run h2t-ops meetgeek --help
uv.exe run h2t-ops research --help
```

Expected: every command exits 0 and prints help/listing without requiring provider credentials.

- [ ] **Step 4: Record baseline result in implementation notes**

Record these facts in the task log or PR body:

```text
Baseline h2t-ops skill dirs: calendar, daily-brief, drive, gmail, meetgeek, notion, research, telegram.
Baseline CLI help smoke passed for h2t-ops and all migrated connectors.
Per-connector skills still exist before navigator experiment.
```

---

### Task 1: Add Failing Surface Tests

**Files:**
- Create: `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py`

- [ ] **Step 1: Create the failing test file**

Create `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py` with:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT.parents[1]
REQUIRED_REFERENCES = {
    "calendar.md",
    "gmail.md",
    "drive.md",
    "notion.md",
    "telegram.md",
    "meetgeek.md",
    "issue-policy.md",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_connectors_skill_exists_and_is_bounded():
    skill = ROOT / "SKILL.md"
    assert skill.is_file()
    text = _text(skill)
    lines = text.splitlines()
    assert "name: h2t-ops:connectors" in text
    assert len(lines) <= 200
    assert "h2t-ops:research" in text
    assert "daily-brief" in text
    assert "Do not use raw provider APIs" in text
    assert "CLAUDE_PLUGIN_ROOT" not in text
    assert "CLAUDE_SKILL_DIR" not in text


def test_connector_references_exist():
    refs = ROOT / "references"
    assert refs.is_dir()
    found = {path.name for path in refs.glob("*.md")}
    assert REQUIRED_REFERENCES <= found


def test_issue_policy_contains_privacy_checklist():
    policy = _text(ROOT / "references" / "issue-policy.md")
    assert "No tokens/API keys/cookies/session files" in policy
    assert "No raw email bodies, transcripts, calendar descriptions, chat text" in policy
    assert "type:bug|feature" in policy
    assert "h2t-ops" in policy


def test_connector_references_have_required_sections():
    for name in REQUIRED_REFERENCES - {"issue-policy.md"}:
        text = _text(ROOT / "references" / name)
        assert "## Intent Map" in text, name
        assert "## Safety" in text, name
        assert "## Commands" in text, name
        assert "## Auth" in text, name
        assert "## Common Failures" in text, name


def test_final_skill_inventory_after_deprecation_gate():
    active = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    assert active == {"connectors", "daily-brief", "research"}
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q
```

Expected: FAIL because `plugins/h2t-ops/skills/connectors/SKILL.md` and references do not exist.

- [ ] **Step 3: Do not commit failing tests yet**

Leave the tests unstaged until Tasks 2, 3, and 6 make them pass.

---

### Task 2: Add Navigator Skill And Issue Policy

**Files:**
- Create: `plugins/h2t-ops/skills/connectors/SKILL.md`
- Create: `plugins/h2t-ops/skills/connectors/references/issue-policy.md`

- [ ] **Step 1: Create the connector navigator skill**

Create `plugins/h2t-ops/skills/connectors/SKILL.md` with:

```markdown
---
name: h2t-ops:connectors
description: "Navigator for h2t-ops provider I/O connectors: Calendar, Gmail, Drive, Notion, Telegram, and MeetGeek. Use when the user asks which connector command to run, asks for provider data/actions, or hits missing connector functionality. Research and daily-brief are intentionally separate."
compatibility: "Claude Code plugin skill with Codex/AGENTS-compatible portable core."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops Connectors

Provider I/O router for `h2t-ops`.

Use this skill for:

- Google Calendar events, availability, and event writes;
- Gmail search, read, draft, send, and labels;
- Google Drive list, search, download, export, upload, and upload-folder;
- Notion pages, blocks, databases, workspace search, graph, and sync;
- Telegram auth, dialogs, messages, saved messages, mentions, and bootstrap;
- MeetGeek teams, meetings, transcripts, summaries, highlights, insights, recording URLs, and submit-url.

Do not use this skill for:

- `h2t-ops:research`;
- `h2t-ops:daily-brief`;
- Telegram digest/tasks/research/students workflows;
- meeting interpretation or POS transcript intake;
- POS/DOR journal, vault, lake, or database writes.

## Safety Boundary

- Use the `h2t-ops` CLI for provider I/O.
- Do not use raw provider APIs when a connector command is missing.
- Missing provider functionality becomes a structured GitHub issue.
- Do not include secrets, tokens, OAuth codes, cookies, private message bodies, transcript bodies, calendar descriptions, or raw provider payloads in issues or final output.
- Write paths require explicit user intent.
- Paid provider checks belong to `h2t-ops:research`, not this skill.
- POS/DOR canonical state writes are out of scope.

## Router

| User intent | Connector | Load reference | CLI prefix |
| --- | --- | --- | --- |
| calendar, schedule, events, availability, FreeBusy, Google Meet links | Calendar | `references/calendar.md` | `h2t-ops calendar` |
| email, inbox, Gmail search, read, draft, send, labels | Gmail | `references/gmail.md` | `h2t-ops gmail` |
| Drive files, folders, Docs export, download, upload, upload folder | Drive | `references/drive.md` | `h2t-ops drive` |
| Notion pages, blocks, databases, workspace graph, embedded DBs | Notion | `references/notion.md` | `h2t-ops notion` |
| Telegram auth, dialogs, messages, saved messages, mentions | Telegram | `references/telegram.md` | `h2t-ops telegram` |
| MeetGeek meetings, transcripts, summaries, recordings | MeetGeek | `references/meetgeek.md` | `h2t-ops meetgeek` |

## Workflow

1. Identify the provider and whether the user requested a read or write.
2. Load only the matching reference file.
3. Prefer JSON output for agent processing: add `--json` when supported.
4. For write commands, restate the intended write and require explicit user approval unless the user already gave clear write intent.
5. Run the `h2t-ops` command.
6. Summarize results without dumping private provider bodies.
7. If the command does not exist or provider behavior is wrong, use `references/issue-policy.md`.

## Preflight

Use these when the environment is unclear:

```bash
h2t-ops --version
h2t-ops doctor
h2t-ops connectors
```

For credential readiness, prefer the installed setup skill:

```text
/h2t-core:setup connectors-check
```

## Output Policy

- Provide concise human summaries.
- Keep provider IDs and artifact refs when useful.
- Do not paste raw emails, chat logs, transcripts, calendar descriptions, or private Notion content unless the user explicitly asks to inspect that content.
- For POS-relevant findings, emit a proposed capture rather than writing POS state directly.

## References

- `references/calendar.md`
- `references/gmail.md`
- `references/drive.md`
- `references/notion.md`
- `references/telegram.md`
- `references/meetgeek.md`
- `references/issue-policy.md`

## Codex / AGENTS Adapter

The portable core is the Safety Boundary, Router, Workflow, Preflight, and Output Policy sections. In Codex or AGENTS.md contexts, treat this file as repo guidance and call the same `h2t-ops` CLI commands. Claude Code frontmatter is optional metadata and is not required for the routing logic.
```

- [ ] **Step 2: Create shared issue policy**

Create `plugins/h2t-ops/skills/connectors/references/issue-policy.md` with:

```markdown
# Connector Issue Policy

Use this policy when an h2t-ops connector command is missing, returns the wrong shape, fails with a provider bug, or forces an agent toward raw provider API code.

## Bug vs Feature

- Bug: a documented `h2t-ops CONNECTOR VERB` command exists but fails, returns the wrong output shape, leaks raw errors, or violates the connector boundary.
- Feature: a useful provider operation is not exposed by `h2t-ops`.

## Never Include

- secrets, tokens, OAuth codes, cookies, session files;
- raw email bodies, transcripts, calendar descriptions, chat text;
- private Notion page bodies or private Drive document bodies;
- full provider JSON payloads containing personal data;
- personal emails, phone numbers, client names, or private file paths unless the user explicitly approves and the data is already public.

## Allowed Evidence

- connector name;
- command name;
- installed/local CLI source;
- operating system class;
- exit code;
- typed error class;
- sanitized error message;
- redacted JSON envelope shape;
- synthetic examples;
- artifact refs without raw content.

## Issue Template

```md
## Context

- Connector:
- Command:
- Environment: Windows/macOS/Linux
- CLI source: installed/local/dev
- Read or write path:

## Expected

Behavior without private payloads.

## Actual

- Exit code:
- Error class:
- Sanitized message:

## Repro

`h2t-ops CONNECTOR VERB --json`

## Evidence

- CLI version:
- Connector:
- Redacted envelope:
- Artifact refs only, no raw content:

## Privacy Review

- [ ] No tokens/API keys/cookies/session files
- [ ] No raw email bodies, transcripts, calendar descriptions, chat text
- [ ] No personal emails/phone numbers/client names unless already public
- [ ] IDs are truncated or generalized where possible
- [ ] Local paths contain no private project/person names, or are generalized

## Classification

type:bug|feature
priority:p?
domain:skills
phase:triage
```

## Command

Use GitHub CLI only after the issue body passes the privacy review:

```bash
gh issue create --repo lichtpfad/h2t-skills --title "h2t-ops CONNECTOR: short issue title" --body-file issue-body.md --label domain:skills --label phase:triage
```

If unsure whether evidence is private, do not create the issue automatically. Show the sanitized issue draft to the user first.
```

- [ ] **Step 3: Run tests and confirm reference tests still fail**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q
```

Expected: FAIL because the six connector reference files do not exist yet and old connector `SKILL.md` entrypoints still exist.

---

### Task 3: Add Connector Reference Files

**Files:**
- Create: `plugins/h2t-ops/skills/connectors/references/calendar.md`
- Create: `plugins/h2t-ops/skills/connectors/references/gmail.md`
- Create: `plugins/h2t-ops/skills/connectors/references/drive.md`
- Create: `plugins/h2t-ops/skills/connectors/references/notion.md`
- Create: `plugins/h2t-ops/skills/connectors/references/telegram.md`
- Create: `plugins/h2t-ops/skills/connectors/references/meetgeek.md`

- [ ] **Step 1: Create Calendar reference**

Create `plugins/h2t-ops/skills/connectors/references/calendar.md` with:

```markdown
# Calendar Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list calendars | `h2t-ops calendar calendars --json` |
| list events | `h2t-ops calendar list --days 1 --max 250 --json` |
| explicit date window | `h2t-ops calendar list --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --max 250 --json` |
| busy windows | `h2t-ops calendar freebusy --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --json` |
| search events | `h2t-ops calendar search "meeting" --max 20 --json` |
| get event | `h2t-ops calendar get EVENT_ID_FROM_LIST --json` |
| create timed event | `h2t-ops calendar create "Planning" 2026-05-23 14:00 --duration-min 60 --json` |
| create all-day event | `h2t-ops calendar create "Travel" 2026-05-23 --all-day --json` |
| update event | `h2t-ops calendar update EVENT_ID_FROM_LIST --summary "Updated title" --json` |
| delete event | `h2t-ops calendar delete EVENT_ID_FROM_LIST --confirm --json` |

## Safety

- Listing, searching, getting, and FreeBusy are read-only.
- Create, update, and delete require explicit user intent.
- Do not infer attendees, recurrence, reminders, or Google Meet links unless the user asks.
- Do not paste private calendar descriptions into GitHub issues.

## Commands

Use JSON for agent processing:

```bash
h2t-ops calendar calendars --json
h2t-ops calendar list --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --max 250 --busy-only --json
h2t-ops calendar freebusy --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --json
h2t-ops calendar create "Planning" 2026-05-23 14:00 --duration-min 60 --meet --json
```

## Auth

Google OAuth credentials and tokens are expected under `~/.config/google-calendar-mcp/`.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- Missing token: run Google OAuth setup before Calendar commands.
- Timezone error on Windows: ensure `tzdata` is installed in the `h2t-ops` environment.
- Delete without `--confirm`: command should fail instead of deleting.
```

- [ ] **Step 2: Create Gmail reference**

Create `plugins/h2t-ops/skills/connectors/references/gmail.md` with:

```markdown
# Gmail Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list recent messages | `h2t-ops gmail list --max 10 --json` |
| search mail | `h2t-ops gmail search "from:example@example.com newer_than:7d" --max 10 --json` |
| read message | `h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json` |
| list labels | `h2t-ops gmail labels --json` |
| create draft | `h2t-ops gmail draft --to person@example.com --subject "Subject" --body "Body" --json` |
| send email | `h2t-ops gmail send --to person@example.com --subject "Subject" --body "Body" --json` |
| modify labels | `h2t-ops gmail label MESSAGE_ID_FROM_SEARCH --add LabelName --json` |

## Safety

- List, search, read, and labels are read-only.
- Draft, send, and label modification require explicit user intent.
- Prefer draft over send when user intent is ambiguous.
- Do not include raw email bodies, addresses, or private snippets in GitHub issues.

## Commands

```bash
h2t-ops gmail list --max 10 --json
h2t-ops gmail search "subject:invoice newer_than:30d" --max 10 --json
h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json
h2t-ops gmail draft --to person@example.com --subject "Follow-up" --body "Draft body" --json
```

## Auth

Gmail reuses Google OAuth credentials under `~/.config/google-calendar-mcp/` or `~/.config/gmail/`.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- Missing OAuth token: run Google OAuth setup.
- Expired token: refresh OAuth through the configured Google auth flow.
- Write command ambiguity: create a draft unless the user explicitly says send.
```

- [ ] **Step 3: Create Drive reference**

Create `plugins/h2t-ops/skills/connectors/references/drive.md` with:

```markdown
# Drive Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list files | `h2t-ops drive list --max 20 --json` |
| search files | `h2t-ops drive search "presentation" --max 20 --json` |
| list folders | `h2t-ops drive folders --json` |
| download file | `h2t-ops drive download FILE_ID_FROM_SEARCH --dest ./downloads --json` |
| export Google Doc | `h2t-ops drive export FILE_ID_FROM_SEARCH --format md --dest ./export.md --json` |
| upload one file | `h2t-ops drive upload ./presentation.html --folder "Uploads" --no-convert --json` |
| upload folder | `h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json` |

## Safety

- List, search, folders, download, and export are read-only from Drive's perspective.
- Upload and upload-folder write to Drive and require explicit user intent.
- Run `upload-folder --dry-run --json` before a real recursive upload.
- Do not write ad-hoc Google Drive API scripts when a command is missing; use `issue-policy.md`.

## Commands

```bash
h2t-ops drive search "lecture" --max 20 --json
h2t-ops drive export FILE_ID_FROM_SEARCH --format md --dest ./lecture.md --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --update-existing --json
```

## Auth

Drive uses the same Google OAuth token family as Gmail and Calendar.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- Ambiguous folder name: use `upload-folder --parent-id` or inspect folders first.
- Existing same-name file: default is skip; use `--update-existing` only when replacement is intended.
- Cloud HTML deployment: preserve relative paths with `upload-folder`, not single-file upload.
```

- [ ] **Step 4: Create Notion reference**

Create `plugins/h2t-ops/skills/connectors/references/notion.md` with:

```markdown
# Notion Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| get page as markdown | `h2t-ops notion get PAGE_ID --format md` |
| get page blocks | `h2t-ops notion blocks PAGE_ID --json` |
| query/filter database | `h2t-ops notion search DATABASE_ID --limit 25 --json` |
| get database items | `h2t-ops notion get-database DATABASE_ID --limit 25 --json` |
| search workspace | `h2t-ops notion search-workspace --object all --limit 25 --json` |
| graph page tree | `h2t-ops notion graph PAGE_ID --max-depth 3 --json` |
| find embedded databases | `h2t-ops notion find-databases PAGE_ID --json` |
| create page | `h2t-ops notion create --parent PAGE_ID --title "Title" --body "Body" --json` |
| update page | `h2t-ops notion update PAGE_ID --title "Updated title" --json` |
| sync page to markdown | `h2t-ops notion sync PAGE_ID --dest ./notion-page.md --json` |

## Safety

- Get, blocks, database reads, search-workspace, graph, and find-databases are read-oriented.
- Sync reads from Notion but writes a local file; require explicit destination intent.
- Create and update are provider writes and require explicit user intent.
- Notion writes execute provider-specific writes only; POS/coordinator owns the decision to accept tasks, journal entries, or KB promotions.
- Do not include private Notion page bodies in GitHub issues.

## Commands

```bash
h2t-ops notion search-workspace --object all --limit 25 --json
h2t-ops notion graph PAGE_ID --max-depth 3 --json
h2t-ops notion find-databases PAGE_ID --json
h2t-ops notion search DATABASE_ID --limit 25 --json
h2t-ops notion get-database DATABASE_ID --limit 25 --json
```

## Auth

Notion expects `NOTION_API_TOKEN` from environment, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, legacy `~/.dor/secrets.env`, or `~/.config/notion/token`.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- Search returns no databases but page contains child databases: use `find-databases PAGE_ID`.
- Permission error: share the Notion page/database with the integration.
- Task creation request: confirm whether the user wants a Notion provider write or a POS/coordinator proposal.
```

- [ ] **Step 5: Create Telegram reference**

Create `plugins/h2t-ops/skills/connectors/references/telegram.md` with:

```markdown
# Telegram Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth status | `h2t-ops telegram auth status --json` |
| request login code | `h2t-ops telegram auth request-code --phone +10000000000 --json` |
| complete login | `h2t-ops telegram auth complete --phone +10000000000 --code 12345 --json` |
| list dialogs | `h2t-ops telegram dialogs --limit 20 --json` |
| list folders | `h2t-ops telegram folders --json` |
| read messages | `h2t-ops telegram messages ENTITY_FROM_DIALOGS --limit 20 --json` |
| read saved messages | `h2t-ops telegram saved-messages --limit 20 --json` |
| read mentions | `h2t-ops telegram mentions --chat-id CHAT_ID_FROM_DIALOGS --days 7 --limit 20 --json` |
| warm entity cache | `h2t-ops telegram bootstrap --json` |

## Safety

- Auth status, dialogs, folders, messages, saved messages, mentions, and bootstrap are provider reads.
- Request-code and complete modify local Telegram session state and require explicit user intent.
- Telegram digest/tasks/research/students workflows are not connector operations.
- Do not include raw chat text, phone numbers, or private usernames in GitHub issues.

## Commands

```bash
h2t-ops telegram auth status --json
h2t-ops telegram dialogs --limit 20 --json
h2t-ops telegram saved-messages --limit 20 --json
h2t-ops telegram messages ENTITY_FROM_DIALOGS --limit 20 --json
```

## Auth

Telegram expects `~/.config/telegram/config.json` with `api_id` and `api_hash`, plus a Telethon session file after login.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- `SESSION_INCOMPATIBLE`: move the old Telethon session aside and re-authenticate.
- Two-factor password required: run auth complete with the password after explicit user consent.
- Workflow request such as digest or task extraction: keep provider reads here, then route analytics to portable workflow scripts or POS/coordinator.
```

- [ ] **Step 6: Create MeetGeek reference**

Create `plugins/h2t-ops/skills/connectors/references/meetgeek.md` with:

```markdown
# MeetGeek Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth check | `h2t-ops meetgeek auth-check --json` |
| list teams | `h2t-ops meetgeek teams --json` |
| list meetings | `h2t-ops meetgeek list --limit 20 --json` |
| get meeting | `h2t-ops meetgeek get MEETING_ID_FROM_LIST --json` |
| transcript | `h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md` |
| summary | `h2t-ops meetgeek summary MEETING_ID_FROM_LIST --format md` |
| highlights | `h2t-ops meetgeek highlights MEETING_ID_FROM_LIST --format md` |
| insights | `h2t-ops meetgeek insights MEETING_ID_FROM_LIST --format md` |
| recording URL | `h2t-ops meetgeek download-url MEETING_ID_FROM_LIST --json` |
| submit public URL | `h2t-ops meetgeek submit-url URL_TO_RECORDING --json` |

## Safety

- Auth-check, teams, list, get, transcript, summary, highlights, insights, and download-url are provider reads.
- Submit-url writes to MeetGeek and requires explicit user intent.
- Local recording recovery remains skill/coordinator layer, not connector runtime.
- Do not include transcript bodies in GitHub issues.

## Commands

```bash
h2t-ops meetgeek auth-check --json
h2t-ops meetgeek list --limit 20 --json
h2t-ops meetgeek get MEETING_ID_FROM_LIST --json
h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md
```

## Auth

MeetGeek expects `MEETGEEK_API_KEY` from environment, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, or legacy `~/.dor/secrets.env`.

Check readiness through:

```bash
/h2t-core:setup connectors-check
```

## Common Failures

- Listed meeting returns 404 from singular metadata endpoint: use current connector version with list fallback.
- Transcript missing for a fresh meeting: wait for MeetGeek processing.
- Local recording recovery request: use the MeetGeek recovery skill/workflow, not connector runtime.
```

- [ ] **Step 7: Run tests and confirm only final inventory test fails**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q
```

Expected: all tests pass except `test_final_skill_inventory_after_deprecation_gate`, because old per-connector `SKILL.md` entrypoints still exist before live smoke.

---

### Task 4: First Commit With Navigator And References

**Files:**
- Add: `plugins/h2t-ops/skills/connectors/**`

- [ ] **Step 1: Temporarily skip final inventory test before first commit**

Modify `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py` by replacing the final test with:

```python
def test_connector_skill_inventory_transition_state():
    active = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    assert {"connectors", "daily-brief", "research"} <= active
    assert {"calendar", "drive", "gmail", "meetgeek", "notion", "telegram"} <= active
```

This records that the first commit is the transition state: navigator exists, old connector skills still exist for smoke comparison.

- [ ] **Step 2: Run surface tests**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q
```

Expected: PASS.

- [ ] **Step 3: Run CLI help smoke**

Run:

```powershell
uv.exe run h2t-ops connectors
uv.exe run h2t-ops calendar --help
uv.exe run h2t-ops gmail --help
uv.exe run h2t-ops drive --help
uv.exe run h2t-ops notion --help
uv.exe run h2t-ops telegram --help
uv.exe run h2t-ops meetgeek --help
```

Expected: every command exits 0.

- [ ] **Step 4: Commit transition state**

Run:

```bash
git add plugins/h2t-ops/skills/connectors
git commit -m "feat(h2t-ops): add connector navigator skill"
```

Expected: one commit containing only the new navigator skill, references, and surface tests.

---

### Task 5: Live Navigator Smoke Gate

**Files:**
- Read: `plugins/h2t-ops/skills/connectors/SKILL.md`
- Read: `plugins/h2t-ops/skills/connectors/references/*.md`

- [ ] **Step 1: Run branch smoke without marketplace install**

Do not use `/plugin marketplace update` for branch smoke. The marketplace source tracks the published branch, so it cannot verify an unmerged branch.

First verify the local CLI from the repository:

```powershell
uv.exe run h2t-ops --version
uv.exe run h2t-ops connectors
```

Then create a temporary standalone plugin copy that mirrors the final skill shape before deleting real files:

```powershell
$smoke = Join-Path $env:TEMP 'h2t-ops-connectors-smoke'
Remove-Item $smoke -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item plugins/h2t-ops $smoke -Recurse
'calendar','drive','gmail','meetgeek','notion','telegram' | ForEach-Object {
  Remove-Item (Join-Path $smoke "skills\$_") -Recurse -Force
}
claude --plugin-dir $smoke
```

Expected in the temporary Claude session:

- `h2t-ops:connectors` is visible as a plugin skill;
- `h2t-ops:research` and `h2t-ops:daily-brief` remain visible;
- old per-connector skills are not visible in the h2t-ops section;
- the cached installed h2t-ops plugin is suppressed by `--plugin-dir`.

- [ ] **Step 2: Run representative CLI routing smoke**

Run these read-only or dry-run commands:

```powershell
uv.exe run h2t-ops calendar list --days 1 --max 5 --json
uv.exe run h2t-ops calendar freebusy --from 2026-05-23 --to 2026-05-23 --json
uv.exe run h2t-ops gmail list --max 5 --json
uv.exe run h2t-ops gmail labels --json
uv.exe run h2t-ops drive search "lecture" --max 5 --json
$driveFixture = Join-Path $env:TEMP 'h2t-ops-drive-smoke'
New-Item -ItemType Directory -Force $driveFixture | Out-Null
Set-Content -Path (Join-Path $driveFixture 'smoke.txt') -Value 'h2t-ops drive dry-run smoke'
if (-not $env:H2T_TEST_DRIVE_FOLDER_ID) { throw 'Set H2T_TEST_DRIVE_FOLDER_ID to a non-sensitive test Drive folder id before Drive upload-folder smoke.' }
uv.exe run h2t-ops drive upload-folder $driveFixture --parent-id $env:H2T_TEST_DRIVE_FOLDER_ID --dry-run --json
uv.exe run h2t-ops notion search-workspace --object all --limit 5 --json
uv.exe run h2t-ops telegram auth status --json
uv.exe run h2t-ops telegram dialogs --limit 5 --json
uv.exe run h2t-ops meetgeek auth-check --json
uv.exe run h2t-ops meetgeek list --limit 5 --json
```

Expected:

- commands exit 0 when credentials are present;
- if credentials are missing, command returns a typed credential/auth error, not a raw Python trace;
- Drive upload-folder uses `--dry-run`;
- Drive upload-folder uses `H2T_TEST_DRIVE_FOLDER_ID`, not a private folder ID hardcoded in the plan;
- no command writes provider data except local auth/session reads;
- Research and Daily Brief are not invoked.

- [ ] **Step 3: Run direct skill-routing smoke in Claude Code**

Invoke:

```text
/h2t-ops:connectors
```

Run this in the temporary Claude session created with `claude --plugin-dir $smoke`, where old per-connector h2t-ops skills were removed from the temp copy. Then ask these routing prompts:

```text
Which h2t-ops command lists today's busy calendar windows?
Which h2t-ops command searches Gmail for messages from a sender?
Which h2t-ops command uploads a local folder to Drive while preserving relative paths?
Which h2t-ops command finds embedded Notion databases under a page?
Which h2t-ops command checks Telegram auth status?
Which h2t-ops command fetches a MeetGeek transcript?
```

Expected command choices:

```text
h2t-ops calendar freebusy --from YYYY-MM-DD --to YYYY-MM-DD --json
h2t-ops gmail search "from:sender@example.com" --max 10 --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json
h2t-ops notion find-databases PAGE_ID --json
h2t-ops telegram auth status --json
h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md
```

- [ ] **Step 4: Record redacted smoke evidence**

Do not paste raw command output into PRs or issues. Record only pass/fail, command class, exit status class, typed error class if any, and redacted provider IDs. Do not include raw email bodies, chat text, transcript bodies, calendar descriptions, Notion page bodies, or full provider JSON payloads.

Record in the PR body or issue comment:

```text
Navigator smoke passed:
- Calendar route: freebusy/list
- Gmail route: search/read
- Drive route: upload-folder dry-run
- Notion route: find-databases/search-workspace
- Telegram route: auth status/dialogs
- MeetGeek route: auth-check/list/transcript
No raw provider API fallback.
No Research/Daily Brief route theft.
```

- [ ] **Step 5: Stop if smoke fails**

If any provider route is wrong, do not delete old per-connector skills. Create a connector-surface bug issue using `references/issue-policy.md` and keep the transition commit only.

---

### Task 6: Remove Per-Connector Skill Entrypoints After Smoke

**Files:**
- Delete: `plugins/h2t-ops/skills/calendar/SKILL.md`
- Delete: `plugins/h2t-ops/skills/drive/SKILL.md`
- Delete: `plugins/h2t-ops/skills/gmail/SKILL.md`
- Delete: `plugins/h2t-ops/skills/meetgeek/SKILL.md`
- Delete: `plugins/h2t-ops/skills/notion/SKILL.md`
- Delete: `plugins/h2t-ops/skills/telegram/SKILL.md`
- Modify: `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py`
- Modify: `plugins/h2t-ops/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `plugins/h2t-core/hooks-handlers/inject-h2t-context`
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`

- [ ] **Step 1: Restore final inventory test**

Modify `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py` so the inventory test is:

```python
def test_final_skill_inventory_after_deprecation_gate():
    active = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    assert active == {"connectors", "daily-brief", "research"}
```

- [ ] **Step 2: Run the inventory test and verify it fails**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py::test_final_skill_inventory_after_deprecation_gate -q
```

Expected: FAIL because old connector `SKILL.md` entrypoints still exist.

- [ ] **Step 3: Delete old per-connector skill entrypoints**

Run:

```bash
git rm plugins/h2t-ops/skills/calendar/SKILL.md
git rm plugins/h2t-ops/skills/drive/SKILL.md
git rm plugins/h2t-ops/skills/gmail/SKILL.md
git rm plugins/h2t-ops/skills/meetgeek/SKILL.md
git rm plugins/h2t-ops/skills/notion/SKILL.md
git rm plugins/h2t-ops/skills/telegram/SKILL.md
```

Expected: six `SKILL.md` entrypoints are staged for deletion. `research`,
`daily-brief`, and `connectors` remain active, and legacy scripts/tests under
provider directories remain available.

- [ ] **Step 4: Bump h2t-ops plugin version to 1.2.5**

Modify `plugins/h2t-ops/.claude-plugin/plugin.json`:

```json
{
  "name": "h2t-ops",
  "description": "H2T Ops — provider I/O connector navigator, daily-brief, and research (Exa).",
  "version": "1.2.5",
  "author": {
    "name": "lichtpfad"
  }
}
```

Modify the h2t-ops entry in `.claude-plugin/marketplace.json` so its version and description are:

```json
"version": "1.2.5",
"description": "H2T Ops — provider I/O connector navigator, daily-brief, and research (Exa)."
```

Also update `plugins/h2t-core/hooks-handlers/inject-h2t-context` so it no longer
advertises retired h2t-ops per-connector skill names. Bump h2t-core patch in
`plugins/h2t-core/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
so the hook index change is delivered by marketplace update.

- [ ] **Step 5: Run final surface tests**

Run:

```powershell
uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q
```

Expected: PASS.

- [ ] **Step 6: Run h2t-ops CLI help smoke again**

Run:

```powershell
uv.exe run h2t-ops connectors
uv.exe run h2t-ops calendar --help
uv.exe run h2t-ops gmail --help
uv.exe run h2t-ops drive --help
uv.exe run h2t-ops notion --help
uv.exe run h2t-ops telegram --help
uv.exe run h2t-ops meetgeek --help
uv.exe run h2t-ops research --help
```

Expected: all CLI commands still work because provider runtime was not deleted.

- [ ] **Step 7: Commit final consolidation**

Run:

```bash
git add .claude-plugin/marketplace.json plugins/h2t-ops/.claude-plugin/plugin.json plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py
git commit -m "refactor(h2t-ops): consolidate connector skills"
```

Expected: commit includes six skill deletions, final inventory test, and version bump.

---

### Task 7: Roadmap And Issue Evidence

**Files:**
- Modify: `docs/h2t-ops-roadmap.md`

- [x] **Step 1: Update roadmap active closure stream**

In `docs/h2t-ops-roadmap.md`, record the #161 closure row:

```markdown
| 2 | #161 | Consolidate non-research connector skills into `h2t-ops:connectors` + lazy references | Implemented in branch; close after installed-plugin smoke |
```

- [x] **Step 2: Update practical order**

In `docs/h2t-ops-roadmap.md`, record the new practical order:

```markdown
2. Close #161 after installed-plugin smoke confirms the h2t-ops skill listing is
   `connectors`, `research`, and `daily-brief`.
```

- [ ] **Step 3: Run doc grep**

Run:

```powershell
Select-String -Path docs/h2t-ops-roadmap.md -Pattern 'Consolidate non-research|h2t-ops:connectors|#161'
```

Expected: roadmap references #161 and `h2t-ops:connectors` as complete.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add docs/h2t-ops-roadmap.md
git commit -m "docs(roadmap): mark connector skill consolidation complete"
```

Expected: one docs-only commit.

- [ ] **Step 5: Push branch**

Run:

```bash
git push -u origin codex-h2t-ops-connectors-surface
```

Expected: branch is pushed.

- [ ] **Step 6: Create PR**

Run:

```bash
gh pr create --repo lichtpfad/h2t-skills --base main --head codex-h2t-ops-connectors-surface --title "h2t-ops: consolidate connector skill surface (#161)" --body-file pr-161.md
```

`pr-161.md` must contain:

```markdown
## Summary

- Adds `h2t-ops:connectors` as the navigator for Calendar, Gmail, Drive, Notion, Telegram, and MeetGeek provider I/O.
- Moves connector-specific details into lazy references.
- Centralizes connector bug/feature issue policy.
- Keeps `h2t-ops:research` and `h2t-ops:daily-brief` separate.
- Removes old per-connector skills after navigator smoke.

## Verification

- `uv.exe run pytest plugins\h2t-ops\skills\connectors\scripts\test_connectors_surface.py -q`
- `uv.exe run h2t-ops connectors`
- `uv.exe run h2t-ops calendar --help`
- `uv.exe run h2t-ops gmail --help`
- `uv.exe run h2t-ops drive --help`
- `uv.exe run h2t-ops notion --help`
- `uv.exe run h2t-ops telegram --help`
- `uv.exe run h2t-ops meetgeek --help`
- `uv.exe run h2t-ops research --help`
- Live navigator smoke passed for Calendar, Gmail, Drive, Notion, Telegram, and MeetGeek routing.

## Boundaries

- No provider runtime changes.
- No h2t-ops into h2t-core merge.
- Only h2t-core runtime skill index wording may change, so session-start does not advertise retired per-connector skill names.
- No Research consolidation.
- No Daily Brief consolidation.
- No POS/DOR state writes.

Refs #161. Do not close #161 until Task 8 installed-plugin smoke passes.
```

- [ ] **Step 7: Comment on #161**

Run:

```bash
gh issue comment 161 --repo lichtpfad/h2t-skills --body "PR created for #161. Navigator smoke passed, old per-connector skills removed after smoke, Research and Daily Brief remain separate. Final close gate is installed-plugin reload verifying h2t-ops 1.2.5 exposes only connectors/research/daily-brief skills."
```

Expected: issue #161 has evidence and close gate.

---

### Task 8: Installed Plugin Smoke And Close

**Files:**
- No code changes.

- [ ] **Step 1: After PR merge, update marketplace**

Run in Claude Code:

```text
/plugin marketplace update
/plugin uninstall h2t-core@lichtpfad
/plugin install h2t-core@lichtpfad
/plugin uninstall h2t-ops@lichtpfad
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

Expected: h2t-ops plugin reloads at version `1.2.5`.

- [ ] **Step 2: Check skill listing**

Run:

```text
/context
```

Expected h2t-ops skill section contains:

```text
h2t-ops:connectors
h2t-ops:research
h2t-ops:daily-brief
```

Expected h2t-ops skill section does not contain:

```text
h2t-ops:calendar
h2t-ops:gmail
h2t-ops:drive
h2t-ops:notion
h2t-ops:telegram
h2t-ops:meetgeek
```

- [ ] **Step 3: Run direct installed navigator smoke**

Invoke:

```text
/h2t-ops:connectors
```

Ask:

```text
Which command checks Telegram auth status?
```

Expected answer includes:

```text
h2t-ops telegram auth status --json
```

- [ ] **Step 4: Close #161**

Run:

```bash
gh issue close 161 --repo lichtpfad/h2t-skills --comment "Installed-plugin smoke passed for h2t-ops 1.2.5. Active h2t-ops skills are connectors, research, and daily-brief. Old per-connector skills are no longer active. #161 acceptance gates met."
```

Expected: #161 is closed.

---

## Self-Review

### Spec Coverage

- Keep `h2t-core` and `h2t-ops` separate: covered by Task 2 navigator boundaries and Task 7 PR boundaries.
- Keep `research` separate: covered by Task 2 non-scope, Task 6 final inventory, Task 8 listing.
- Keep `daily-brief` separate: covered by Task 2 non-scope, Task 6 final inventory, Task 8 listing.
- Lazy references: covered by Task 3.
- Issue capture policy: covered by Task 2 `issue-policy.md`.
- Live behavior before deletion: covered by Task 5 gate before Task 6 deletion.
- Old connector skills retained or removed with evidence: covered by Task 4 transition commit and Task 6 deletion after smoke.
- `plugins/h2t/` remains retired: no task re-adds or edits `plugins/h2t/`.
- Claude/Codex portability: covered by Task 2 `Codex / AGENTS Adapter` and issue policy.

### Placeholder Scan

The plan avoids unresolved placeholder markers. Command examples use concrete connector verbs and named sentinel values like `EVENT_ID_FROM_LIST` to show where values come from during live use.

### Type Consistency

Test paths, reference paths, skill names, version numbers, and command prefixes are consistent:

- Skill name: `h2t-ops:connectors`
- Skill root: `plugins/h2t-ops/skills/connectors/`
- References root: `plugins/h2t-ops/skills/connectors/references/`
- Test file: `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py`
- Final h2t-ops plugin version: `1.2.5`
