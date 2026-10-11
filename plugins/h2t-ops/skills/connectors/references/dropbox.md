# Dropbox Connector

Dropbox over HTTP API v2: reads, plus two writes (`upload`, `link`). Its reason to exist is the case the desktop
client cannot serve: an **online-only placeholder** has no bytes on disk, so
`ffmpeg` and ordinary reads fail on it with `Invalid argument` while the API
streams the content fine (~11 MB/s measured).

## Command Map

| intent | command |
| --- | --- |
| who am I, which namespace | `h2t-ops dropbox account --json` |
| list a folder | `h2t-ops dropbox list /HOU2TOUCH --json` |
| walk a tree | `h2t-ops dropbox list /HOU2TOUCH --recursive --limit 500 --json` |
| metadata for one path | `h2t-ops dropbox meta /HOU2TOUCH/clip.wav --json` |
| stream a file to disk | `h2t-ops dropbox download /HOU2TOUCH/clip.wav ~/Downloads --json` |
| gzip content under a plain name | `h2t-ops dropbox download /x/seq.prproj ./seq.prproj --gunzip --json` |
| upload a file (write) | `h2t-ops dropbox upload ./a.py "/HOU2TOUCH/X/a.py" --confirm-write --json` |
| upload a folder (write) | `h2t-ops dropbox upload ./dir "/HOU2TOUCH/X" --confirm-write --json` |
| public link (write) | `h2t-ops dropbox link "/HOU2TOUCH/X/a.py" --confirm-public --json` |

## Writes

- `upload` never overwrites: mode `add`, no autorename. A different file already at the
  path comes back as `"status": "exists"` and stays as it was. A file with the **same
  content** is accepted by Dropbox as a no-op and reported as `uploaded`; no copy is made.
  The stored size is read back and must equal the local size. A folder's files go under
  `dest` with their sub-paths; one failure does not stop the rest, and the command then
  fails with the list. Files over 150 MB are refused (upload sessions not implemented).
- `link` returns the path's existing shared link (with its visibility) or creates a
  public one.
- Both refuse without their flag (`--confirm-write`, `--confirm-public`) before any token
  is read. Restate the target and get the user's yes before running them.
- Run them from PowerShell or cmd, not Git Bash: MSYS rewrites `/HOU2TOUCH/...` into
  `C:/Program Files/Git/HOU2TOUCH/...` and the write lands on a wrong path or is refused.

## Paths are from the Dropbox root, not from the disk

```text
E:\DROPBOX\LichtPfad Dropbox\HOU2TOUCH\COURSES_DEVELOPMENT\LISBON\x.wav
                             └────────────── API path ──────────────┘
                             /HOU2TOUCH/COURSES_DEVELOPMENT/LISBON/x.wav
```

The root itself is `""` or `/`, never a drive letter.

## Business accounts: the namespace gate

On a Business account the member's home namespace is not the team root, and team
folders are invisible without a `Dropbox-API-Path-Root` header. The connector
resolves it itself from `users/get_current_account` → `root_info.root_namespace_id`
and applies it only when it differs from `home_namespace_id`. Nothing is hardcoded;
`dropbox account` prints both ids and the value actually applied.

## Token

`DROPBOX_TOKEN` in `~/.h2t/config/secrets/secrets.env` — the file `load_secrets`
reads. `~/.h2t/config/secrets/dropbox.env` is also read, for the per-provider file
shape, but it is read by this connector alone.

A token from the app dashboard's **Generate** button is short-lived (~4 hours).
For durable access set `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` and
`DROPBOX_REFRESH_TOKEN`; the connector exchanges them for an access token when
`DROPBOX_TOKEN` is absent.

Scopes: `account_info.read`, `files.metadata.read`, `files.content.read`; for writes also
`files.content.write` (upload) and `sharing.write` (link).

To get the refresh token once: open
`https://www.dropbox.com/oauth2/authorize?client_id=<APP_KEY>&response_type=code&token_access_type=offline`,
Allow, and exchange the code at `oauth2/token` (`grant_type=authorization_code`, app key and
secret). The code is single-use and useless without the secret.

`account_info.read` is not optional even for a pure file read: the namespace gate
above resolves through `users/get_current_account` on the first request, so a token
carrying only the two `files.*` scopes fails with `missing_scope` before it reaches
a single file.

When the refresh triple is configured, a 401 on an aged-out access token is
refreshed once and the call retried. `missing_scope` is not retried: a new token
carries the same scopes.

## Download safety

`download` streams to a `.part` sibling and renames on success, so a dropped
connection leaves the destination untouched rather than truncated.

`--gunzip` decompresses in chunks against a ceiling — 512 MiB by default,
`DROPBOX_MAX_GUNZIP_BYTES` to change it. The compression ratio is the uploader's
choice, so a few MB of gzip can expand to as much as it likes.

## Common Failures

- `DROPBOX_SCOPE_MISSING`: a token issued **before** a scope was enabled keeps the
  scopes it was born with. Enable the scope, Submit, then generate a new token.
- `DROPBOX_TOKEN invalid or expired`: the ~4-hour dashboard token ran out.
- `NotFound`: check the path is from the Dropbox root and that the namespace gate
  above applies — a team path under the home namespace reads as missing.
