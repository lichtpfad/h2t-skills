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

## Common Failures

- Search returns no databases but page contains child databases: use `find-databases PAGE_ID`.
- Permission error: share the Notion page/database with the integration.
- Task creation request: confirm whether the user wants a Notion provider write or a POS/coordinator proposal.
