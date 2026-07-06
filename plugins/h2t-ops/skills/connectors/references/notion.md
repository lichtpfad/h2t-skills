# Notion Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| get page as markdown | `h2t-ops notion get PAGE_ID --format md` |
| get page blocks | `h2t-ops notion blocks PAGE_ID --json` |
| query/filter database | `h2t-ops notion search DATABASE_ID --limit 25 --json` |
| get database items | `h2t-ops notion get-database DATABASE_ID --limit 25 --json` |
| search workspace | `h2t-ops notion search-workspace --object all --limit 25 --json` |
| graph page tree | `h2t-ops notion graph PAGE_ID --max-depth 3 --json` |
| find embedded databases | `h2t-ops notion find-databases PAGE_ID --json` |
| create page | `h2t-ops notion create PAGE_ID "Title" --content "Body" --json` |
| update page | `h2t-ops notion update PAGE_ID --title "Updated title" --json` |
| sync page to markdown | `h2t-ops notion sync PAGE_ID ./notion-page.md --json` |
| create typed database | `h2t-ops notion create-database PARENT_PAGE_ID --title "Partners" --properties-file schema.json --json` |
| add/rename/remove columns | `h2t-ops notion patch-db-schema DB_ID --properties-file schema.json --json` |
| create database row | `h2t-ops notion create-db-item DB_ID --title "Task" --json` |
| update database row properties | `h2t-ops notion update-db-item PAGE_ID --property-json '{"Status":{"select":{"name":"Done"}}}' --json` |
| archive page (safe, title-verified) | `h2t-ops notion archive PAGE_ID --confirm-title "Exact Title" --json` |
| append markdown file as blocks | `h2t-ops notion append-blocks PAGE_ID --content-file ./content.md --json` |
| replace page content (safe, title-verified) | `h2t-ops notion replace-content PAGE_ID --content-file ./content.md --confirm-title "Exact Title" --json` |

## Safety

- Get, blocks, database reads, search-workspace, graph, and find-databases are provider read-oriented.
- Sync reads from Notion but writes markdown to a local filesystem destination; use it only with explicit user intent and an explicit destination path.
- Create and update are Notion provider writes and require explicit user intent.
- Notion provider writes execute provider-specific writes only; POS/coordinator owns the decision to accept tasks, journal entries, or KB promotions.
- Do not include private Notion page bodies in GitHub issues.

## Commands

```bash
h2t-ops notion search-workspace --object all --limit 25 --json
h2t-ops notion graph PAGE_ID --max-depth 3 --json
h2t-ops notion find-databases PAGE_ID --json
h2t-ops notion search DATABASE_ID --limit 25 --json
h2t-ops notion get-database DATABASE_ID --limit 25 --json
```

## Auth

Notion expects `NOTION_API_TOKEN` from environment, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, legacy `~/.dor/secrets.env`, or `~/.config/notion/token`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Database schema ops (API 2025-09-03)

The SDK targets Notion API `2025-09-03`, where a database owns one or more
**data sources** and the column schema lives on the data source, not the
database. This shapes the write commands:

- `create-database` wraps the properties map in `initial_data_source` (not a
  flat top-level `properties`). The map must include exactly one title-typed
  property, e.g. `{"Company": {"title": {}}}`.
- `patch-db-schema` resolves the database's first data source and calls
  `data_sources.update`; pass `--data-source-id` to target a specific one on a
  multi-source database. Rename the title column in the same call with
  `{"OldName": {"name": "NewName"}}`.
- `create-db-item` resolves the title property **by type** from the data source
  schema, so it works after the title column is renamed away from `Name`.

`--properties-file` is a JSON file holding the Notion `properties` map.

## Common Failures

- Search returns no databases but page contains child databases: use `find-databases PAGE_ID`.
- Permission error: share the Notion page/database with the integration.
- Task creation request: confirm whether the user wants a Notion provider write or a POS/coordinator proposal.
- `create-database` needs a **page** parent, not a database — a database cannot parent another database directly.

## Manual E2E Smoke Recipe

> Automated live E2E never archives pages without explicit user approval.
> Run only with `$env:H2T_E2E_CONNECTORS="1"`.

### Create/update DB item (safe, no archive)

```python
import subprocess, json

db_id = "<your-database-id>"

# Create item
result = subprocess.run(
    ["h2t-ops", "notion", "create-db-item", db_id,
     "--title", "h2t-e2e-connector-api-notion", "--json"],
    capture_output=True, text=True, check=True,
)
page = json.loads(result.stdout)["result"]
page_id = page["id"]

# Update properties
subprocess.run(
    ["h2t-ops", "notion", "update-db-item", page_id,
     "--property-json", '{"Name":{"title":[{"text":{"content":"h2t-e2e-updated"}}]}}',
     "--json"],
    check=True,
)

# Append blocks
subprocess.run(
    ["h2t-ops", "notion", "append-blocks", page_id,
     "--content-file", "./smoke-append.md", "--json"],
    check=True,
)
```

Cleanup: Archive the created page manually after smoke.
Archive command (requires exact title confirmation):

```bash
h2t-ops notion archive <page_id> --confirm-title "h2t-e2e-updated" --json
```

Replace-content (requires exact title confirmation):

```bash
h2t-ops notion replace-content <page_id> --content-file ./new-content.md --confirm-title "h2t-e2e-updated" --json
```
