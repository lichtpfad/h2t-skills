# Design: h2t-ops drive share (#168)

**Date:** 2026-05-24
**Issue:** [#168](https://github.com/lichtpfad/h2t-skills/issues/168)
**Approach:** A — single `share` subcommand with mutually exclusive flags

## Problem

After uploading a file via `h2t-ops drive upload`, there is no CLI way to share it
with a collaborator or set link permissions. Users must switch to the Drive web UI,
breaking the automation flow.

## Solution Overview

Add `h2t-ops drive share <FILE_ID>` with three operating modes controlled by flags:
invite a user, open access by link, or retrieve the existing link.

## CLI Interface

```bash
# Invite a specific user (role: reader | writer | commenter; default: reader)
h2t-ops drive share <FILE_ID> --email user@example.com --role writer --json

# Make file accessible to anyone with the link
h2t-ops drive share <FILE_ID> --anyone --role reader --json

# Get the existing shareable link without changing permissions
h2t-ops drive share <FILE_ID> --get-link --json
```

**Flags:**
- `--email <addr>` — invite a specific user; mutually exclusive with `--anyone`
- `--anyone` — set link access; mutually exclusive with `--email`
- `--role <role>` — `reader` (default) | `writer` | `commenter`; invalid with `--get-link`
- `--get-link` — read-only mode, returns `webViewLink` without modifying permissions
- `--json` — machine-readable envelope

## Architecture

Two files modified, following the existing Drive connector pattern:

| File | Change |
|------|--------|
| `h2t_ops/connectors/drive/client.py` | Add `share_file()` method |
| `h2t_ops/connectors/drive/commands.py` | Register `share` subparser + dispatch |
| `tests/connectors/test_drive_share.py` | New test file |

No new classes or modules. `share_file()` sits alongside `upload_file()` in `DriveClient`.

## Backend: `share_file()`

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
```

**Mode: `--get-link`**
- Calls `files().get(fileId=file_id, fields="id,name,webViewLink", supportsAllDrives=True)`
- Returns link without touching permissions

**Mode: `--email`**
- Calls `permissions().create()` with:
  - `type=user`, `role=<role>`, `emailAddress=<email>`
  - `sendNotificationEmail=False`
  - `supportsAllDrives=True`
- Fetches `webViewLink` from `files().get()` and includes in result

**Mode: `--anyone`**
- Calls `permissions().create()` with:
  - `type=anyone`, `role=<role>`
  - `sendNotificationEmail=False`
  - `supportsAllDrives=True`
- Fetches `webViewLink` and includes in result

## JSON Output

```json
{
  "kind": "drive_share/v1",
  "file_id": "...",
  "web_view_link": "https://docs.google.com/...",
  "permission_id": "...",
  "role": "reader",
  "type": "user" | "anyone" | "get-link"
}
```

`permission_id` is omitted in `--get-link` mode. `email` is never included in output.

## Error Handling

| Situation | Error |
|-----------|-------|
| `--email` + `--anyone` together | `UsageError` (exit 2) |
| `--get-link` + `--role` together | `UsageError` (exit 2) |
| `--email` without `--role` | defaults to `reader` |
| File not found | `NotFoundError` (exit 5) |
| Insufficient sharing permissions | `ProviderError` (exit 1) |
| Invalid role | argparse `choices` validation |

## Testing (`tests/connectors/test_drive_share.py`)

All tests use a mock `DriveClient.service` — no real API calls.

1. `--email` calls `permissions().create()` with `type=user`, `sendNotificationEmail=False`
2. `--anyone` calls `permissions().create()` with `type=anyone`, no `emailAddress` key
3. `--get-link` calls only `files().get()`, never `permissions().create()`
4. `--email` + `--anyone` → `UsageError`
5. `--get-link` + `--role writer` → `UsageError`
6. Result JSON does not contain email address (security invariant)
7. Default role is `reader` when `--role` omitted

## Out of Scope

- `--notify` / custom notification message (add when user requests)
- Listing current permissions (`drive share list <FILE_ID>`)
- Removing permissions (`drive share remove <FILE_ID> --permission-id`)
- Domain-restricted sharing (`type=domain`)
