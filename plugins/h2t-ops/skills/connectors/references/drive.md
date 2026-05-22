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

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- Ambiguous folder name: use `upload-folder --parent-id` or inspect folders first.
- Existing same-name file: default is skip; use `--update-existing` only when replacement is intended.
- Cloud HTML deployment: preserve relative paths with `upload-folder`, not single-file upload.
