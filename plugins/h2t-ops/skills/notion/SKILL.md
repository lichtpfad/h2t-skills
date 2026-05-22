---
name: h2t-ops:notion
description: "Reads and writes Notion pages and databases via the h2t-ops CLI. Use for GTD tasks, creating pages, querying databases, syncing pages to markdown. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database', 'h2t-ops:notion'"
compatibility: "Requires the `h2t-ops` CLI (run /h2t-core:setup) and NOTION_API_TOKEN in ~/.dor/secrets.env or ~/.config/notion/token"
metadata:
  author: lichtpfad
  version: 2.1.0
---

# Notion (h2t-ops connector)

## POS Boundary

For POS and daily-loop workflows, follow the shared boundary reference:
`../../references/pos-operational-boundary.md`. This skill may read Notion data
through `h2t-ops`, but must not write POS journal rows, mutate `~/.dor/pos.db`,
or modify vault/lake directly. Emit structured proposed captures until POS
journal commands exist.

## Availability (cross-platform contract)

`h2t-ops --version` exits 0 when installed (identical on PowerShell and POSIX — no shell idioms).
If it fails: run `/h2t-core:setup`. `h2t-ops doctor` reports version, install path, connectors,
and secrets presence (no network).

## Secrets

`NOTION_API_TOKEN` resolved in order: env var (incl. `~/.dor/secrets.env` if loaded) → `~/.config/notion/token`.
Missing → exit 3 (`config`) with hint.

## Commands

| Command | Purpose |
|---|---|
| `h2t-ops notion get <page-id>` | page blocks as markdown (raw blocks with `--json`) |
| `h2t-ops notion blocks <page-id> [--limit N]` | raw/markdown blocks |
| `h2t-ops notion search <database-id> [--filter "Status=Done"] [--filter-json '{...}'] [--limit N]` | query database |
| `h2t-ops notion get-database <database-id> [--limit N]` | database items as markdown |
| `h2t-ops notion find-databases <page-id> [--recursive] [--with-rows] [--row-limit N]` | discover embedded/linked databases |
| `h2t-ops notion create <parent-id> "Title" [--content "md" \| --file f.md] [--database]` | create page |
| `h2t-ops notion update <page-id> [--title T] [--append "md" \| --file f.md] [--replace]` | update page |
| `h2t-ops notion sync <page-id> <out.md> [--include-databases] [--databases-json out.json]` | explicit page export; embedded DBs only when requested |
| `h2t-ops notion search-workspace [--object page\|database\|all] [--limit N]` | search shared workspace objects |
| `h2t-ops notion graph <root-page-id> [--max-depth N] [--include-databases]` | emit source-ref graph for a page subtree |

Output flags (every command): `--json` (raw envelope), `--format md` (markdown/table),
default = concise human text.

Plain `sync` is not a complete workspace dump. If embedded databases matter, use
`find-databases --recursive --with-rows --json` or `sync --include-databases`
with an explicit `--databases-json` sidecar.

Connector output is provider evidence/source metadata. POS/KB registration and
promotion happen outside this skill.

## Examples

```bash
h2t-ops notion get 1a2b3c4d --format md
h2t-ops notion search 9f8e7d6c --filter "Status=In progress" --json
h2t-ops notion find-databases 1a2b3c4d --recursive --with-rows --row-limit 25 --json
h2t-ops notion create 1a2b3c4d "Sprint notes" --file notes.md
h2t-ops notion sync 1a2b3c4d ./export/page.md --include-databases --databases-json ./export/page.databases.json
h2t-ops notion search-workspace --object all --limit 25
h2t-ops notion graph 1a2b3c4d --max-depth 3 --include-databases
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

`h2t-ops ingest notion …` still works (forwards here) but prints a deprecation notice to
stderr unless `--json`. Migrate call sites to `h2t-ops notion …`.

> In the internal umbrella CLI, `h2t notion …` may be available later via h2t-ai delegation. Skills should call `h2t-ops …` directly unless a project explicitly provides the umbrella bridge.
