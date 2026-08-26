---
title: "h2t-ops Notion Functional Completion - Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-22"
milestone: ""
---
# h2t-ops Notion Functional Completion - Design

Date: 2026-05-22
Status: review-ready
Owner connector: h2t-ops/notion
Issues: #81, #146
Depends on: connector freeze complete (#155)

## Goal

Make the Notion connector functionally complete for practical workspace reads.

The immediate gap is #81: embedded `child_database` blocks inside already-shared
pages are accessible, but current commands can miss them because Notion `/search`
may return zero standalone databases. The broader follow-up is #146: workspace
discovery and parent graph traversal for POS/KB source refs.

This is provider I/O only. h2t-ops must not write POS journal, vault, lake, or
SQLite state.

## Issue Closure Contract

#81 is closed only when embedded database rows are recoverable from a page dump
path, not merely discoverable as ids.

Required closure behavior:

- `find-databases --recursive --with-rows --json` is the canonical
  machine-readable embedded database dump primitive.
- Existing `sync <page_id> <out.md>` remains explicit-file page export.
- `sync --include-databases --recursive --row-limit N` appends discovered
  database row summaries to the explicit markdown output.
- `sync --include-databases --databases-json <out.json>` writes the full
  `notion_database_discovery/v1` payload only to the explicit sidecar path.
- Skill docs must stop implying that plain `sync` is a complete page/workspace
  dump when embedded databases matter.

#146 is closed only after the graph output contains enough structure for future
source refs:

- prior-art audit for older Notion dump/extract scripts;
- `parent_map`, `children_map`, and `parent_chain`;
- raw Notion `parent` objects preserved;
- block-owner resolution for `block_id` parents when practical;
- timestamps and stable source refs.

## Current State

Current command surface:

- `notion get <page_id>`
- `notion blocks <page_id>`
- `notion search <database_id>`
- `notion get-database <database_id>`
- `notion find-databases <page_id>`
- `notion find-project-tasks <project_page_id>`
- `notion create`
- `notion update`
- `notion sync`

Current `find-databases` is shallow: it scans immediate page children only and
returns `child_database` / `linked_database` refs. It does not recursively walk
page trees, query discovered child databases, or emit a graph.

## Prior Art / Reuse Decision

Before implementation, inspect existing Notion dump prior art if present:

- `C:/dev/h2t-business/scripts/notion_dump.py`
- `C:/dev/h2t-business/scripts/notion_extract.py`
- any local `notion_dump`, `notion_extract`, or `NotionClient` helpers found
  by repository search.

The implementation plan must record:

- which traversal ideas are reused;
- which code is intentionally not reused;
- whether old scripts treat `child_database` rows as page dump content;
- any fixture examples worth porting into tests.

Do not copy POS/DOR write behavior from older scripts into the connector.

## Architecture

### Layer 1: #81 Embedded Database Discovery

Add recursive provider-read helpers to `NotionClient`:

- `iter_blocks_recursive(root_page_id, *, max_depth, limit_blocks=None)`
- `find_databases_on_page(page_id, *, recursive=False, max_depth=3)`
- `query_discovered_databases(discovered, *, row_limit=100)`

`child_database` semantics:

- `block.type == "child_database"` means the block id is the database id.
- The database is already accessible when the containing page is accessible.
- Query it via `databases/{id}/query` just like standalone databases.

`linked_database` semantics:

- Preserve linked database support where API response provides a database id.
- If linked metadata lookup fails, return the ref with `accessible=false` and a
  typed reason instead of dropping it.

Traversal semantics:

- Depth is measured from the root page: root page = depth 0, its child blocks =
  depth 1.
- `max_depth` is inclusive.
- Traversal follows Notion block pagination until `next_cursor` is exhausted.
- Traversal is deterministic DFS pre-order.
- Use `visited_block_ids` and `visited_database_ids` to dedupe repeated refs.
- `limit_blocks` is a global cap, not per-page.
- Partial permission failures are collected in `errors[]`; accessible siblings
  continue.
- Negative `max_depth`, `limit_blocks`, or `row_limit` raises `UsageError`.
- `row_limit=0` is allowed and queries metadata only, returning no rows.

### Layer 2: #146 Workspace Search And Graph

Add workspace/discovery helpers:

- `search_workspace(object_type="all", *, limit=None)`
- `graph_page(root_page_id, *, max_depth=3, include_databases=True)`

`search_workspace` uses Notion `/search` and preserves raw parent shapes:

- `workspace`
- `page_id`
- `database_id`
- `block_id`

`graph_page` walks a known root page and emits nodes/edges plus normalized maps.
Logical teamspace/root labels are optional explicit input/config conventions,
not a Notion API truth. Do not pretend Notion exposes reliable teamspace ids for
all nodes.

Block-owner resolution:

- If a node parent is `block_id`, try to resolve that block and attach its
  owner chain.
- If resolution fails due to permissions or API limits, keep the raw
  `block_id` parent and record an error; do not drop the node.

## CLI Surface

### Existing Command Extended

```bash
h2t-ops notion find-databases <page_id> \
  [--recursive] [--max-depth N] [--limit-blocks N] \
  [--with-rows] [--row-limit N] [--json]
```

Default remains shallow for compatibility. `--recursive` enables page-tree walk.
`--with-rows` queries each discovered database and includes rows up to
`--row-limit`.

Backward compatibility:

- `find-databases <page_id>` with no new flags keeps the legacy list shape.
- `find-databases <page_id> --json` with no new flags keeps the legacy list
  under the universal JSON envelope's `result`.
- `--recursive` or `--with-rows` switches `result` to the versioned
  `notion_database_discovery/v1` payload.
- Each versioned database item also preserves legacy aliases:
  `type`, `database_id`, and `title`.

### Existing Sync Extended

```bash
h2t-ops notion sync <page_id> <out.md> \
  [--preserve-metadata] \
  [--include-databases] [--recursive] [--max-depth N] [--row-limit N] \
  [--databases-json <out.json>]
```

Rules:

- Plain `sync` is unchanged.
- `--include-databases` appends a markdown section for discovered database
  refs and row summaries.
- `--databases-json` is allowed only with `--include-databases`.
- All writes remain explicit user-supplied output paths.

### New Commands

```bash
h2t-ops notion search-workspace [--object page|database|all] [--limit N] [--json]

h2t-ops notion graph <root_page_id> \
  [--max-depth N] [--include-databases] [--root-label LABEL] [--json]
```

Both commands are read-only and output to stdout. If file output is added later,
it must be explicit `--out`, never an implicit DOR/POS write.

## Universal Envelope

All examples below are `result` payloads. The CLI JSON output remains wrapped in
the global connector envelope:

```json
{
  "ok": true,
  "provider": "notion",
  "result": {}
}
```

Do not bypass the universal envelope to place `kind` at top level.

## Output Contracts

### Database Discovery Result Payload

```json
{
  "kind": "notion_database_discovery/v1",
  "root_page_id": "...",
  "recursive": true,
  "max_depth": 3,
  "databases": [
    {
      "kind": "child_database",
      "type": "child_database",
      "database_id": "...",
      "title": "...",
      "source_block_id": "...",
      "parent_page_id": "...",
      "path": ["Root", "Section"],
      "accessible": true,
      "source_ref": "notion:database:...",
      "notion_url": "...",
      "last_edited_time": "...",
      "rows": [],
      "row_count": 0
    }
  ],
  "errors": [],
  "stats": {
    "blocks_seen": 0,
    "blocks_skipped": 0,
    "databases_found": 0,
    "databases_queried": 0,
    "duplicate_database_refs": 0,
    "rows_returned": 0
  }
}
```

### Workspace Graph Result Payload

```json
{
  "kind": "notion_workspace_graph/v1",
  "root_page_id": "...",
  "root_label": "optional-explicit-label",
  "nodes": [
    {
      "id": "...",
      "object": "page|database|block",
      "title": "...",
      "parent": {"type": "page_id", "page_id": "..."},
      "parent_chain": ["..."],
      "source_ref": "notion:page:...",
      "notion_url": "...",
      "created_time": "...",
      "last_edited_time": "..."
    }
  ],
  "edges": [
    {"from": "...", "to": "...", "relation": "contains|parent|linked_database"}
  ],
  "parent_map": {"child_id": "parent_id"},
  "children_map": {"parent_id": ["child_id"]},
  "errors": [],
  "stats": {"nodes": 0, "edges": 0}
}
```

Human/markdown output may summarize the same data, but `--json` plus the
universal envelope is the authoritative machine contract.

## Boundary Rules

- No POS, vault, lake, `~/.dor/context`, `pos.db`, or `dor.db` writes.
- No hidden workspace root mapping. Root/teamspace labels must be explicit input
  or future config.
- Preserve lazy imports: `commands.py` must not import `notion_client` or `httpx`
  at module scope.
- Preserve typed errors: auth/permission denied -> `AuthError`, missing resource
  -> `NotFoundError`, network -> `NetworkError`.
- `create` and `update` remain existing behavior.
- `sync` remains an explicit-output command; new database sidecars require
  explicit `--databases-json`.
- Provider output is evidence/source metadata, not accepted POS capture.
- POS capture generation, KB registration, and privacy policy decisions happen
  outside this connector.

## Tests To Add

Client tests:

- `test_find_databases_shallow_keeps_existing_behavior`
- `test_find_databases_recursive_collects_child_database_in_nested_page`
- `test_find_databases_with_rows_queries_discovered_child_database`
- `test_find_databases_preserves_inaccessible_linked_database_ref`
- `test_iter_blocks_recursive_respects_max_depth`
- `test_iter_blocks_recursive_paginates_children`
- `test_iter_blocks_recursive_dedupes_seen_blocks_and_databases`
- `test_iter_blocks_recursive_collects_partial_permission_errors`
- `test_search_workspace_preserves_parent_shapes`
- `test_graph_page_returns_nodes_edges_and_maps`
- `test_graph_page_resolves_block_id_parent_when_accessible`
- `test_graph_page_preserves_block_id_parent_when_resolution_fails`

Command tests:

- `test_find_databases_parser_accepts_recursive_with_rows_row_limit`
- `test_find_databases_dispatch_passes_recursive_options`
- `test_find_databases_json_legacy_shape_without_new_flags`
- `test_sync_include_databases_requires_explicit_paths_for_json_sidecar`
- `test_sync_include_databases_appends_markdown_section`
- `test_search_workspace_parser_registered`
- `test_graph_parser_registered`
- `test_commands_import_does_not_import_sdk`
- `test_json_output_wraps_result_in_universal_envelope`

Boundary tests:

- grep/import guard: no POS/DOR/vault/lake references in
  `h2t_ops/connectors/notion`.
- no default file writes from new commands.
- no implicit DOR/POS writes from extended `sync`.

## Live Smoke

Read-only smoke:

```bash
h2t-ops notion find-databases <real_page_id> --recursive --json
h2t-ops notion find-databases <real_page_id> --recursive --with-rows --row-limit 5 --json
h2t-ops notion search-workspace --object page --limit 5 --json
h2t-ops notion graph <real_root_page_id> --max-depth 2 --json
```

Explicit-output smoke:

```bash
h2t-ops notion sync <real_page_id> ./tmp/notion-page.md \
  --include-databases --recursive --row-limit 5 \
  --databases-json ./tmp/notion-databases.json
```

Expected evidence:

- embedded databases are found even if `/search` returns zero databases;
- queried database rows are counted separately from page/block counts;
- graph includes `parent_map`, `children_map`, and `parent_chain`;
- no POS/DOR writes occur;
- token leak scan is clean.

## Implementation Order

1. #81 first: recursive `find-databases` + optional row query.
2. #81 dump closure: `sync --include-databases` using the same discovery helper.
3. #146 prior-art audit and fixture selection.
4. #146 `search-workspace` and `graph`.
5. Update Notion skill docs after E2E.

## Out Of Scope

- POS source registry / KB ingestion.
- Automatic Notion teamspace inference as truth.
- Bulk workspace dump to local lake.
- Notion writes beyond existing create/update behavior.
