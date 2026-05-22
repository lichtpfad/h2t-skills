# Notion Prior-Art Audit

Date: 2026-05-22

Issues: #81, #146

## Scripts Found

- `C:\dev\h2t-business\scripts\notion_dump.py` - Keep as a behavior reference for traversal, cursor pagination, recursive block dumps, and embedded database row dumping; reject for direct reuse because it is a standalone urllib/JSON utility outside current connector patterns.
- `C:\dev\h2t-business\scripts\notion_extract.py` - Keep as a behavior reference for `_children` traversal, `block_id` parent resolution, parent/children maps, and property flattening; reject for direct reuse because it is an offline dump extractor, not provider I/O inside `h2t_ops.connectors.notion`.
- `C:\dev\h2t-business\scripts\__pycache__\notion_extract.cpython-311.pyc` - Reject; compiled cache only, no source to reuse or audit beyond confirming the historical extractor existed.

## Required Answers

- Traversal/pagination idea reused: true. The concepts are reusable because `notion_dump.py` has `search_all`, `get_all_blocks`, and `query_database_all` loops using `start_cursor`, `has_more`, and `next_cursor`; the new connector should reimplement the same behavior through the Notion SDK and current error/envelope boundaries.
- Old code reused verbatim: no.
- Old scripts dump `child_database` rows: true. Evidence: `notion_dump.py` defines `fetch_embedded_dbs(out_dir)`, scans block dump files for blocks where `type == "child_database"`, collects their IDs, fetches each missing database schema with `/databases/{did}`, queries rows through `query_database_all(did)`, and writes `{"schema": schema, "items": items}` to `databases/<id>.json`.
- Fixtures/examples reusable for #81/#146 tests: no literal fixtures are reused. `C:\dev\h2t-business\scripts\notion_dump.py` is useful only as a behavior example/reference for recursive block traversal, database query pagination, and embedded `child_database` row discovery. `C:\dev\h2t-business\scripts\notion_extract.py` is useful only as a behavior example/reference for `_children` recursion, `block_id` parent resolution, `parent_map`/`children_map`, and flattened Notion properties.

## Reuse Decision

Decision constraint: no POS, DOR, vault, lake, SQLite, or filesystem write behavior is approved for copying into `h2t_ops.connectors.notion`. The connector boundary remains provider I/O only: output is source metadata and evidence, including stable Notion IDs, parent shapes, source refs, timestamps, and optionally explicitly requested sync sidecars.

Implementation may reuse the prior-art ideas, but not the old scripts' code shape. New code should follow the current Notion connector architecture, lazy import policy, typed errors, argparse command style, and universal CLI envelope.

## Acceptance Notes

- #81 acceptance requires recursive embedded database discovery that can include `child_database` rows when explicitly requested, without changing the legacy shallow `find-databases <page_id>` list shape.
- #81 acceptance also requires explicit sync sidecars only through user-supplied output paths; plain `sync <page_id> <out.md>` remains unchanged.
- #146 acceptance requires workspace discovery and graph output with raw parent shapes, `parent_map`, `children_map`, `parent_chain` or owner resolution for `block_id` parents, timestamps, Notion URLs where available, and stable `source_ref` fields.
- #146 prior-art acceptance is satisfied by this report: old scripts were audited, concept reuse was approved, verbatim code reuse was rejected, and test-reference behaviors were identified.
