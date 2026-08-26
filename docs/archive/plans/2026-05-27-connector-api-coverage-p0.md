---
title: "Connector API Coverage P0"
status: "draft"
date: "2026-05-27"
milestone: "skills-release"
---

# Connector API Coverage P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close release-blocking connector API coverage gaps #212-#231 so the shipped skills do not advertise non-functional connector surfaces.

**Architecture:** Add narrowly scoped client methods and CLI commands per connector, following existing lazy-import command modules and JSON-first output conventions. Every write/destructive command must be guarded by explicit IDs and confirmation flags. Automated E2E is non-destructive by default: it may create drafts or read safe resources, but it must not send messages, create persistent calendars, or delete/trash/archive anything without explicit user approval for that exact run.

**Tech Stack:** Python 3.11, `uv.exe run pytest`, Google Drive/Gmail/Calendar APIs, Notion SDK, Telethon, MeetGeek REST API, GitHub CLI.

---

## Release Rule

The skills pack is not releasable until:

- #212-#231 are closed or explicitly split with a release-safe reason.
- All new CLI commands have parser + dispatch tests.
- All write/destructive paths have guardrails.
- Communication commands default to draft/no-send. Real send/forward requires both `--send` and `--confirm-send`.
- Connector docs reference the new commands.
- Unit/contract tests pass.
- Live E2E smoke either passes against safe resources or is marked `SKIP` with a missing-env reason in the E2E report.

`#208` is not part of this P0 plan. It is an alternative Pandoc/Drive convert workflow, not basic connector API coverage.

## File Map

| Area | Files |
| --- | --- |
| Drive | `h2t_ops/connectors/drive/client.py`, `h2t_ops/connectors/drive/commands.py`, `tests/connectors/drive/test_client.py`, `tests/connectors/drive/test_commands.py`, `tests/connectors/drive/test_drive_docs_tab_write.py`, `plugins/h2t-ops/skills/connectors/references/drive.md` |
| Gmail | `h2t_ops/connectors/gmail/client.py`, `h2t_ops/connectors/gmail/commands.py`, `tests/connectors/gmail/test_client.py`, `tests/connectors/gmail/test_commands.py`, `plugins/h2t-ops/skills/connectors/references/gmail.md` |
| Notion | `h2t_ops/connectors/notion/client.py`, `h2t_ops/connectors/notion/commands.py`, `tests/connectors/notion/test_client.py`, `tests/connectors/notion/test_commands.py`, `plugins/h2t-ops/skills/connectors/references/notion.md` |
| Telegram | `h2t_ops/connectors/telegram/client.py`, `h2t_ops/connectors/telegram/commands.py`, `tests/connectors/telegram/test_client.py`, `tests/connectors/telegram/test_commands.py`, `plugins/h2t-ops/skills/connectors/references/telegram.md` |
| Calendar | `h2t_ops/connectors/calendar/client.py`, `h2t_ops/connectors/calendar/commands.py`, `tests/connectors/calendar/test_client.py`, `tests/connectors/calendar/test_commands.py`, `plugins/h2t-ops/skills/connectors/references/calendar.md` |
| MeetGeek | `h2t_ops/connectors/meetgeek/client.py`, `h2t_ops/connectors/meetgeek/commands.py`, `tests/connectors/meetgeek/test_client.py`, `tests/connectors/meetgeek/test_commands.py`, `plugins/h2t-ops/skills/connectors/references/meetgeek.md` |
| E2E | `tests/e2e/test_connector_api_coverage.py`, `docs/reports/2026-05-27-connector-api-coverage-p0-e2e.md` |
| Roadmap | `docs/h2t-ops-roadmap.md` |

## E2E Strategy

### Safety Model

Live E2E tests must be opt-in:

```powershell
$env:H2T_E2E_CONNECTORS="1"
uv.exe run pytest tests/e2e/test_connector_api_coverage.py -q
```

Tests must skip with a clear reason when required env vars are absent. They must never use arbitrary user resources.

Safe resource rules:

- All created resources use prefix `h2t-e2e-connector-api-`.
- Destructive operations are never executed by automated E2E.
- Gmail/Telegram live E2E must not send real messages. Gmail uses drafts only. Telegram write/send live E2E is skipped unless the user explicitly approves a specific manual smoke run.
- Calendar live E2E must not create persistent calendars automatically; `create-calendar` is unit/contract-tested and manually smoked only after approval.
- Delete/trash/archive commands are verified by unit/contract tests and by dry manual recipes only. Manual execution requires the user to confirm the exact resource name/title/id in the current session.
- Permanent delete is never part of automated E2E.
- E2E tests write a JSON evidence file under `docs/reports/e2e/connector-api-coverage-p0.json` and the final task summarizes it in Markdown.
- Any live E2E mutation that creates a durable artifact must record the created resource id, title/name, connector, command, cleanup status, and whether cleanup requires manual approval.

### Required E2E Environment

Use these env vars. Missing values skip only the affected connector.

```powershell
$env:H2T_E2E_CONNECTORS="1"
$env:H2T_E2E_DRIVE_FOLDER_ID="<test folder id>"
$env:H2T_E2E_GMAIL_TO="<self or test inbox>"
$env:H2T_E2E_NOTION_PARENT_PAGE_ID="<test parent page id>"
$env:H2T_E2E_NOTION_DATABASE_ID="<test database id>"
$env:H2T_E2E_TELEGRAM_ENTITY="<Saved Messages or test chat id>"
$env:H2T_E2E_CALENDAR_ID="primary"
$env:H2T_E2E_CALENDAR_RECURRING_EVENT_ID="<safe recurring event id>"
$env:H2T_E2E_MEETGEEK_MEETING_ID="<safe existing meeting id>"
```

### E2E Command Matrix

| Connector | Command proof | Cleanup |
| --- | --- | --- |
| Drive | create/upload/get/read operations only; trash/delete command behavior covered by mocks and manual recipe | no automated trash/delete |
| Gmail | create drafts only; reply/forward as drafts; label create is allowed only with no delete in automated E2E | no automated send/trash/delete-label |
| Notion | create/update/append/replace on E2E pages only; archive command behavior covered by mocks and manual recipe | no automated archive |
| Telegram | read-only by default; send-file/forward-message/delete-message covered by mocks and manual recipe | no automated send/forward/delete |
| Calendar | list-instances may be tested only against env-provided safe recurring event; create-calendar covered by mocks and manual recipe | no automated create/delete |
| MeetGeek | list with date range, get action-items for known safe meeting | read-only |

### Manual Smoke Approval Rules

If a task needs live proof for a destructive or externally visible command, stop and ask the user with the exact command and resource:

```text
Approve this one manual smoke?
Command: h2t-ops <connector> ...
Resource: <id/title/name>
Effect: <trash/delete/archive/send/forward>
Rollback: <how to undo or why not needed>
```

Do not run the command unless the user approves that exact command.

### Evidence Schema

Every E2E record must use this shape:

```json
{
  "at": "2026-05-27T12:00:00Z",
  "connector": "drive",
  "command": "upload --update-existing",
  "mode": "read_only|draft|create_only|manual_approved",
  "ok": true,
  "resource": {
    "id": "optional",
    "name": "optional",
    "cleanup": "not_needed|manual_required|not_created"
  },
  "skip_reason": null
}
```

`manual_approved` must only appear after the user approved the exact command in the current session.

## Parallel Execution Model

This plan is intentionally split by connector. Implementation can run in parallel, but only with isolated worktrees and one connector per branch.

Recommended branches:

| Branch | Issues | Files owned |
| --- | --- | --- |
| `codex-p0-drive-api` | #212-#218 | `h2t_ops/connectors/drive/**`, `tests/connectors/drive/**`, Drive reference docs |
| `codex-p0-gmail-api` | #219, #221, #225 | `h2t_ops/connectors/gmail/**`, `tests/connectors/gmail/**`, Gmail reference docs |
| `codex-p0-notion-api` | #220, #223, #227 | `h2t_ops/connectors/notion/**`, `tests/connectors/notion/**`, Notion reference docs |
| `codex-p0-telegram-api` | #222, #226, #229 | `h2t_ops/connectors/telegram/**`, `tests/connectors/telegram/**`, Telegram reference docs |
| `codex-p0-calendar-meetgeek-api` | #224, #228, #230, #231 | Calendar + MeetGeek connector/test/reference docs |
| `codex-p0-e2e-release-evidence` | final report only | `tests/e2e/**`, `docs/reports/**`, `docs/h2t-ops-roadmap.md` |

Do not let parallel connector branches edit `tests/e2e/test_connector_api_coverage.py` directly. Each connector PR should include a small manual/E2E recipe in its reference docs. The final evidence branch creates the shared E2E harness after connector PRs merge, avoiding merge conflicts.

Execution order:

1. Task 0 GitHub metadata normalization.
2. Run Drive first if #212 blocks active work.
3. Gmail, Notion, Telegram, and Calendar+MeetGeek can run in parallel after Task 0.
4. Final E2E/report branch runs after all connector branches merge.

Subagent rule:

- Use one subagent per connector branch.
- Give each subagent only its connector task and owned files.
- Do not dispatch multiple workers against the same connector.
- Final evidence branch should be single-agent to avoid shared report conflicts.

## Task 0: Normalize GitHub Release Blockers

**Files:** none

- [ ] **Step 1: Move connector API gaps into `skills-release`**

```powershell
1..20 | ForEach-Object {
  $issue = 211 + $_
  gh issue edit $issue --repo lichtpfad/h2t-skills --milestone "skills-release"
}
```

Expected: issues #212-#231 have milestone `skills-release`.

- [ ] **Step 2: Apply release-blocker labels**

```powershell
1..20 | ForEach-Object {
  $issue = 211 + $_
  gh issue edit $issue --repo lichtpfad/h2t-skills `
    --add-label "priority:p0" `
    --add-label "domain:skills" `
    --add-label "type:feature" `
    --add-label "phase:implementation"
}
```

Expected: all #212-#231 have `priority:p0`, `domain:skills`, `type:feature`, `phase:implementation`.

- [ ] **Step 3: Verify blocker set**

```powershell
gh issue list --repo lichtpfad/h2t-skills --state open --milestone skills-release --limit 100
```

Expected: #190 and #212-#231 are visible. #208 is not required.

- [ ] **Step 4: Comment on blocker promotion**

For each #212-#231, add:

```powershell
1..20 | ForEach-Object {
  $issue = 211 + $_
  gh issue comment $issue --repo lichtpfad/h2t-skills --body "Promoted to skills-release P0: connector skills should not ship while this basic API surface is missing. Implementation will follow the connector API coverage P0 plan with non-destructive automated E2E and manual approval for send/delete/archive smoke."
}
```

Expected: every issue has an audit comment explaining why it became release-blocking.

- [ ] **Step 5: Commit**

No commit. GitHub metadata only.

## Task 1: Add E2E Harness and Evidence Writer

**Files:**
- Create: `tests/e2e/test_connector_api_coverage.py`
- Create: `tests/e2e/__init__.py`

- [ ] **Step 1: Create package marker**

```python
# tests/e2e/__init__.py
```

- [ ] **Step 2: Add opt-in helpers**

Create `tests/e2e/test_connector_api_coverage.py`:

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


E2E_PREFIX = "h2t-e2e-connector-api"
EVIDENCE_PATH = Path("docs/reports/e2e/connector-api-coverage-p0.json")


def _enabled() -> bool:
    return os.environ.get("H2T_E2E_CONNECTORS") == "1"


def _need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for this connector E2E")
    return value


def _run(*args: str) -> dict:
    if not _enabled():
        pytest.skip("set H2T_E2E_CONNECTORS=1 to run connector E2E")
    result = subprocess.run(
        [sys.executable, "-m", "h2t_ops.cli", *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    return payload["result"]


def _record(
    connector: str,
    command: str,
    result: dict,
    *,
    mode: str = "read_only",
    resource: dict | None = None,
    skip_reason: str | None = None,
) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if EVIDENCE_PATH.exists():
        data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    else:
        data = {"schema": "connector_api_coverage_e2e/v0.1", "runs": []}
    data["runs"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "connector": connector,
        "command": command,
        "mode": mode,
        "ok": True,
        "resource": resource or {"cleanup": "not_created"},
        "skip_reason": skip_reason,
        "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
    })
    EVIDENCE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
```

- [ ] **Step 3: Add skip smoke**

Append:

```python
def test_e2e_harness_skips_without_opt_in():
    if _enabled():
        pytest.skip("opt-in enabled; skip-only test not applicable")
    with pytest.raises(pytest.skip.Exception):
        _run("connectors")
```

- [ ] **Step 4: Run harness test**

```powershell
uv.exe run pytest tests/e2e/test_connector_api_coverage.py::test_e2e_harness_skips_without_opt_in -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add tests/e2e/__init__.py tests/e2e/test_connector_api_coverage.py
git commit -m "test(e2e): add opt-in connector API coverage harness"
```

## Task 2: Drive P0 Coverage (#212-#218)

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py`
- Modify: `h2t_ops/connectors/drive/commands.py`
- Modify: `tests/connectors/drive/test_client.py`
- Modify: `tests/connectors/drive/test_commands.py`
- Modify: `tests/connectors/drive/test_drive_docs_tab_write.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/drive.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

**Scope:**

- #212 `drive upload --update-existing`
- #213 `drive trash`, `drive delete`
- #214 `drive get-file`
- #215 `docs-tab write --clear-first`
- #216 `drive docs create`
- #217 inline `**bold**` and `*italic*` in docs-tab write
- #218 `docs-tab read`

- [ ] **Step 1: Write parser tests**

Add to `tests/connectors/drive/test_commands.py`:

```python
def test_drive_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["drive", "get-file", "file1"]).drive_cmd == "get-file"
    assert parser.parse_args(["drive", "trash", "file1", "--confirm-name", "A"]).drive_cmd == "trash"
    assert parser.parse_args(["drive", "delete", "file1", "--confirm-name", "A", "--confirm-permanent"]).drive_cmd == "delete"
    assert parser.parse_args(["drive", "docs", "create", "Title"]).drive_cmd == "docs"
    assert parser.parse_args(["drive", "docs-tab", "read", "doc1", "tab1"]).docs_tab_cmd == "read"
    ns = parser.parse_args(["drive", "docs-tab", "write", "doc1", "tab1", "--content-file", "x.md", "--clear-first"])
    assert ns.clear_first is True
    ns2 = parser.parse_args(["drive", "upload", "note.md", "--folder", "Folder", "--update-existing"])
    assert ns2.update_existing is True
```

- [ ] **Step 2: Run parser test and verify failure**

```powershell
uv.exe run pytest tests/connectors/drive/test_commands.py::test_drive_p0_parser_surface -q
```

Expected: FAIL until commands exist.

- [ ] **Step 3: Implement client methods**

Add methods to `DriveClient`:

```python
def get_file(self, file_id: str) -> dict[str, object]:
    return self.service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,parents,webViewLink,modifiedTime,size,trashed",
        supportsAllDrives=True,
    ).execute()

def _confirm_file_name(self, file_id: str, confirm_name: str) -> dict[str, object]:
    meta = self.get_file(file_id)
    actual = str(meta.get("name", "")).strip()
    if actual.lower() != confirm_name.strip().lower():
        from h2t_ops.core.errors import UsageError
        raise UsageError(f'name mismatch — expected "{confirm_name}", got "{actual}"')
    return meta

def trash_file(self, file_id: str, *, confirm_name: str) -> dict[str, object]:
    meta = self._confirm_file_name(file_id, confirm_name)
    updated = self.service.files().update(
        fileId=file_id,
        body={"trashed": True},
        fields="id,name,trashed",
        supportsAllDrives=True,
    ).execute()
    return {"file_id": updated["id"], "name": updated["name"], "trashed": updated.get("trashed", True), "previous": meta}

def delete_file(self, file_id: str, *, confirm_name: str) -> dict[str, object]:
    meta = self._confirm_file_name(file_id, confirm_name)
    self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
    return {"file_id": file_id, "name": meta.get("name"), "deleted": True}
```

For upload, add `update_existing=False` to the single-file upload method and reuse existing Drive search-by-name-in-folder logic. If one existing file matches, call `files().update(fileId=existing["id"], media_body=..., body=metadata, fields=...)`. If more than one matches, raise `UsageError("multiple existing files match; use file id or clean duplicates")`.

- [ ] **Step 4: Implement Docs helpers**

Add:

```python
def create_document(self, title: str, *, folder_id: str | None = None) -> dict[str, object]:
    body = {"name": title, "mimeType": "application/vnd.google-apps.document"}
    if folder_id:
        body["parents"] = [folder_id]
    return self.service.files().create(
        body=body,
        fields="id,name,mimeType,webViewLink,parents",
        supportsAllDrives=True,
    ).execute()
```

For `docs-tab read`, use Docs API `documents().get(documentId=..., includeTabsContent=True)` and extract text from the matching tab body `content[].paragraph.elements[].textRun.content`.

For `docs-tab write --clear-first`, read the target tab end index and send a `deleteContentRange` request before insert/style requests.

For #217, extend `_md_to_docs_requests` to emit bold/italic `updateTextStyle` ranges for inline `**text**` and `*text*`. Strip markdown markers from inserted text; style the resulting text ranges.

- [ ] **Step 5: Implement CLI**

Add subcommands:

```text
drive get-file <file_id>
drive trash <file_id> --confirm-name <exact name>
drive delete <file_id> --confirm-name <exact name> --confirm-permanent
drive docs create <title> [--folder-id ...]
drive docs-tab read <doc_id> <tab_id>
drive docs-tab write ... --clear-first
drive upload ... --update-existing
```

`drive delete` must raise `UsageError` without `--confirm-permanent`.

- [ ] **Step 6: Add unit/dispatch tests**

Required tests:

```text
test_upload_update_existing_uses_files_update
test_upload_update_existing_rejects_duplicate_matches
test_trash_requires_confirm_name_match_before_update
test_delete_requires_confirm_permanent
test_get_file_returns_metadata
test_docs_create_calls_files_create_google_doc
test_docs_tab_write_clear_first_sends_delete_before_insert
test_md_to_docs_requests_inline_bold_italic_ranges
test_docs_tab_read_extracts_text
```

- [ ] **Step 7: Add Drive E2E**

Append to `tests/e2e/test_connector_api_coverage.py`:

```python
def test_drive_api_coverage_live():
    folder_id = _need("H2T_E2E_DRIVE_FOLDER_ID")
    title = f"{E2E_PREFIX}-drive.md"
    tmp = Path("tmp-e2e-drive.md")
    tmp.write_text("# First\n\nHello", encoding="utf-8")
    created = _run("drive", "upload", str(tmp), "--parent-id", folder_id, "--update-existing")
    tmp.write_text("# Second\n\nHello **bold**", encoding="utf-8")
    updated = _run("drive", "upload", str(tmp), "--parent-id", folder_id, "--update-existing")
    file_id = updated.get("file_id") or updated.get("id") or created.get("file_id")
    meta = _run("drive", "get-file", file_id)
    assert meta["name"]
    _record(
        "drive",
        "upload/get-file",
        meta,
        mode="create_only",
        resource={"id": file_id, "name": meta["name"], "cleanup": "manual_required"},
    )
```

- [ ] **Step 8: Run tests**

```powershell
uv.exe run pytest tests/connectors/drive -q
uv.exe run pytest tests/connectors/drive/test_commands.py tests/connectors/drive/test_client.py tests/connectors/drive/test_drive_docs_tab_write.py -q
```

Expected: all pass.

- [ ] **Step 9: Commit and close issues**

```powershell
git add h2t_ops/connectors/drive tests/connectors/drive plugins/h2t-ops/skills/connectors/references/drive.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(drive): complete P0 API coverage"
```

Close #212-#218 after PR merge or include `Closes #212 ... #218` in PR body.

## Task 3: Gmail P0 Coverage (#219, #221, #225)

**Files:**
- Modify: `h2t_ops/connectors/gmail/client.py`
- Modify: `h2t_ops/connectors/gmail/commands.py`
- Modify: `tests/connectors/gmail/test_client.py`
- Modify: `tests/connectors/gmail/test_commands.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/gmail.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

- [ ] **Step 1: Add parser tests**

Add:

```python
def test_gmail_p0_parser_surface():
    p = _parser()
    assert p.parse_args(["gmail", "reply", "T1", "--body", "ok"]).gmail_cmd == "reply"
    assert p.parse_args(["gmail", "forward", "M1", "--to", "me@example.com"]).gmail_cmd == "forward"
    assert p.parse_args(["gmail", "label-create", "Project X"]).gmail_cmd == "label-create"
    assert p.parse_args(["gmail", "label-delete", "Label_1", "--confirm-name", "Project X"]).gmail_cmd == "label-delete"
```

- [ ] **Step 2: Implement client methods**

Add:

```python
def reply_to_thread(self, thread_id: str, *, body: str, body_file: str | None = None, send: bool = False, confirm_send: bool = False) -> dict[str, object]:
    if send and not confirm_send:
        from h2t_ops.core.errors import UsageError
        raise UsageError("gmail reply: --confirm-send is required with --send")
    thread = self.get_thread(thread_id)
    messages = thread.get("messages") or []
    if not messages:
        from h2t_ops.core.errors import UsageError
        raise UsageError(f"gmail reply: thread has no messages: {thread_id}")
    last = messages[-1]
    subject = last.get("subject") or ""
    to_addr = last.get("from") or ""
    reply_body = Path(body_file).read_text(encoding="utf-8") if body_file else body
    return self.send_message(
        to=to_addr,
        subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
        body=reply_body,
        thread_id=thread_id,
        reply_to_message_id=last.get("id"),
        draft=not send,
    )

def create_label(self, name: str) -> dict[str, object]:
    body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    return self.service.users().labels().create(userId="me", body=body).execute()

def delete_label(self, label_id: str, *, confirm_name: str) -> dict[str, object]:
    labels = self.list_labels()
    match = next((l for l in labels if l.get("id") == label_id), None)
    actual = (match or {}).get("name", "")
    if actual.strip().lower() != confirm_name.strip().lower():
        from h2t_ops.core.errors import UsageError
        raise UsageError(f'label mismatch — expected "{confirm_name}", got "{actual}"')
    self.service.users().labels().delete(userId="me", id=label_id).execute()
    return {"label_id": label_id, "name": actual, "deleted": True}
```

Implement `forward_message(message_id, to, body=None, send=False, confirm_send=False)` by reading the source message and creating a draft by default with `Fwd: <subject>` and quoted body. Use existing `send_message`; do not mutate the original message. If `send=True` and `confirm_send=False`, raise `UsageError("gmail forward: --confirm-send is required with --send")`.

- [ ] **Step 3: Add CLI**

Commands:

```text
gmail reply <thread_id> --body <text> | --file <path> [--send --confirm-send]
gmail forward <message_id> --to <addr> [--body <text>] [--send --confirm-send]
gmail label-create <name>
gmail label-delete <label_id> --confirm-name <exact name>
```

Guardrails:

- `reply` requires body or file.
- `reply` and `forward` create drafts by default.
- Real send requires both `--send` and `--confirm-send`.
- `label-delete` requires `--confirm-name`.
- `forward` requires explicit `--to`.

- [ ] **Step 4: Add tests**

Required tests:

```text
test_reply_reads_thread_and_calls_send_with_thread_headers
test_reply_requires_body
test_reply_defaults_to_draft
test_reply_send_requires_confirm_send
test_forward_reads_message_and_sends_new_message
test_forward_defaults_to_draft
test_forward_send_requires_confirm_send
test_label_create_calls_gmail_labels_create
test_label_delete_requires_name_match_before_delete
test_label_delete_mismatch_raises_usageerror
```

- [ ] **Step 5: Add Gmail E2E**

Append:

```python
def test_gmail_api_coverage_live():
    to_addr = _need("H2T_E2E_GMAIL_TO")
    subject = f"{E2E_PREFIX}-gmail"
    seed = _run("gmail", "send", to_addr, subject, "--body", "seed", "--draft")
    assert seed.get("draft") is True
    _record(
        "gmail",
        "draft",
        seed,
        mode="draft",
        resource={"id": seed.get("id"), "name": subject, "cleanup": "manual_required"},
    )
```

Live reply/forward must run as draft by default in E2E. Do not add an env var that sends real mail automatically.

- [ ] **Step 6: Run tests and commit**

```powershell
uv.exe run pytest tests/connectors/gmail -q
git add h2t_ops/connectors/gmail tests/connectors/gmail plugins/h2t-ops/skills/connectors/references/gmail.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(gmail): add reply forward and label lifecycle"
```

## Task 4: Notion P0 Coverage (#220, #223, #227)

**Files:**
- Modify: `h2t_ops/connectors/notion/client.py`
- Modify: `h2t_ops/connectors/notion/commands.py`
- Modify: `tests/connectors/notion/test_client.py`
- Modify: `tests/connectors/notion/test_commands.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/notion.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

- [ ] **Step 1: Parser tests**

```python
def test_notion_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["notion", "create-db-item", "db1", "--title", "Task"]).notion_cmd == "create-db-item"
    assert parser.parse_args(["notion", "update-db-item", "page1", "--property-json", '{"Status":{"select":{"name":"Done"}}}']).notion_cmd == "update-db-item"
    assert parser.parse_args(["notion", "archive", "page1", "--confirm-title", "Task"]).notion_cmd == "archive"
    assert parser.parse_args(["notion", "append-blocks", "page1", "--content-file", "x.md"]).notion_cmd == "append-blocks"
    assert parser.parse_args(["notion", "replace-content", "page1", "--content-file", "x.md", "--confirm-title", "Task"]).notion_cmd == "replace-content"
```

- [ ] **Step 2: Client methods**

Add:

```python
def create_db_item(self, database_id: str, *, title: str, property_json: str | None = None) -> dict:
    properties = json.loads(property_json) if property_json else {}
    if "Name" not in properties and "title" not in {k.lower() for k in properties}:
        properties["Name"] = {"title": [{"text": {"content": title}}]}
    return self.client.pages.create(parent={"database_id": database_id}, properties=properties)

def update_db_item(self, page_id: str, *, property_json: str) -> dict:
    return self.client.pages.update(page_id=page_id, properties=json.loads(property_json))

def archive_page(self, page_id: str, *, confirm_title: str) -> dict:
    page = self.client.pages.retrieve(page_id=page_id)
    actual = self._page_title(page)
    if actual.strip().lower() != confirm_title.strip().lower():
        raise UsageError(f'title mismatch — expected "{confirm_title}", got "{actual}"')
    return self.client.pages.update(page_id=page_id, archived=True)
```

Use the existing markdown-to-block conversion used by `create/update` for `append-blocks` and `replace-content`. `replace-content` must confirm page title, delete existing child blocks, then append new blocks.

- [ ] **Step 3: Tests**

Required tests:

```text
test_create_db_item_builds_title_property
test_update_db_item_passes_properties_json
test_archive_confirms_title_before_update
test_append_blocks_uses_blocks_children_append
test_replace_content_deletes_existing_blocks_then_appends
test_replace_content_mismatch_raises_before_delete
```

- [ ] **Step 4: E2E**

```python
def test_notion_api_coverage_live():
    db_id = _need("H2T_E2E_NOTION_DATABASE_ID")
    item = _run("notion", "create-db-item", db_id, "--title", f"{E2E_PREFIX}-notion")
    page_id = item.get("id") or item.get("page_id")
    updated = _run("notion", "update-db-item", page_id, "--property-json", '{"Name":{"title":[{"text":{"content":"h2t-e2e-connector-api-notion-updated"}}]}}')
    assert updated
    _record(
        "notion",
        "create/update",
        updated,
        mode="create_only",
        resource={"id": page_id, "name": "h2t-e2e-connector-api-notion-updated", "cleanup": "manual_required"},
    )
```

- [ ] **Step 5: Run tests and commit**

```powershell
uv.exe run pytest tests/connectors/notion -q
git add h2t_ops/connectors/notion tests/connectors/notion plugins/h2t-ops/skills/connectors/references/notion.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(notion): add database row and page lifecycle commands"
```

## Task 5: Telegram P0 Coverage (#222, #226, #229)

**Files:**
- Modify: `h2t_ops/connectors/telegram/client.py`
- Modify: `h2t_ops/connectors/telegram/commands.py`
- Modify: `tests/connectors/telegram/test_client.py`
- Modify: `tests/connectors/telegram/test_commands.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/telegram.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

- [ ] **Step 1: Parser tests**

```python
def test_telegram_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["telegram", "send-file", "me", "file.txt"]).telegram_cmd == "send-file"
    assert parser.parse_args(["telegram", "forward-message", "me", "--from", "me", "--message-id", "1"]).telegram_cmd == "forward-message"
    assert parser.parse_args(["telegram", "delete-message", "me", "1", "--confirm"]).telegram_cmd == "delete-message"
```

- [ ] **Step 2: Client methods**

Add Telethon-backed methods:

```python
def send_file(self, entity: str, path: str, *, caption: str | None = None) -> dict:
    msg = self.client.send_file(entity, path, caption=caption)
    return self._message_to_dict(msg)

def forward_message(self, to_entity: str, *, from_entity: str, message_id: int) -> dict:
    msg = self.client.forward_messages(to_entity, message_id, from_peer=from_entity)
    return self._message_to_dict(msg)

def delete_message(self, entity: str, message_id: int) -> dict:
    result = self.client.delete_messages(entity, [message_id])
    return {"entity": entity, "message_id": message_id, "deleted": True, "raw": str(result)}
```

- [ ] **Step 3: CLI guardrails**

Commands:

```text
telegram send-file <entity> <path> [--caption ...]
telegram forward-message <to_entity> --from <from_entity> --message-id <id>
telegram delete-message <entity> <message_id> --confirm
```

`delete-message` must raise `UsageError` without `--confirm`.

- [ ] **Step 4: Tests**

Required tests:

```text
test_send_file_dispatches_path_and_caption
test_forward_message_dispatches_entities_and_message_id
test_delete_message_requires_confirm
test_delete_message_dispatches_after_confirm
```

- [ ] **Step 5: E2E**

```python
def test_telegram_api_coverage_live():
    pytest.skip("Telegram write/forward/delete live smoke requires explicit user approval; covered by unit/contract tests")
```

Telegram live E2E must not send, forward, or delete automatically. Manual smoke requires explicit user approval for the exact command and resource.

- [ ] **Step 6: Run tests and commit**

```powershell
uv.exe run pytest tests/connectors/telegram -q
git add h2t_ops/connectors/telegram tests/connectors/telegram plugins/h2t-ops/skills/connectors/references/telegram.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(telegram): add file forward and delete message commands"
```

## Task 6: Calendar P0 Coverage (#224, #228)

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/calendar.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

- [ ] **Step 1: Parser tests**

```python
def test_calendar_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["calendar", "create-calendar", "Test Calendar"]).calendar_cmd == "create-calendar"
    assert parser.parse_args(["calendar", "instances", "event1", "--calendar-id", "primary"]).calendar_cmd == "instances"
```

- [ ] **Step 2: Client methods**

Add:

```python
def create_calendar(self, summary: str, *, timezone: str | None = None) -> dict:
    body = {"summary": summary}
    if timezone:
        body["timeZone"] = timezone
    return self.service.calendars().insert(body=body).execute()

def list_instances(self, event_id: str, *, calendar_id: str = "primary", time_min: str | None = None, time_max: str | None = None, max_results: int = 250) -> list[dict]:
    req = self.service.events().instances(
        calendarId=calendar_id,
        eventId=event_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
    )
    return req.execute().get("items", [])
```

- [ ] **Step 3: CLI**

Commands:

```text
calendar create-calendar <summary> [--timezone ...]
calendar instances <event_id> [--calendar-id ...] [--from ... --to ...] [--max ...]
```

Use existing date-window parsing for `instances`.

- [ ] **Step 4: Tests**

Required tests:

```text
test_create_calendar_dispatches_summary_timezone
test_instances_dispatches_date_window_and_max
test_instances_rejects_partial_date_window
```

- [ ] **Step 5: E2E**

```python
def test_calendar_api_coverage_live():
    event_id = _need("H2T_E2E_CALENDAR_RECURRING_EVENT_ID")
    calendar_id = os.environ.get("H2T_E2E_CALENDAR_ID", "primary")
    rows = _run("calendar", "instances", event_id, "--calendar-id", calendar_id)
    assert isinstance(rows, list)
    _record(
        "calendar",
        "instances",
        {"count": len(rows)},
        mode="read_only",
        resource={"id": event_id, "name": "env-provided recurring event", "cleanup": "not_needed"},
    )
```

`create-calendar` live proof is a manual smoke recipe only. Do not create calendars in automated E2E.

- [ ] **Step 6: Run tests and commit**

```powershell
uv.exe run pytest tests/connectors/calendar -q
git add h2t_ops/connectors/calendar tests/connectors/calendar plugins/h2t-ops/skills/connectors/references/calendar.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(calendar): add calendar creation and recurring instances"
```

## Task 7: MeetGeek P0 Coverage (#230, #231)

**Files:**
- Modify: `h2t_ops/connectors/meetgeek/client.py`
- Modify: `h2t_ops/connectors/meetgeek/commands.py`
- Modify: `tests/connectors/meetgeek/test_client.py`
- Modify: `tests/connectors/meetgeek/test_commands.py`
- Modify: `plugins/h2t-ops/skills/connectors/references/meetgeek.md`
- Modify: `tests/e2e/test_connector_api_coverage.py`

- [ ] **Step 1: Parser tests**

```python
def test_meetgeek_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["meetgeek", "action-items", "meeting1"]).meetgeek_cmd == "action-items"
    ns = parser.parse_args(["meetgeek", "list", "--from", "2026-05-01", "--to", "2026-05-27"])
    assert ns.from_date == "2026-05-01"
    assert ns.to_date == "2026-05-27"
```

- [ ] **Step 2: Client changes**

For date range, filter client-side if MeetGeek list endpoint lacks server-side date params. Use meeting `start_time`, `started_at`, or `created_at` fields already returned by list.

Add:

```python
def action_items(self, meeting_id: str) -> dict:
    summary = self.summary(meeting_id)
    return {
        "meeting_id": meeting_id,
        "action_items": summary.get("action_items") or [],
        "source": "summary",
    }
```

- [ ] **Step 3: CLI**

Commands:

```text
meetgeek list [--from YYYY-MM-DD --to YYYY-MM-DD]
meetgeek action-items <meeting_id>
```

Partial date windows must raise `UsageError`.

- [ ] **Step 4: Tests**

Required tests:

```text
test_list_date_range_filters_meetings
test_list_partial_date_window_raises
test_action_items_returns_summary_action_items
```

- [ ] **Step 5: E2E**

```python
def test_meetgeek_api_coverage_live():
    meeting_id = _need("H2T_E2E_MEETGEEK_MEETING_ID")
    actions = _run("meetgeek", "action-items", meeting_id)
    assert "action_items" in actions
    _record(
        "meetgeek",
        "action-items",
        actions,
        mode="read_only",
        resource={"id": meeting_id, "name": "env-provided meeting", "cleanup": "not_needed"},
    )
```

- [ ] **Step 6: Run tests and commit**

```powershell
uv.exe run pytest tests/connectors/meetgeek -q
git add h2t_ops/connectors/meetgeek tests/connectors/meetgeek plugins/h2t-ops/skills/connectors/references/meetgeek.md tests/e2e/test_connector_api_coverage.py
git commit -m "feat(meetgeek): add action-items and date range filtering"
```

## Task 8: Final E2E Report, Docs, and Release Gate

**Files:**
- Create: `docs/reports/2026-05-27-connector-api-coverage-p0-e2e.md`
- Modify: `docs/h2t-ops-roadmap.md`
- Modify: connector reference docs touched above

- [ ] **Step 1: Run full focused unit suite**

```powershell
uv.exe run pytest tests/connectors/drive tests/connectors/gmail tests/connectors/notion tests/connectors/telegram tests/connectors/calendar tests/connectors/meetgeek -q
```

Expected: all pass.

- [ ] **Step 2: Run full connector suite**

```powershell
uv.exe run pytest tests/connectors -q
```

Expected: all pass. If `uv.lock` changes after `uv.exe run`, restore it unless dependency changes were intentionally introduced.

- [ ] **Step 3: Run opt-in E2E**

```powershell
uv.exe run pytest tests/e2e/test_connector_api_coverage.py -q
```

Expected:

- Without `H2T_E2E_CONNECTORS=1`: skip/pass only.
- With env configured: safe live resources are created and cleaned according to the matrix.

- [ ] **Step 4: Write E2E report**

Create `docs/reports/2026-05-27-connector-api-coverage-p0-e2e.md`:

```markdown
---
title: "Connector API Coverage P0 E2E"
status: "complete"
date: "2026-05-27"
---

# Connector API Coverage P0 E2E

## Unit Verification

- `uv.exe run pytest tests/connectors -q`: PASS

## Live E2E

| Connector | Status | Evidence |
| --- | --- | --- |
| Drive | PASS/SKIP | ... |
| Gmail | PASS/SKIP | ... |
| Notion | PASS/SKIP | ... |
| Telegram | PASS/SKIP | ... |
| Calendar | PASS/SKIP | ... |
| MeetGeek | PASS/SKIP | ... |

## Safety

Automated live checks did not send messages and did not delete/trash/archive resources. Destructive and externally visible command behavior is covered by unit/contract tests and optional manual smoke recipes requiring explicit user approval.
```

- [ ] **Step 5: Update roadmap**

In `docs/h2t-ops-roadmap.md`, mark connector API coverage as release-ready and list #212-#231 as closed.

- [ ] **Step 6: Commit**

```powershell
git add docs/reports/2026-05-27-connector-api-coverage-p0-e2e.md docs/h2t-ops-roadmap.md plugins/h2t-ops/skills/connectors/references
git commit -m "docs(release): record connector API coverage P0 evidence"
```

- [ ] **Step 7: PR body**

Use this PR body for the final evidence PR after connector PRs merge:

```markdown
## Summary

- record P0 connector API coverage evidence after connector PRs merged
- add opt-in non-destructive E2E harness
- update roadmap for release readiness

## Issues

No issue closes here unless a connector issue was intentionally left for final evidence.
Connector implementation PRs close their own issues.

## Tests

- uv.exe run pytest tests/connectors -q
- uv.exe run pytest tests/e2e/test_connector_api_coverage.py -q
```

## Execution Notes

- Use isolated connector branches listed in the Parallel Execution Model.
- Each task commits independently.
- Prefer one subagent per connector task.
- Do not make one giant implementation PR for #212-#231.
- Connector branches should not edit shared `tests/e2e/**`, `docs/reports/**`, or `docs/h2t-ops-roadmap.md`; leave those to the final evidence branch.
- Do not run live E2E without `H2T_E2E_CONNECTORS=1`.
- Do not send messages in automated E2E. Use Gmail drafts only.
- Do not delete/trash/archive in automated E2E.
- Do not use existing personal production resources for destructive tests.
- Manual destructive/send smoke requires explicit user approval for the exact command and resource.
- Do not include `uv.lock` unless a new dependency is intentionally added and justified.

## Self-Review Checklist

- #212-#231 have a task.
- E2E is opt-in and safe by construction.
- Destructive commands have explicit confirmation.
- Read/write commands have parser and dispatch tests.
- Docs and roadmap updates are included.
- #208 remains outside P0.
