---
title: "h2t-ops drive share Implementation Plan (#168)"
status: "draft"
date: "2026-05-24"
milestone: ""
---
# h2t-ops drive share Implementation Plan (#168)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `h2t-ops drive share <FILE_ID>` with three modes — invite a user by email, open link access to anyone, or inspect current permission state.

**Architecture:** `share_file()` is added to `DriveClient` in `client.py` alongside `upload_file()`. The `share` subcommand is registered in `commands.py` using an argparse mutually exclusive group (exactly one of `--email`, `--anyone`, `--get-link` required). Two post-parse checks enforce `--anyone --confirm-public` and reject `--role` with `--get-link`. All HTTP 401/403 errors surface as `AuthError` (exit 4) via the existing `_map_http_error()`.

**Tech Stack:** Python stdlib `argparse`, `unittest.mock.MagicMock`, `pytest`, Google Drive API v3 (`permissions.create`, `permissions.list`, `files.get`).

---

## File Map

| File | Action |
|------|--------|
| `h2t_ops/connectors/drive/client.py` | Modify — add `share_file()` to `DriveClient` after `upload_file()` |
| `h2t_ops/connectors/drive/commands.py` | Modify — register `share` subparser in `register()`; add dispatch in `run()` |
| `tests/connectors/drive/test_drive_share.py` | Create — 17 tests (10 client, 7 command) |

---

### Task 1: `share_file()` backend — TDD

**Files:**
- Create: `tests/connectors/drive/test_drive_share.py`
- Modify: `h2t_ops/connectors/drive/client.py`

- [ ] **Step 1: Write the failing test file**

```python
"""Tests for DriveClient.share_file() — spec #168."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sc():
    """DriveClient with mocked service — no network."""
    from h2t_ops.connectors.drive.client import DriveClient
    c = object.__new__(DriveClient)
    c.service = MagicMock()
    return c


def _setup_create(sc, perm_id="perm1", link="https://docs.google.com/file"):
    sc.service.permissions.return_value.create.return_value.execute.return_value = {"id": perm_id}
    sc.service.files.return_value.get.return_value.execute.return_value = {"webViewLink": link}


def _setup_get_link(sc, permissions, link="https://docs.google.com/file"):
    sc.service.files.return_value.get.return_value.execute.return_value = {"webViewLink": link}
    sc.service.permissions.return_value.list.return_value.execute.return_value = {
        "permissions": permissions
    }


# --- --email mode ---

def test_email_calls_permissions_create_type_user(sc):
    _setup_create(sc)
    sc.share_file("fid1", email="user@example.com")
    call = sc.service.permissions.return_value.create.call_args
    assert call.kwargs["body"]["type"] == "user"
    assert call.kwargs["body"]["emailAddress"] == "user@example.com"
    assert call.kwargs["sendNotificationEmail"] is False


def test_email_result_granted_to(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="alice@example.com")
    assert result["granted_to"] == "alice@example.com"


def test_email_default_role_reader(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="user@example.com")
    call = sc.service.permissions.return_value.create.call_args
    assert call.kwargs["body"]["role"] == "reader"
    assert result["role"] == "reader"


def test_email_result_kind_and_type(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="user@example.com")
    assert result["kind"] == "drive_share/v1"
    assert result["type"] == "user"
    assert "permission_id" in result


# --- --anyone mode ---

def test_anyone_calls_permissions_create_no_email_key(sc):
    _setup_create(sc)
    sc.share_file("fid1", anyone=True)
    call = sc.service.permissions.return_value.create.call_args
    body = call.kwargs["body"]
    assert body["type"] == "anyone"
    assert "emailAddress" not in body


def test_anyone_result_granted_to_anyone(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", anyone=True)
    assert result["granted_to"] == "anyone"
    assert result["type"] == "anyone"


# --- --get-link mode ---

def test_get_link_never_calls_permissions_create(sc):
    _setup_get_link(sc, permissions=[])
    sc.share_file("fid1", get_link=True)
    sc.service.permissions.return_value.create.assert_not_called()


def test_get_link_has_anyone_permission_true(sc):
    _setup_get_link(sc, permissions=[{"type": "anyone", "role": "reader"}])
    result = sc.share_file("fid1", get_link=True)
    assert result["has_anyone_permission"] is True


def test_get_link_has_anyone_permission_false(sc):
    _setup_get_link(sc, permissions=[{"type": "user", "role": "writer"}])
    result = sc.share_file("fid1", get_link=True)
    assert result["has_anyone_permission"] is False


def test_get_link_excludes_granted_to_and_permission_id(sc):
    _setup_get_link(sc, permissions=[])
    result = sc.share_file("fid1", get_link=True)
    assert "granted_to" not in result
    assert "permission_id" not in result
    assert result["type"] == "get-link"
    assert result["kind"] == "drive_share/v1"
```

- [ ] **Step 2: Run tests to confirm they all fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/drive/test_drive_share.py -v
```

Expected: 10 tests fail with `AttributeError: 'DriveClient' object has no attribute 'share_file'`

- [ ] **Step 3: Add `share_file()` to `DriveClient` in `client.py`**

Insert this method immediately after `upload_file()` (after the `raise _map_http_error(e, op=f"upload file {src}") from e` line):

```python
    def share_file(
        self,
        file_id: str,
        *,
        email: Optional[str] = None,
        role: str = "reader",
        anyone: bool = False,
        get_link: bool = False,
    ) -> Dict[str, Any]:
        try:
            if get_link:
                meta = self.service.files().get(
                    fileId=file_id,
                    fields="id,name,webViewLink",
                    supportsAllDrives=True,
                ).execute()
                perms_resp = self.service.permissions().list(
                    fileId=file_id,
                    fields="permissions(type,role)",
                    supportsAllDrives=True,
                ).execute()
                permissions = perms_resp.get("permissions", [])
                has_anyone = any(p.get("type") == "anyone" for p in permissions)
                return {
                    "kind": "drive_share/v1",
                    "file_id": file_id,
                    "web_view_link": meta.get("webViewLink", ""),
                    "type": "get-link",
                    "has_anyone_permission": has_anyone,
                }
            perm_type = "user" if email else "anyone"
            perm_body: Dict[str, Any] = {"type": perm_type, "role": role}
            if email:
                perm_body["emailAddress"] = email
            perm = self.service.permissions().create(
                fileId=file_id,
                body=perm_body,
                sendNotificationEmail=False,
                supportsAllDrives=True,
                fields="id",
            ).execute()
            meta = self.service.files().get(
                fileId=file_id,
                fields="webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "kind": "drive_share/v1",
                "file_id": file_id,
                "web_view_link": meta.get("webViewLink", ""),
                "permission_id": perm.get("id", ""),
                "role": role,
                "type": perm_type,
                "granted_to": email if email else "anyone",
            }
        except Exception as e:
            raise _map_http_error(e, op=f"share file {file_id}") from e
```

- [ ] **Step 4: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/drive/test_drive_share.py -v
```

Expected: all 10 tests pass

- [ ] **Step 5: Run full drive test suite — no regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/drive/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```
git add tests/connectors/drive/test_drive_share.py h2t_ops/connectors/drive/client.py
git commit -m "feat(drive): add share_file() to DriveClient (#168)"
```

---

### Task 2: `share` subcommand — TDD

**Files:**
- Modify: `tests/connectors/drive/test_drive_share.py` (append command tests)
- Modify: `h2t_ops/connectors/drive/commands.py`

- [ ] **Step 1: Append command tests to `test_drive_share.py`**

Append these tests after the existing client tests:

```python
# --- command: parser registration ---

import argparse


def _build_parser():
    from h2t_ops.connectors.drive.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_share_subcommand_registered():
    parser = _build_parser()
    args = parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com"])
    assert args.drive_cmd == "share"
    assert args.email == "u@e.com"


def test_no_mode_flag_exits_nonzero():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["drive", "share", "fid1"])
    assert exc.value.code != 0


def test_email_and_anyone_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com", "--anyone"])


def test_email_and_get_link_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com", "--get-link"])


def test_anyone_and_get_link_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--anyone", "--get-link"])


# --- command: dispatch post-parse checks ---

def test_get_link_with_role_raises_usage_error(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=False, get_link=True,
        role="writer", confirm_public=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError, match="--role cannot be used with --get-link"):
        cmds_mod.run(args)


def test_anyone_without_confirm_public_raises_usage_error(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=True, get_link=False,
        role="reader", confirm_public=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError, match="--confirm-public"):
        cmds_mod.run(args)
```

- [ ] **Step 2: Run new command tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/drive/test_drive_share.py::test_share_subcommand_registered tests/connectors/drive/test_drive_share.py::test_no_mode_flag_exits_nonzero tests/connectors/drive/test_drive_share.py::test_email_and_anyone_mutually_exclusive tests/connectors/drive/test_drive_share.py::test_email_and_get_link_mutually_exclusive tests/connectors/drive/test_drive_share.py::test_anyone_and_get_link_mutually_exclusive tests/connectors/drive/test_drive_share.py::test_get_link_with_role_raises_usage_error tests/connectors/drive/test_drive_share.py::test_anyone_without_confirm_public_raises_usage_error -v
```

Expected: all 7 fail — parser has no `share` subcommand yet, `run()` raises `UsageError: unknown drive subcommand: share`

- [ ] **Step 3: Register `share` subparser in `commands.py`**

In `register()`, insert before `p.set_defaults(_handler=run)` (after the `add_fmt(ufp)` block):

```python
    shp = cmds.add_parser("share", help="Share a Drive file or inspect its permission state")
    shp.add_argument("file_id", help="Drive file ID")
    mode_group = shp.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--email", metavar="ADDR",
        help="Invite a specific user by email",
    )
    mode_group.add_argument(
        "--anyone", action="store_true",
        help="Open link access (anyone with the link); requires --confirm-public",
    )
    mode_group.add_argument(
        "--get-link", action="store_true", dest="get_link",
        help="Return webViewLink and permission state (read-only)",
    )
    shp.add_argument(
        "--role", choices=["reader", "writer", "commenter"], default="reader",
        help="Permission role (default: reader); not valid with --get-link",
    )
    shp.add_argument(
        "--confirm-public", action="store_true", dest="confirm_public",
        help="Required with --anyone; explicitly acknowledges public exposure",
    )
    add_fmt(shp)
```

- [ ] **Step 4: Add `share` dispatch in `run()`**

Insert before the final `raise UsageError(f"unknown drive subcommand: {cmd}")` line:

```python
    if cmd == "share":
        if args.get_link and args.role != "reader":
            raise UsageError("--role cannot be used with --get-link")
        if args.anyone and not args.confirm_public:
            raise UsageError(
                "--anyone requires --confirm-public to prevent accidental public exposure"
            )
        return client.share_file(
            args.file_id,
            email=args.email,
            role=args.role,
            anyone=args.anyone,
            get_link=args.get_link,
        )
```

- [ ] **Step 5: Run all share tests — all 17 pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/drive/test_drive_share.py -v
```

Expected: all 17 tests pass

- [ ] **Step 6: Run full test suite — no regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/ -v --tb=short
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```
git add h2t_ops/connectors/drive/commands.py tests/connectors/drive/test_drive_share.py
git commit -m "feat(drive): add share subcommand — email/anyone/get-link modes (#168)"
```

---

### Task 3: Update SKILL.md — remove placeholder, document share command

**Files:**
- Modify: `plugins/h2t-ops/skills/connectors/SKILL.md`

- [ ] **Step 1: Replace the "Missing share command" placeholder**

Find the `### Upload safety rules (mandatory)` section. The last bullet currently reads:

```
- **Missing `share` command.** Inviting collaborators via CLI is not yet supported (issue #168). After upload, show the Google Docs edit URL and instruct the user to share manually via Drive web UI.
```

Replace that bullet with:

```
- **Sharing after upload.** Use `h2t-ops drive share <FILE_ID>`:
  - Invite by email: `h2t-ops drive share <FILE_ID> --email user@example.com --role writer --json`
  - Open link access: `h2t-ops drive share <FILE_ID> --anyone --confirm-public --json`
  - Inspect permissions: `h2t-ops drive share <FILE_ID> --get-link --json`
  - `--anyone` always requires `--confirm-public` (safety gate against accidental public exposure).
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-ops/skills/connectors/SKILL.md
git commit -m "docs(connectors): update SKILL.md — document share command (#168)"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `share_file()` with `email`/`anyone`/`get_link`/`role` params | Task 1 |
| `--email` → `permissions().create()` `type=user`, `sendNotificationEmail=False` | Task 1 test 1, impl |
| `--anyone` → `permissions().create()` `type=anyone`, no `emailAddress` | Task 1 test 5, impl |
| `--get-link` → `files().get()` + `permissions().list()`, never `create()` | Task 1 tests 7–10 |
| `has_anyone_permission=True` when `type=anyone` permission exists | Task 1 test 8 |
| `has_anyone_permission=False` when no `anyone` permission | Task 1 test 9 |
| `granted_to: <email>` in `--email` result | Task 1 test 2 |
| `granted_to: "anyone"` in `--anyone` result | Task 1 test 6 |
| No `granted_to`/`permission_id` in `--get-link` result | Task 1 test 10 |
| Default role `reader` with `--email` | Task 1 test 3 |
| `kind: "drive_share/v1"` | Task 1 test 4 |
| argparse mutually exclusive group (exactly one mode required) | Task 2 parser block |
| No mode flag → `SystemExit` | Task 2 test 2 |
| `--email --anyone` → `SystemExit` | Task 2 test 3 |
| `--email --get-link` → `SystemExit` | Task 2 test 4 |
| `--anyone --get-link` → `SystemExit` | Task 2 test 5 |
| `--get-link --role writer` → `UsageError` | Task 2 test 6 |
| `--anyone` without `--confirm-public` → `UsageError` | Task 2 test 7 |
| 403 → `AuthError` (exit 4) | Pre-existing `_map_http_error()` — no code change needed |
| SKILL.md updated | Task 3 |

All 15 spec tests covered. No placeholders. `share_file()` signature in Task 1 matches the dispatch call in Task 2. ✓
