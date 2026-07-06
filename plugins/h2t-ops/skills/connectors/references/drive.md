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
| markdown to a new Google Doc | `h2t-ops drive upload ./brief.md --parent-id DRIVE_FOLDER_ID --title "Interview Guide" --json` |
| upload folder | `h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json` |
| list tabs in a Google Doc | `h2t-ops drive docs-tab list DOC_ID --json` |
| add a new tab to a Google Doc | `h2t-ops drive docs-tab add DOC_ID "Tab Title" --json` |
| write markdown content to a tab | `h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file notes.md --json` |
| read text from a tab | `h2t-ops drive docs-tab read DOC_ID TAB_ID --json` |
| overwrite tab content (clear first) | `h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file notes.md --clear-first --json` |
| get file metadata by id | `h2t-ops drive get-file FILE_ID --json` |
| trash a file (recoverable) | `h2t-ops drive trash FILE_ID --confirm-name "exact name" --json` |
| permanently delete a file | `h2t-ops drive delete FILE_ID --confirm-name "exact name" --confirm-permanent --json` |
| create a new Google Doc | `h2t-ops drive docs create "Title" --json` |
| upload file and update if exists | `h2t-ops drive upload ./note.md --folder "Folder" --update-existing --json` |

## Safety

- List, search, folders, download, export, get-file, and docs-tab read are read-only.
- Upload and upload-folder write to Drive and require explicit user intent.
- `docs-tab write` inserts content at the start of an existing tab — use `--clear-first` to replace content instead of appending.
- `trash` is recoverable from Drive Trash. `delete` is **permanent and irreversible** — requires `--confirm-permanent`.
- Both `trash` and `delete` require `--confirm-name` matching the exact file name (case-insensitive) as a safety guard.
- Run `upload-folder --dry-run --json` before a real recursive upload.
- Do not write ad-hoc Google Drive API scripts when a command is missing; use `issue-policy.md`.

## Commands

```bash
h2t-ops drive search "lecture" --max 20 --json
h2t-ops drive list <folder_id_from_url> --json
h2t-ops drive export FILE_ID_FROM_SEARCH --format md --dest ./lecture.md --json
h2t-ops drive export FILE_ID_FROM_SEARCH --format text --dest ./lecture.txt --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --dry-run --json
h2t-ops drive upload-folder ./deploy --parent-id DRIVE_FOLDER_ID --update-existing --json

# Single-file upload with update-existing
h2t-ops drive upload ./note.md --folder "Target" --update-existing --json

# Get file metadata
h2t-ops drive get-file FILE_ID --json

# Create a new Google Doc
h2t-ops drive docs create "My Report" --json
h2t-ops drive docs create "My Report" --folder-id FOLDER_ID --json

# Trash/delete (destructive — see Manual E2E Smoke Recipe below)
h2t-ops drive trash FILE_ID --confirm-name "exact-file-name.txt" --json
h2t-ops drive delete FILE_ID --confirm-name "exact-file-name.txt" --confirm-permanent --json

# Google Docs tabs
h2t-ops drive docs-tab list DOC_ID --json
h2t-ops drive docs-tab add DOC_ID "Meeting Notes" --json   # → returns tab_id
h2t-ops drive docs-tab read DOC_ID TAB_ID --json
h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file ./notes.md --json
h2t-ops drive docs-tab write DOC_ID TAB_ID --content-file ./notes.md --clear-first --json
```

## URL helpers

- Folder link pattern:
  `https://drive.google.com/drive/folders/<FOLDER_ID>` -> folder id is the part after `/folders/`.
- File link pattern:
  `https://drive.google.com/file/d/<FILE_ID>/...` -> file id is the part after `/d/`.
- Google Doc link pattern:
  `https://docs.google.com/document/d/<DOC_ID>/...` -> export with `h2t-ops drive export <DOC_ID> --format text --json`.
- Google Sheet link pattern:
  `https://docs.google.com/spreadsheets/d/<SHEET_ID>/...` -> export with `h2t-ops drive export <SHEET_ID> --format csv --json` or `--format xlsx`.
- Google Slides link pattern:
  `https://docs.google.com/presentation/d/<SLIDES_ID>/...` -> export with `h2t-ops drive export <SLIDES_ID> --format pdf --json` or `--format pptx`.

For folder links, there is no dedicated “download folder” command; enumerate entries via `list`, then download each file id with `download`.

## Auth

Drive uses the same Google OAuth token family as Gmail and Calendar.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- `--format txt` is accepted as an alias for `--format text`; `--format markdown` is accepted as an alias for `--format md`.
- Binary export formats (`pdf`, `docx`, `xlsx`, `pptx`) write raw bytes to `--dest`; they cannot be used with `--print`.
- Markdown → Google Doc: `upload ./brief.md` converts natively via Drive (`.md`/`.docx`/`.html` are in the convert map) — no pandoc dependency. Use `--title` to name the resulting doc; without it the filename stem is used.
- Markdown export works without optional `html2text`; when `html2text` is not installed, h2t-ops uses a smaller stdlib HTML-to-Markdown fallback.
- Ambiguous folder name: use `upload-folder --parent-id` or inspect folders first.
- Existing same-name file: default is skip; use `--update-existing` only when replacement is intended.
- Cloud HTML deployment: preserve relative paths with `upload-folder`, not single-file upload.
- `delete` without `--confirm-permanent` raises UsageError — this is intentional.
- `trash`/`delete` name mismatch (case-insensitive): command checks actual Drive file name before executing.

## Manual E2E Smoke Recipe

> Run only with `$env:H2T_E2E_CONNECTORS="1"` and a safe test folder.
> Destructive commands (trash, delete) require explicit manual approval per resource.
> Automated E2E for destructive ops is intentionally excluded from `tests/e2e/`.

### Upload + update existing + get-file

```python
# test_drive_api_coverage_live (to be wired in final evidence branch)
import os, sys, subprocess
from pathlib import Path

folder_id = os.environ["H2T_E2E_DRIVE_FOLDER_ID"]
title = "h2t-e2e-connector-api-drive.md"
tmp = Path("tmp-e2e-drive.md")

# First upload
tmp.write_text("# First\n\nHello", encoding="utf-8")
result = subprocess.run(
    [sys.executable, "-m", "h2t_ops.cli", "drive", "upload",
     str(tmp), "--parent-id", folder_id, "--update-existing", "--json"],
    capture_output=True, text=True,
)
assert result.returncode == 0
import json
data = json.loads(result.stdout)
file_id = data["result"]["file_id"]

# Second upload (update)
tmp.write_text("# Second\n\nHello **bold**", encoding="utf-8")
result2 = subprocess.run(
    [sys.executable, "-m", "h2t_ops.cli", "drive", "upload",
     str(tmp), "--parent-id", folder_id, "--update-existing", "--json"],
    capture_output=True, text=True,
)
assert result2.returncode == 0
assert json.loads(result2.stdout)["result"]["action"] == "updated"

# get-file
gf = subprocess.run(
    [sys.executable, "-m", "h2t_ops.cli", "drive", "get-file", file_id, "--json"],
    capture_output=True, text=True,
)
assert gf.returncode == 0

# Cleanup: trash then delete manually
# h2t-ops drive trash FILE_ID --confirm-name "h2t-e2e-connector-api-drive" --json
# h2t-ops drive delete FILE_ID --confirm-name "h2t-e2e-connector-api-drive" --confirm-permanent --json
```
