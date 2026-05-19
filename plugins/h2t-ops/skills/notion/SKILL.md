---
name: notion
description: "Reads and writes Notion pages and databases via the h2t CLI. Use for GTD tasks, creating pages, querying databases, syncing pages to markdown. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database', 'h2t:notion'"
compatibility: "Requires the `h2t` CLI (run /h2t-core:setup) and NOTION_API_TOKEN in ~/.dor/secrets.env or ~/.config/notion/token"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# Notion (h2t connector)

## Availability (cross-platform contract)

`h2t --version` exits 0 when installed (identical on PowerShell and POSIX — no shell idioms).
If it fails: run `/h2t-core:setup`. `h2t doctor` reports version, install path, connectors,
and secrets presence (no network).

## Secrets

`NOTION_API_TOKEN` resolved in order: env var (incl. `~/.dor/secrets.env` if loaded) → `~/.config/notion/token`.
Missing → exit 3 (`config`) with hint.

## Commands

| Command | Purpose |
|---|---|
| `h2t notion get <page-id>` | page blocks as markdown (raw blocks with `--json`) |
| `h2t notion blocks <page-id> [--limit N]` | raw/markdown blocks |
| `h2t notion search <database-id> [--filter "Status=Done"] [--filter-json '{...}'] [--limit N]` | query database |
| `h2t notion get-database <database-id> [--limit N]` | database items as markdown |
| `h2t notion find-databases <page-id>` | list databases on a page |
| `h2t notion create <parent-id> "Title" [--content "md" \| --file f.md] [--database]` | create page |
| `h2t notion update <page-id> [--title T] [--append "md" \| --file f.md] [--replace]` | update page |
| `h2t notion sync <page-id> <out.md> [--preserve-metadata]` | write page to a file |

Output flags (every command): `--json` (raw envelope), `--format md` (markdown/table),
default = concise human text.

## Examples

```bash
h2t notion get 1a2b3c4d --format md
h2t notion search 9f8e7d6c --filter "Status=In progress" --json
h2t notion create 1a2b3c4d "Sprint notes" --file notes.md
h2t notion sync 1a2b3c4d ./export/page.md --preserve-metadata
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | provider/runtime error |
| 2 | usage / bad args |
| 3 | config / secrets missing |
| 4 | auth / permission denied |
| 5 | not found / empty resource |
| 6 | network / timeout |

`--json` errors go to stderr as `{"ok":false,"provider":"notion","error":{...}}`; exit is non-zero.

## When to use / not use

- ✅ Read/write Notion pages, query databases, sync a page to markdown.
- ❌ Bulk export of an entire workspace — out of scope.
- ❌ Do NOT fall back to raw HTTP if a command fails — report the exit code/error.

## Deprecated

`h2t ingest notion …` still works (forwards here) but prints a deprecation notice to
stderr unless `--json`. Migrate call sites to `h2t notion …`.
