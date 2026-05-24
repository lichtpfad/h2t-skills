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

# Get link and check whether it is actually accessible (no permission change)
h2t-ops drive share <FILE_ID> --get-link --json
```

**Flags (exactly one required — argparse mutually exclusive group):**
- `--email <addr>` — invite a specific user
- `--anyone` — set link access (anyone with the link)
- `--get-link` — read-only: return `webViewLink` and actual link shareability state

**Additional flags:**
- `--role <role>` — `reader` (default) | `writer` | `commenter`; valid only with `--email` or `--anyone`; `UsageError` with `--get-link`
- `--json` — machine-readable envelope

**Invalid combinations → `UsageError` (exit 2):**
- No mode flag provided
- `--email --anyone` (argparse mutually exclusive)
- `--email --get-link` (argparse mutually exclusive)
- `--anyone --get-link` (argparse mutually exclusive)
- `--get-link --role <role>` (explicit post-parse check)

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
- Calls `permissions().list(fileId=file_id, fields="permissions(type,role)", supportsAllDrives=True)`
- Sets `link_accessible=True` if any permission with `type=anyone` exists, `False` otherwise
- Does NOT call `permissions().create()` — purely read-only

**Mode: `--email`**
- Calls `permissions().create()` with:
  - `type=user`, `role=<role>`, `emailAddress=<email>`
  - `sendNotificationEmail=False`
  - `supportsAllDrives=True`
- Fetches `webViewLink` from `files().get()` and includes in result
- Includes `granted_to: <email>` in output for audit trail

**Mode: `--anyone`**
- Calls `permissions().create()` with:
  - `type=anyone`, `role=<role>`
  - `sendNotificationEmail=False`
  - `supportsAllDrives=True`
- Fetches `webViewLink` and includes in result
- Includes `granted_to: "anyone"` in output

## JSON Output

**`--email` mode:**
```json
{
  "kind": "drive_share/v1",
  "file_id": "...",
  "web_view_link": "https://docs.google.com/...",
  "permission_id": "...",
  "role": "writer",
  "type": "user",
  "granted_to": "user@example.com"
}
```

**`--anyone` mode:**
```json
{
  "kind": "drive_share/v1",
  "file_id": "...",
  "web_view_link": "https://docs.google.com/...",
  "permission_id": "...",
  "role": "reader",
  "type": "anyone",
  "granted_to": "anyone"
}
```

**`--get-link` mode:**
```json
{
  "kind": "drive_share/v1",
  "file_id": "...",
  "web_view_link": "https://docs.google.com/...",
  "type": "get-link",
  "link_accessible": true
}
```

`permission_id` and `granted_to` are omitted in `--get-link` mode.
`granted_to` is included for `--email` and `--anyone` as an audit trail — callers should log/store this to verify and recover from wrong-permission grants.

## Error Handling

| Situation | Error |
|-----------|-------|
| No mode flag provided | `UsageError` (exit 2): "one of --email, --anyone, --get-link is required" |
| `--email` + `--anyone` | argparse mutually exclusive group → `UsageError` (exit 2) |
| `--email` + `--get-link` | argparse mutually exclusive group → `UsageError` (exit 2) |
| `--anyone` + `--get-link` | argparse mutually exclusive group → `UsageError` (exit 2) |
| `--get-link` + `--role` | explicit post-parse check → `UsageError` (exit 2) |
| `--email` without `--role` | defaults to `reader` |
| File not found | `NotFoundError` (exit 5) |
| Insufficient sharing permissions | `ProviderError` (exit 1) |
| Invalid role | argparse `choices` validation |

## Testing (`tests/connectors/test_drive_share.py`)

All tests use a mock `DriveClient.service` — no real API calls.

1. `--email` calls `permissions().create()` with `type=user`, `sendNotificationEmail=False`
2. `--anyone` calls `permissions().create()` with `type=anyone`, no `emailAddress` key in body
3. `--get-link` calls `files().get()` + `permissions().list()`, never `permissions().create()`
4. `--get-link` returns `link_accessible=True` when `type=anyone` permission exists
5. `--get-link` returns `link_accessible=False` when no `anyone` permission exists
6. `--email` result includes `granted_to` with the email address
7. `--anyone` result includes `granted_to: "anyone"`
8. `--get-link` result does not include `granted_to` or `permission_id`
9. No mode flag → `UsageError`
10. `--email --anyone` → `UsageError`
11. `--email --get-link` → `UsageError`
12. `--anyone --get-link` → `UsageError`
13. `--get-link --role writer` → `UsageError`
14. Default role is `reader` when `--role` omitted with `--email`

## Out of Scope

- `--notify` / custom notification message (add when user requests)
- Listing current permissions (`drive share list <FILE_ID>`)
- Removing permissions (`drive share remove <FILE_ID> --permission-id`)
- Domain-restricted sharing (`type=domain`)
