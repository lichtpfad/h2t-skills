# Drive Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list files | `h2t-ops drive list --max 20 --json` |
| search files | `h2t-ops drive search "presentation" --max 20 --json` |
| list folders | `h2t-ops drive folders --json` |
| download file | `h2t-ops drive download FILE_ID_FROM_SEARCH --dest ./downloads --json` |
| list folder contents by URL | extract folder ID and run `h2t-ops drive list FOLDER_ID --json` |
| export Google Doc | `h2t-ops drive export FILE_ID_FROM_SEARCH --format md --dest ./export.md --json` |
| upload one file | `h2t-ops drive upload ./presentation.html --folder "Uploads" --no-convert --json` |
| upload folder | `h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json` |
| list tabs in a Google Doc | `h2t-ops drive docs-tab list DOC_ID --json` |
| add a new tab to a Google Doc | `h2t-ops drive docs-tab add DOC_ID "Tab Title" --json` |
| write markdown content to a tab | `h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file notes.md --json` |

## Safety

- List, search, folders, download, and export are read-only from Drive's perspective.
- Upload and upload-folder write to Drive and require explicit user intent.
- `docs-tab write` inserts content at the start of an existing tab — use on a freshly created (empty) tab to avoid garbling existing content.
- Run `upload-folder --dry-run --json` before a real recursive upload.
- Do not write ad-hoc Google Drive API scripts when a command is missing; use `issue-policy.md`.

## Commands

```bash
h2t-ops drive search "lecture" --max 20 --json
h2t-ops drive list <folder_id_from_url> --json
h2t-ops drive export FILE_ID_FROM_SEARCH --format md --dest ./lecture.md --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --update-existing --json

# Google Docs tabs
h2t-ops drive docs-tab list DOC_ID --json
h2t-ops drive docs-tab add DOC_ID "Meeting Notes" --json   # → returns tab_id
h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file ./notes.md --json
```

## URL helpers

- Folder link pattern:
  `https://drive.google.com/drive/folders/<FOLDER_ID>` -> folder id is the part after `/folders/`.
- File link pattern:
  `https://drive.google.com/file/d/<FILE_ID>/...` -> file id is the part after `/d/`.

For folder links, there is no dedicated “download folder” command; enumerate entries via `list`, then download each file id with `download`.

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
