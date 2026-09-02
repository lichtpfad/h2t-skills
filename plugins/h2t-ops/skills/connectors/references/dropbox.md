# Dropbox Connector

Read-only Dropbox over HTTP API v2. Its reason to exist is the case the desktop
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

Scopes: `files.metadata.read` and `files.content.read`.

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
