# h2t-ops Notion Functional Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close practical Notion connector gaps #81 and #146: embedded database dumps, explicit sync sidecars, workspace search, and parent graph/source refs.

**Architecture:** Keep the current three-file Notion connector. Add recursive provider-read helpers to `client.py`, expose them through argparse-only `commands.py`, and update the skill docs after live proof. The connector remains provider I/O only: no POS, DOR, vault, lake, or SQLite writes.

**Tech Stack:** Python 3.11, notion-client, httpx, argparse, pytest, h2t_ops typed errors/envelopes.

---

## Inputs

| Source | Path / Issue | Use |
|---|---|---|
| Design | `docs/superpowers/specs/2026-05-22-h2t-ops-notion-functional-completion-design.md` | Source of truth |
| Issue | `#81` | Embedded `child_database` rows in dumps |
| Issue | `#146` | Workspace discovery and parent graph |
| Current client | `h2t_ops/connectors/notion/client.py` | Implementation target |
| Current commands | `h2t_ops/connectors/notion/commands.py` | CLI target |
| Current tests | `tests/connectors/notion/` | Extend in place |
| Skill docs | `plugins/h2t-ops/skills/notion/SKILL.md` | User-facing update |

---

## File Map

| File | Action | Owner task | Responsibility |
|---|---|---|---|
| `h2t_ops/connectors/notion/client.py` | Modify | T1/T3 | Recursive traversal, database discovery, workspace search, graph helpers |
| `h2t_ops/connectors/notion/commands.py` | Modify | T2/T3 | Parser flags, dispatch, explicit sync sidecar writes |
| `tests/connectors/notion/test_client.py` | Modify | T1/T3 | Client unit tests with fakes |
| `tests/connectors/notion/test_commands.py` | Modify | T2/T3 | Parser/dispatch/lazy tests |
| `plugins/h2t-ops/skills/notion/SKILL.md` | Modify | T4 | Document new dump and graph behavior |
| `docs/reports/2026-05-22-notion-prior-art-audit.md` | Create | T3 | Record #146 prior-art decision |

Do not modify `plugins/h2t/skills/notion/**`.

---

## Hard Constraints

1. No POS/DOR/vault/lake/context writes from `h2t_ops/connectors/notion/**`.
2. `sync` may write only explicit user-supplied output paths.
3. New JSON payloads are returned inside the universal CLI envelope's `result`.
4. Plain `find-databases <page_id>` keeps the legacy list shape.
5. Plain `sync <page_id> <out.md>` is unchanged.
6. Lazy import policy stays intact: `commands.py` must not import `notion_client`, `httpx`, or `NotionClient` at module scope.
7. Each commit-bearing task stages only its listed files.

---

## Shared Commands

Run after every commit-bearing task:

```powershell
uv.exe run pytest tests/connectors/notion -q
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Boundary grep:

```powershell
Select-String -Path h2t_ops/connectors/notion/*.py -Pattern "DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/|~/.dor"
```

Expected: no matches.

---

## T0 - Baseline And Prior-Art Discovery

**Files:**
- Read only

- [ ] **Step 1: Confirm branch and dirty tree**

Run:

```powershell
git status --short --branch
```

Expected: unrelated dirty files may exist. Do not stage or modify them.

- [ ] **Step 2: Run current Notion tests**

Run:

```powershell
uv.exe run pytest tests/connectors/notion -q
```

Expected: existing tests pass.

- [ ] **Step 3: Locate prior-art scripts**

Run only bounded repository scans; do not recurse all of `C:/dev` in this task:

```powershell
Get-ChildItem -Path C:/dev/h2t-business,C:/dev/POS,C:/dev/h2t-skills -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match "notion_(dump|extract)|notion.*dump|notion.*extract" } |
  Select-Object -ExpandProperty FullName
```

Expected: record found paths for T3A. The prior-art report must answer:

- whether traversal or pagination ideas are reused;
- whether any old code is reused verbatim;
- whether old scripts dump `child_database` rows;
- whether fixtures/examples are useful for #81/#146 tests.

- [ ] **Step 4: Do not commit T0**

Expected: no files changed by T0.

---

## T1 - Recursive Database Discovery Client

**Files:**
- Modify: `h2t_ops/connectors/notion/client.py`
- Modify: `tests/connectors/notion/test_client.py`

- [ ] **Step 1: Add failing client tests**

Append to `tests/connectors/notion/test_client.py`:

```python
def test_iter_blocks_recursive_paginates_and_respects_depth(conv):
    calls = []
    pages = {
        ("root", None): {
            "results": [
                {"id": "child-page", "type": "child_page", "has_children": True,
                 "child_page": {"title": "Child"}},
            ],
            "has_more": False,
            "next_cursor": None,
        },
        ("child-page", None): {
            "results": [
                {"id": "db1", "type": "child_database", "has_children": False,
                 "child_database": {"title": "DB"}},
            ],
            "has_more": False,
            "next_cursor": None,
        },
    }

    class _Children:
        def list(self, block_id, start_cursor=None, page_size=100):
            calls.append((block_id, start_cursor, page_size))
            return pages[(block_id, start_cursor)]

    conv.client = type("C", (), {"blocks": type("B", (), {"children": _Children()})()})()
    shallow = list(conv.iter_blocks_recursive("root", max_depth=1))
    assert [r["block"]["id"] for r in shallow] == ["child-page"]
    assert [r["depth"] for r in shallow] == [1]
    assert calls == [("root", None, 100)]

    calls.clear()
    rows = list(conv.iter_blocks_recursive("root", max_depth=2))
    assert [r["block"]["id"] for r in rows] == ["child-page", "db1"]
    assert [r["depth"] for r in rows] == [1, 2]
    assert calls == [("root", None, 100), ("child-page", None, 100)]


def test_iter_blocks_recursive_max_depth_zero_fetches_no_children(conv):
    calls = []
    conv._list_block_children_page = lambda block_id, start_cursor=None: calls.append(block_id)

    rows = list(conv.iter_blocks_recursive("root", max_depth=0))

    assert rows == []
    assert calls == []


def test_iter_blocks_recursive_limit_blocks_is_global(conv):
    blocks = [{"id": f"b{i}", "type": "paragraph", "has_children": False} for i in range(3)]
    conv._list_block_children_page = lambda block_id, start_cursor=None: {
        "results": blocks,
        "has_more": False,
        "next_cursor": None,
    }

    rows = list(conv.iter_blocks_recursive("root", max_depth=1, limit_blocks=2))

    assert [r["block"]["id"] for r in rows] == ["b0", "b1"]


def test_iter_blocks_recursive_collects_child_permission_errors(conv):
    pages = {
        "root": {"results": [
            {"id": "bad-child", "type": "child_page", "has_children": True},
            {"id": "sibling", "type": "paragraph", "has_children": False},
        ], "has_more": False, "next_cursor": None},
    }
    def _page(block_id, start_cursor=None):
        if block_id == "bad-child":
            raise ProviderError("restricted")
        return pages[block_id]
    conv._list_block_children_page = _page

    rows = list(conv.iter_blocks_recursive("root", max_depth=2))

    assert [r["block"]["id"] for r in rows] == ["bad-child", "sibling"]
    assert conv._last_traversal_errors == [{"block_id": "bad-child", "error": "restricted"}]


def test_find_databases_recursive_collects_child_database_and_rows(conv):
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {"id": "db1", "type": "child_database",
                      "child_database": {"title": "Tasks"},
                      "parent": {"type": "page_id", "page_id": "root"},
                      "last_edited_time": "2026-05-22T00:00:00Z"},
            "depth": 1,
            "path": ["Root"],
        },
    ])
    conv.query_database = lambda database_id, limit=None: [{"id": "row1"}]

    result = conv.find_databases_on_page("root", recursive=True, with_rows=True, row_limit=5)

    assert result["kind"] == "notion_database_discovery/v1"
    assert result["databases"][0]["database_id"] == "db1"
    assert result["databases"][0]["type"] == "child_database"
    assert result["databases"][0]["rows"] == [{"id": "row1"}]
    assert result["stats"]["databases_queried"] == 1


def test_find_databases_shallow_keeps_legacy_list_shape(conv):
    conv.get_blocks = lambda page_id: [
        {"id": "db1", "type": "child_database", "child_database": {"title": "Tasks"}},
    ]

    result = conv.find_databases_on_page("root")

    assert result == [{"type": "child_database", "database_id": "db1", "title": "Tasks"}]


def test_find_databases_inaccessible_linked_database_kept(conv):
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {"id": "ld1", "type": "linked_database",
                      "linked_database": {"database_id": "db2"},
                      "parent": {"type": "page_id", "page_id": "root"}},
            "depth": 1,
            "path": [],
        },
    ])
    def _fail(db_id):
        raise ProviderError("blocked")
    conv.get_database = _fail

    result = conv.find_databases_on_page("root", recursive=True)

    assert result["databases"][0]["database_id"] == "db2"
    assert result["databases"][0]["accessible"] is False
    assert "blocked" in result["databases"][0]["reason"]


def test_find_databases_row_limit_zero_queries_metadata_but_no_rows(conv):
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {"block": {"id": "db1", "type": "child_database",
                   "child_database": {"title": "Tasks"}},
         "depth": 1, "path": []},
    ])
    conv.query_database = lambda database_id, limit=None: pytest.fail("row_limit=0 must not query rows")

    result = conv.find_databases_on_page("root", recursive=True, with_rows=True, row_limit=0)

    assert result["databases"][0]["rows"] == []
    assert result["databases"][0]["row_count"] == 0
    assert result["stats"]["databases_queried"] == 0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/notion/test_client.py -q
```

Expected: FAIL because `iter_blocks_recursive` and new keyword arguments are missing.

- [ ] **Step 3: Implement traversal and discovery helpers**

Modify `h2t_ops/connectors/notion/client.py`:

1. Add `Iterable` imports and `UsageError` if needed:

```python
from typing import Any, Dict, Iterable, List, Optional
from h2t_ops.core.errors import UsageError
```

2. Add helpers inside `NotionClient` after `get_blocks`:

```python
    def _list_block_children_page(
        self,
        block_id: str,
        *,
        start_cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        try:
            return self.client.blocks.children.list(
                block_id=block_id,
                start_cursor=start_cursor,
                page_size=page_size,
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"list block children {block_id}") from e

    def iter_blocks_recursive(
        self,
        root_page_id: str,
        *,
        max_depth: int = 3,
        limit_blocks: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        if max_depth < 0:
            raise UsageError("max_depth must be non-negative")
        if limit_blocks is not None and limit_blocks < 0:
            raise UsageError("limit_blocks must be non-negative")
        if max_depth == 0:
            return

        seen: set[str] = set()
        emitted = 0
        self._last_traversal_errors: List[Dict[str, str]] = []

        def walk(block_id: str, depth: int, path: List[str]):
            nonlocal emitted
            if limit_blocks is not None and emitted >= limit_blocks:
                return
            cursor = None
            while True:
                try:
                    response = self._list_block_children_page(block_id, start_cursor=cursor)
                except Exception as exc:
                    self._last_traversal_errors.append({"block_id": block_id, "error": str(exc)})
                    return
                for block in response.get("results", []):
                    bid = block.get("id", "")
                    if bid in seen:
                        continue
                    seen.add(bid)
                    emitted += 1
                    emitted_depth = depth + 1
                    row = {"block": block, "depth": emitted_depth, "path": list(path)}
                    yield row
                    if limit_blocks is not None and emitted >= limit_blocks:
                        return
                    if block.get("has_children") and emitted_depth < max_depth:
                        title = (
                            block.get("child_page", {}).get("title")
                            or block.get("child_database", {}).get("title")
                            or block.get("type", "")
                        )
                        yield from walk(bid, emitted_depth, path + ([title] if title else []))
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")

        yield from walk(root_page_id, 0, [])
```

3. Replace `find_databases_on_page` with this signature and behavior:

```python
    def find_databases_on_page(
        self,
        page_id: str,
        *,
        recursive: bool = False,
        max_depth: int = 3,
        limit_blocks: Optional[int] = None,
        with_rows: bool = False,
        row_limit: int = 100,
    ):
        if not recursive and not with_rows:
            databases = []
            blocks = self.get_blocks(page_id)
            for block in blocks:
                block_type = block.get("type")
                block_id = block.get("id")
                if block_type == "child_database":
                    databases.append({
                        "type": "child_database",
                        "database_id": block_id,
                        "title": block.get("child_database", {}).get("title", "Untitled"),
                    })
                elif block_type == "linked_database":
                    db_id = block.get("linked_database", {}).get("database_id")
                    if db_id:
                        try:
                            db_info = self.get_database(db_id)
                            title = db_info.get("title", [{}])[0].get("plain_text", "Untitled")
                        except Exception:
                            title = "Unknown"
                        databases.append({
                            "type": "linked_database",
                            "database_id": db_id,
                            "title": title,
                        })
            return databases

        if row_limit < 0:
            raise UsageError("row_limit must be non-negative")

        seen_databases: set[str] = set()
        databases: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        blocks_seen = 0
        duplicate_refs = 0
        queried = 0
        rows_returned = 0

        for item in self.iter_blocks_recursive(
            page_id,
            max_depth=max_depth,
            limit_blocks=limit_blocks,
        ):
            block = item["block"]
            blocks_seen += 1
            block_type = block.get("type")
            database_id = None
            title = "Untitled"
            kind = None
            accessible = True
            reason = None
            if block_type == "child_database":
                database_id = block.get("id")
                title = block.get("child_database", {}).get("title", "Untitled")
                kind = "child_database"
            elif block_type == "linked_database":
                database_id = block.get("linked_database", {}).get("database_id")
                kind = "linked_database"
                if database_id:
                    try:
                        meta = self.get_database(database_id)
                        title = meta.get("title", [{}])[0].get("plain_text", "Untitled")
                    except Exception as exc:
                        title = "Unknown"
                        accessible = False
                        reason = str(exc)
                        errors.append({"database_id": database_id, "error": str(exc)})
            if not database_id or not kind:
                continue
            if database_id in seen_databases:
                duplicate_refs += 1
                continue
            seen_databases.add(database_id)
            rows: List[Dict[str, Any]] = []
            if with_rows:
                try:
                    if row_limit == 0:
                        rows = []
                    else:
                        rows = self.query_database(database_id, limit=row_limit)
                        queried += 1
                    rows_returned += len(rows)
                except Exception as exc:
                    accessible = False
                    reason = str(exc)
                    errors.append({"database_id": database_id, "error": reason})
            databases.append({
                "kind": kind,
                "type": kind,
                "database_id": database_id,
                "title": title,
                "source_block_id": block.get("id"),
                "parent_page_id": block.get("parent", {}).get("page_id"),
                "path": item.get("path", []),
                "accessible": accessible,
                "reason": reason,
                "source_ref": f"notion:database:{database_id}",
                "notion_url": block.get("url", ""),
                "last_edited_time": block.get("last_edited_time", ""),
                "rows": rows,
                "row_count": len(rows),
            })

        return {
            "kind": "notion_database_discovery/v1",
            "root_page_id": page_id,
            "recursive": recursive,
            "max_depth": max_depth,
            "databases": databases,
            "errors": errors + list(getattr(self, "_last_traversal_errors", [])),
            "stats": {
                "blocks_seen": blocks_seen,
                "blocks_skipped": 0,
                "databases_found": len(databases),
                "databases_queried": queried,
                "duplicate_database_refs": duplicate_refs,
                "rows_returned": rows_returned,
            },
        }
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv.exe run pytest tests/connectors/notion/test_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Run shared checks**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Expected: PASS and `OK lazy-registry`.

- [ ] **Step 6: Commit T1**

Run:

```powershell
git add h2t_ops/connectors/notion/client.py tests/connectors/notion/test_client.py
git commit -m "feat(notion): discover embedded databases recursively (#81)"
```

---

## T2 - CLI Flags And Explicit Sync Sidecars

**Files:**
- Modify: `h2t_ops/connectors/notion/commands.py`
- Modify: `tests/connectors/notion/test_commands.py`

- [ ] **Step 1: Add failing command tests**

Append to `tests/connectors/notion/test_commands.py`:

```python
# Ensure the file imports json for envelope assertions.
import json

def test_find_databases_parser_accepts_recursive_rows_and_limits():
    ns = _parser().parse_args([
        "notion", "find-databases", "PAGE",
        "--recursive", "--max-depth", "4", "--limit-blocks", "200",
        "--with-rows", "--row-limit", "5", "--json",
    ])
    assert ns.recursive is True
    assert ns.max_depth == 4
    assert ns.limit_blocks == 200
    assert ns.with_rows is True
    assert ns.row_limit == 5


def test_find_databases_dispatch_passes_recursive_options(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    calls = []

    class _Stub:
        def find_databases_on_page(self, page_id, **kwargs):
            calls.append((page_id, kwargs))
            return {"kind": "notion_database_discovery/v1"}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="find-databases", page_id="PAGE", recursive=True,
        max_depth=4, limit_blocks=200, with_rows=True, row_limit=5,
        as_json=True, fmt="human",
    ))
    assert out["kind"] == "notion_database_discovery/v1"
    assert calls == [("PAGE", {
        "recursive": True,
        "max_depth": 4,
        "limit_blocks": 200,
        "with_rows": True,
        "row_limit": 5,
    })]


def test_find_databases_json_uses_universal_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from h2t_ops.cli import main as cli_main

    class _Stub:
        def find_databases_on_page(self, page_id, **kwargs):
            return {"kind": "notion_database_discovery/v1", "databases": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    cli_main(["notion", "find-databases", "PAGE", "--recursive", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["provider"] == "notion"
    assert payload["result"]["kind"] == "notion_database_discovery/v1"


def test_sync_include_databases_requires_sidecar_flag_rules(tmp_path, monkeypatch):
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    _patch_client(monkeypatch)
    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            notion_cmd="sync", page_id="P", output_file=str(tmp_path / "p.md"),
            preserve_metadata=False, include_databases=False, recursive=False,
            max_depth=3, row_limit=100, databases_json=str(tmp_path / "db.json"),
            as_json=False, fmt="human",
        ))


def test_sync_include_databases_writes_markdown_and_json_sidecar(tmp_path, monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    import json

    class _Stub:
        def get_blocks(self, page_id):
            return [{"id": "b1", "type": "paragraph"}]
        def blocks_to_markdown(self, blocks):
            return "Body\n"
        def find_databases_on_page(self, page_id, **kwargs):
            return {
                "kind": "notion_database_discovery/v1",
                "databases": [{"title": "Tasks", "database_id": "db1", "row_count": 1}],
                "stats": {"databases_found": 1},
            }

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    md = tmp_path / "page.md"
    sidecar = tmp_path / "db.json"
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="sync", page_id="P", output_file=str(md),
        preserve_metadata=False, include_databases=True, recursive=True,
        max_depth=3, row_limit=5, databases_json=str(sidecar),
        as_json=False, fmt="human",
    ))
    assert "Synced to" in out
    assert "## Embedded databases" in md.read_text(encoding="utf-8")
    assert json.loads(sidecar.read_text(encoding="utf-8"))["kind"] == "notion_database_discovery/v1"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/notion/test_commands.py -q
```

Expected: FAIL because parser flags and dispatch paths do not exist.

- [ ] **Step 3: Extend parser**

Modify `h2t_ops/connectors/notion/commands.py`.

For `find-databases`, replace:

```python
fd = cmds.add_parser("find-databases", help="Find databases on a page")
fd.add_argument("page_id"); add_fmt(fd)
```

with:

```python
fd = cmds.add_parser("find-databases", help="Find databases on a page")
fd.add_argument("page_id")
fd.add_argument("--recursive", action="store_true")
fd.add_argument("--max-depth", type=int, default=3)
fd.add_argument("--limit-blocks", type=int)
fd.add_argument("--with-rows", action="store_true", dest="with_rows")
fd.add_argument("--row-limit", type=int, default=100)
add_fmt(fd)
```

For `sync`, add:

```python
sy.add_argument("--include-databases", action="store_true")
sy.add_argument("--recursive", action="store_true")
sy.add_argument("--max-depth", type=int, default=3)
sy.add_argument("--row-limit", type=int, default=100)
sy.add_argument("--databases-json")
```

- [ ] **Step 4: Extend dispatch**

Replace the `find-databases` branch with:

```python
    if cmd == "find-databases":
        return client.find_databases_on_page(
            args.page_id,
            recursive=getattr(args, "recursive", False),
            max_depth=getattr(args, "max_depth", 3),
            limit_blocks=getattr(args, "limit_blocks", None),
            with_rows=getattr(args, "with_rows", False),
            row_limit=getattr(args, "row_limit", 100),
        )
```

In the `sync` branch, after base markdown generation and metadata block, add:

```python
        if getattr(args, "databases_json", None) and not getattr(args, "include_databases", False):
            raise UsageError("sync: --databases-json requires --include-databases")
        if getattr(args, "include_databases", False):
            discovery = client.find_databases_on_page(
                args.page_id,
                recursive=getattr(args, "recursive", False),
                max_depth=getattr(args, "max_depth", 3),
                with_rows=True,
                row_limit=getattr(args, "row_limit", 100),
            )
            lines = ["\n\n## Embedded databases\n\n"]
            for db in discovery.get("databases", []):
                lines.append(
                    f"- **{db.get('title', 'Untitled')}** "
                    f"({db.get('type', db.get('kind', 'database'))}) "
                    f"`{db.get('database_id', '')}` - rows: {db.get('row_count', 0)}\n"
                )
            md += "".join(lines)
            if getattr(args, "databases_json", None):
                sidecar = Path(args.databases_json)
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                import json as _json
                sidecar.write_text(_json.dumps(discovery, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 5: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/notion/test_commands.py tests/connectors/notion/test_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Run shared checks**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Expected: PASS and `OK lazy-registry`.

- [ ] **Step 7: Commit T2**

Run:

```powershell
git add h2t_ops/connectors/notion/commands.py tests/connectors/notion/test_commands.py
git commit -m "feat(notion): expose embedded database dump commands (#81)"
```

---

## T3 - Workspace Search, Graph, And Prior-Art Report

This task is intentionally split into four commit-sized vertical slices:

- **T3A prior-art report**: docs only, no connector code.
- **T3B workspace search**: `search-workspace` client + command + tests.
- **T3C graph basics**: `graph` client + command + tests.
- **T3D block-owner resolution**: owner chain/source refs for `block_id` parents.

Do not merge T3B/T3C/T3D into one large patch.

Commit boundaries:

```powershell
# T3A
git add docs/reports/2026-05-22-notion-prior-art-audit.md
git commit -m "docs(notion): audit prior workspace scripts (#146)"

# T3B
git add h2t_ops/connectors/notion/client.py h2t_ops/connectors/notion/commands.py tests/connectors/notion/test_client.py tests/connectors/notion/test_commands.py
git commit -m "feat(notion): add workspace search (#146)"

# T3C
git add h2t_ops/connectors/notion/client.py h2t_ops/connectors/notion/commands.py tests/connectors/notion/test_client.py tests/connectors/notion/test_commands.py
git commit -m "feat(notion): add workspace graph refs (#146)"

# T3D
git add h2t_ops/connectors/notion/client.py tests/connectors/notion/test_client.py
git commit -m "feat(notion): resolve block owner chains (#146)"
```

**Files:**
- Modify: `h2t_ops/connectors/notion/client.py`
- Modify: `h2t_ops/connectors/notion/commands.py`
- Modify: `tests/connectors/notion/test_client.py`
- Modify: `tests/connectors/notion/test_commands.py`
- Create: `docs/reports/2026-05-22-notion-prior-art-audit.md`

- [ ] **Step 1: Write prior-art report**

Run:

```powershell
Test-Path C:/dev/h2t-business/scripts/notion_dump.py
Test-Path C:/dev/h2t-business/scripts/notion_extract.py
Get-ChildItem -Path C:/dev/h2t-business,C:/dev/POS,C:/dev/h2t-skills -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match "notion_(dump|extract)|notion.*dump|notion.*extract" } |
  Select-Object -ExpandProperty FullName
```

Then create `docs/reports/2026-05-22-notion-prior-art-audit.md` with the exact
paths printed by the command. If no scripts are found, write the no-findings
variant below.

Use this content when no prior-art scripts are found:

```markdown
# Notion Prior-Art Audit

Date: 2026-05-22
Issues: #81, #146

## Scripts Found

- No prior-art scripts found in checked paths.

## Reuse Decision

- Reuse traversal ideas only if they are provider-read and testable.
- Do not copy POS/DOR/vault/lake writes into `h2t_ops.connectors.notion`.
- Connector output is source metadata/evidence, not POS capture.

## Required Answers

- Traversal/pagination idea reused: false; no prior-art scripts were found.
- Old code reused verbatim: false; no prior-art scripts were found.
- Old scripts dump `child_database` rows: unknown; no prior-art scripts were found.
- Fixtures/examples reusable for #81/#146 tests: false; no prior-art scripts were found.

## Acceptance Notes

- #81 closure requires embedded database rows in `find-databases --recursive --with-rows`
  and explicit `sync --include-databases`.
- #146 closure requires `parent_map`, `children_map`, `parent_chain`, raw parent shapes,
  timestamps, and stable `source_ref` fields.
```

If scripts are found, replace only the `Scripts Found` bullet list with exact
paths and add these required sections before `Reuse Decision`:

```markdown
## Required Answers

- Traversal/pagination idea reused: state true or false, with reason.
- Old code reused verbatim: no, or exact copied line ranges if approved.
- Old scripts dump `child_database` rows: state true, false, or unknown, with evidence.
- Fixtures/examples reusable for #81/#146 tests: state true or false, with paths.
```

Keep the rest of the report unchanged.

- [ ] **Step 2: Add failing client tests for search and graph**

Append to `tests/connectors/notion/test_client.py`:

```python
def test_search_workspace_preserves_parent_shapes(conv):
    class _Search:
        def __call__(self, **kwargs):
            return {
                "results": [
                    {"id": "p1", "object": "page", "parent": {"type": "workspace"},
                     "url": "https://notion.so/p1", "created_time": "c", "last_edited_time": "m"},
                ],
                "has_more": False,
            }
    conv.client = type("C", (), {"search": _Search()})()
    result = conv.search_workspace(object_type="page", limit=5)
    assert result["kind"] == "notion_workspace_search/v1"
    assert result["results"][0]["parent"] == {"type": "workspace"}


def test_search_workspace_rejects_negative_limit(conv):
    with pytest.raises(UsageError):
        conv.search_workspace(object_type="page", limit=-1)


def test_graph_page_returns_nodes_edges_and_maps(conv):
    conv.get_page = lambda page_id: {
        "id": page_id, "object": "page", "parent": {"type": "workspace"},
        "url": "https://notion.so/root", "created_time": "c", "last_edited_time": "m",
        "properties": {"title": {"title": [{"plain_text": "Root"}]}},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {"block": {"id": "b1", "type": "paragraph", "parent": {"type": "page_id", "page_id": "root"},
                   "created_time": "c", "last_edited_time": "m"}, "depth": 1, "path": ["Root"]},
        {"block": {"id": "db1", "type": "child_database", "parent": {"type": "page_id", "page_id": "root"},
                   "child_database": {"title": "Tasks"},
                   "created_time": "c", "last_edited_time": "m"}, "depth": 1, "path": ["Root"]},
    ])
    result = conv.graph_page("root", max_depth=2)
    assert result["kind"] == "notion_workspace_graph/v1"
    assert result["parent_map"]["b1"] == "root"
    assert "db1" in result["children_map"]["root"]
    assert result["nodes"][0]["source_ref"].startswith("notion:")


def test_graph_page_includes_traversal_permission_errors(conv):
    conv.get_page = lambda page_id: {
        "id": page_id, "object": "page", "parent": {"type": "workspace"}, "properties": {},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([])
    conv._last_traversal_errors = [{"block_id": "restricted", "error": "blocked"}]

    result = conv.graph_page("root")

    assert result["errors"] == [{"block_id": "restricted", "error": "blocked"}]


def test_graph_block_parent_owner_chain_uses_retrieve_block(conv):
    conv.get_page = lambda page_id: {
        "id": page_id, "object": "page", "parent": {"type": "workspace"},
        "properties": {},
    }
    conv.get_block = lambda block_id: {
        "id": block_id,
        "type": "column_list",
        "parent": {"type": "page_id", "page_id": "root"},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {"block": {"id": "nested", "type": "paragraph",
                   "parent": {"type": "block_id", "block_id": "owner"}},
         "depth": 1, "path": []},
    ])

    result = conv.graph_page("root", max_depth=2)

    assert result["parent_map"]["nested"] == "owner"
    assert result["owner_map"]["nested"]["owner_block_id"] == "owner"
    assert result["owner_map"]["nested"]["owner_page_id"] == "root"
```

- [ ] **Step 3: Add failing command tests**

Append to `tests/connectors/notion/test_commands.py`:

```python
def test_search_workspace_and_graph_parsers_registered():
    parser = _parser()
    ns = parser.parse_args(["notion", "search-workspace", "--object", "page", "--limit", "5", "--json"])
    assert ns.notion_cmd == "search-workspace"
    assert ns.object == "page"
    ns2 = parser.parse_args(["notion", "graph", "ROOT", "--max-depth", "2", "--include-databases", "--json"])
    assert ns2.notion_cmd == "graph"
    assert ns2.root_page_id == "ROOT"
    assert ns2.include_databases is True
    ns3 = parser.parse_args(["notion", "graph", "ROOT", "--no-include-databases", "--json"])
    assert ns3.include_databases is False
    ns4 = parser.parse_args(["notion", "graph", "ROOT", "--json"])
    assert ns4.include_databases is True


def test_graph_dispatch_passes_options(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    calls = []

    class _Stub:
        def graph_page(self, root_page_id, **kwargs):
            calls.append((root_page_id, kwargs))
            return {"kind": "notion_workspace_graph/v1"}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="graph", root_page_id="ROOT", max_depth=2,
        include_databases=True, root_label="KB", as_json=True, fmt="human",
    ))
    assert out["kind"] == "notion_workspace_graph/v1"
    assert calls == [("ROOT", {"max_depth": 2, "include_databases": True, "root_label": "KB"})]


def test_search_workspace_and_graph_json_use_universal_envelope(monkeypatch, capsys):
    import json
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.cli import main as cli_main

    class _Stub:
        def search_workspace(self, **kwargs):
            return {"kind": "notion_workspace_search/v1", "results": []}
        def graph_page(self, root_page_id, **kwargs):
            return {"kind": "notion_workspace_graph/v1", "nodes": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    cli_main(["notion", "search-workspace", "--object", "page", "--json"])
    search_payload = json.loads(capsys.readouterr().out)
    assert search_payload["ok"] is True
    assert search_payload["result"]["kind"] == "notion_workspace_search/v1"

    cli_main(["notion", "graph", "ROOT", "--json"])
    graph_payload = json.loads(capsys.readouterr().out)
    assert graph_payload["ok"] is True
    assert graph_payload["result"]["kind"] == "notion_workspace_graph/v1"
```

Execution split for the test block above:

- T3B adds only `test_search_workspace_preserves_parent_shapes`,
  `test_search_workspace_rejects_negative_limit`, and the
  `search-workspace` half of `test_search_workspace_and_graph_json_use_universal_envelope`.
- T3C adds `test_graph_page_returns_nodes_edges_and_maps`,
  `test_graph_page_includes_traversal_permission_errors`,
  `test_search_workspace_and_graph_parsers_registered`,
  `test_graph_dispatch_passes_options`, and the graph envelope assertion.
- T3D adds only `test_graph_block_parent_owner_chain_uses_retrieve_block`.

Do not append all T3 tests in one edit.

- [ ] **Step 4: Implement client helpers**

Add to `NotionClient`:

```python
    def search_workspace(self, object_type: str = "all", *, limit: Optional[int] = None) -> Dict[str, Any]:
        if limit is not None and limit < 0:
            raise UsageError("limit must be non-negative")
        query_filter = None
        if object_type in ("page", "database"):
            query_filter = {"property": "object", "value": object_type}
        results: List[Dict[str, Any]] = []
        start_cursor = None
        while True:
            kwargs: Dict[str, Any] = {}
            if query_filter:
                kwargs["filter"] = query_filter
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            if limit:
                kwargs["page_size"] = min(limit - len(results), 100)
            try:
                response = self.client.search(**kwargs)
            except Exception as e:
                raise _map_sdk_exc(e, op="search workspace") from e
            results.extend(response.get("results", []))
            if limit and len(results) >= limit:
                results = results[:limit]
                break
            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")
        return {"kind": "notion_workspace_search/v1", "object": object_type, "results": results}

    def _title_from_object(self, obj: Dict[str, Any]) -> str:
        props = obj.get("properties", {})
        for pdata in props.values():
            if pdata.get("type") == "title":
                return self._rich_text_to_markdown(pdata.get("title", [])) or "Untitled"
        if obj.get("type") == "child_database":
            return obj.get("child_database", {}).get("title", "Untitled")
        return obj.get("type", "Untitled")

    def get_block(self, block_id: str) -> Dict[str, Any]:
        try:
            return self.client.blocks.retrieve(block_id=block_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"retrieve block {block_id}") from e

    def _resolve_block_owner(self, block_id: str) -> Dict[str, Any]:
        chain: List[str] = []
        current = block_id
        while current:
            owner = self.get_block(current)
            chain.append(current)
            parent = owner.get("parent", {})
            if parent.get("type") == "page_id":
                return {"owner_block_id": block_id, "owner_page_id": parent.get("page_id"), "chain": chain}
            current = parent.get("block_id")
        return {"owner_block_id": block_id, "owner_page_id": None, "chain": chain}

    def graph_page(
        self,
        root_page_id: str,
        *,
        max_depth: int = 3,
        include_databases: bool = True,
        root_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        parent_map: Dict[str, str] = {}
        children_map: Dict[str, List[str]] = {}
        owner_map: Dict[str, Dict[str, Any]] = {}
        errors: List[Dict[str, Any]] = []

        try:
            root = self.get_page(root_page_id)
            nodes.append({
                "id": root_page_id,
                "object": root.get("object", "page"),
                "title": self._title_from_object(root),
                "parent": root.get("parent", {}),
                "parent_chain": [],
                "source_ref": f"notion:page:{root_page_id}",
                "notion_url": root.get("url", ""),
                "created_time": root.get("created_time", ""),
                "last_edited_time": root.get("last_edited_time", ""),
            })
        except Exception as exc:
            errors.append({"id": root_page_id, "error": str(exc)})

        for item in self.iter_blocks_recursive(root_page_id, max_depth=max_depth):
            block = item["block"]
            bid = block.get("id", "")
            parent = block.get("parent", {})
            parent_id = parent.get("page_id") or parent.get("block_id") or root_page_id
            if parent.get("type") == "block_id" and parent.get("block_id"):
                try:
                    owner_map[bid] = self._resolve_block_owner(parent["block_id"])
                except Exception as exc:
                    owner_map[bid] = {"owner_block_id": parent["block_id"], "owner_page_id": None, "error": str(exc)}
                    errors.append({"id": bid, "error": str(exc)})
            if block.get("type") == "child_database" and not include_databases:
                continue
            nodes.append({
                "id": bid,
                "object": "database" if block.get("type") == "child_database" else "block",
                "title": self._title_from_object(block),
                "parent": parent,
                "parent_chain": [root_page_id] + item.get("path", []),
                "source_ref": f"notion:{'database' if block.get('type') == 'child_database' else 'block'}:{bid}",
                "notion_url": block.get("url", ""),
                "created_time": block.get("created_time", ""),
                "last_edited_time": block.get("last_edited_time", ""),
            })
            parent_map[bid] = parent_id
            children_map.setdefault(parent_id, []).append(bid)
            edges.append({"from": parent_id, "to": bid, "relation": "contains"})

        return {
            "kind": "notion_workspace_graph/v1",
            "root_page_id": root_page_id,
            "root_label": root_label,
            "nodes": nodes,
            "edges": edges,
            "parent_map": parent_map,
            "children_map": children_map,
            "owner_map": owner_map,
            "errors": errors + list(getattr(self, "_last_traversal_errors", [])),
            "stats": {"nodes": len(nodes), "edges": len(edges)},
        }
```

Execution split for the client block above:

- T3B adds `search_workspace` only.
- T3C adds `_title_from_object` and `graph_page` without block-owner lookup.
- T3D adds `get_block`, `_resolve_block_owner`, `owner_map`, and traversal
  error propagation in `graph_page`.

Do not implement all helpers in one patch.

- [ ] **Step 5: Implement parser and dispatch**

In `commands.py`, add parsers:

```python
sw = cmds.add_parser("search-workspace", help="Search shared Notion workspace objects")
sw.add_argument("--object", choices=["page", "database", "all"], default="all")
sw.add_argument("--limit", type=int)
add_fmt(sw)

gr = cmds.add_parser("graph", help="Build a page subtree graph")
gr.add_argument("root_page_id")
gr.add_argument("--max-depth", type=int, default=3)
db_group = gr.add_mutually_exclusive_group()
db_group.add_argument("--include-databases", dest="include_databases", action="store_true", default=True)
db_group.add_argument("--no-include-databases", dest="include_databases", action="store_false")
gr.add_argument("--root-label")
add_fmt(gr)
```

Add dispatch branches:

```python
    if cmd == "search-workspace":
        return client.search_workspace(object_type=args.object, limit=args.limit)
    if cmd == "graph":
        return client.graph_page(
            args.root_page_id,
            max_depth=args.max_depth,
            include_databases=args.include_databases,
            root_label=args.root_label,
        )
```

Execution split for parser/dispatch:

- T3B adds `search-workspace` parser and dispatch only.
- T3C adds `graph` parser and dispatch.
- T3D does not change parser/dispatch.

- [ ] **Step 6: Run tests and guards**

Run:

```powershell
uv.exe run pytest tests/connectors/notion -q
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
Select-String -Path h2t_ops/connectors/notion/*.py -Pattern "DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/|~/.dor"
```

Expected: tests pass, lazy-registry OK, grep has no matches.

- [ ] **Step 7: Commit the current T3 slice**

Use the T3A/T3B/T3C/T3D commit boundary commands at the top of this section.
Do not stage all T3 files into one large commit unless the user explicitly asks
for a squash.

Expected: each slice is independently reviewable.

---

## T4 - Skill Docs And Closure Verification

**Files:**
- Modify: `plugins/h2t-ops/skills/notion/SKILL.md`

- [ ] **Step 1: Update skill command table**

Edit `plugins/h2t-ops/skills/notion/SKILL.md` so the command table includes:

```markdown
| `h2t-ops notion find-databases <page-id> [--recursive] [--with-rows] [--row-limit N]` | discover embedded/linked databases |
| `h2t-ops notion sync <page-id> <out.md> [--include-databases] [--databases-json out.json]` | explicit page export; embedded DBs only when requested |
| `h2t-ops notion search-workspace [--object page|database|all] [--limit N]` | search shared workspace objects |
| `h2t-ops notion graph <root-page-id> [--max-depth N] [--include-databases]` | emit source-ref graph for a page subtree |
```

Add this boundary note:

```markdown
Plain `sync` is not a complete workspace dump. If embedded databases matter, use
`find-databases --recursive --with-rows --json` or `sync --include-databases`
with an explicit `--databases-json` sidecar.

Connector output is provider evidence/source metadata. POS/KB registration and
promotion happen outside this skill.
```

- [ ] **Step 2: Run docs grep**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/notion/SKILL.md -Pattern "find-databases .*--recursive|--include-databases|search-workspace|graph <root-page-id>|Plain `sync` is not"
```

Expected: matches for all terms.

- [ ] **Step 3: Run full tests**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Expected: PASS and `OK lazy-registry`.

- [ ] **Step 4: Live smoke**

Only run if real Notion credentials and a shared root page are available:

```powershell
uv.exe run h2t-ops notion find-databases <real_page_id> --recursive --json
uv.exe run h2t-ops notion find-databases <real_page_id> --recursive --with-rows --row-limit 5 --json
uv.exe run h2t-ops notion sync <real_page_id> C:/tmp/notion-smoke.md --include-databases --databases-json C:/tmp/notion-smoke-databases.json
uv.exe run h2t-ops notion search-workspace --object page --limit 5 --json
uv.exe run h2t-ops notion graph <real_root_page_id> --max-depth 2 --json
```

Expected: JSON commands exit 0 and return valid JSON. The sync smoke creates
Markdown containing `## Embedded databases` and a sidecar with
`kind == notion_database_discovery/v1`. If no suitable page exists, record
`SKIPPED: no shared test page`.

- [ ] **Step 5: Commit T4**

Run:

```powershell
git add plugins/h2t-ops/skills/notion/SKILL.md
git commit -m "docs(notion): document embedded database and graph commands (#81 #146)"
```

---

## T5 - Final Evidence

**Files:**
- No commits

- [ ] **Step 1: Full verification**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops --help
uv.exe run h2t-ops notion --help
uv.exe run h2t-ops dev check lazy-registry
```

Expected: tests pass, help exits 0, lazy-registry OK.

- [ ] **Step 2: Boundary audit**

Run:

```powershell
Select-String -Path h2t_ops/connectors/notion/*.py -Pattern "DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/|~/.dor"
git diff --name-only HEAD
```

Expected: no boundary matches; only expected uncommitted files if a reviewed fix is pending.

- [ ] **Step 3: Prepare closure evidence**

Prepare but do not post:

```markdown
## Notion functional completion evidence

- #81 embedded database discovery: PASS
- #81 explicit sync sidecar: PASS
- #146 prior-art audit: PASS
- #146 workspace search/graph: PASS
- tests/core tests/connectors: PASS
- lazy-registry: PASS
- boundary grep: CLEAN
- live smoke: PASS/SKIPPED with reason
```

- [ ] **Step 4: Stop for approval**

Do not push, post comments, or close #81/#146 without explicit user approval.

---

## Self-Review Checklist

- #81 discovery rows: T1/T2.
- #81 explicit sync sidecar: T2/T4.
- #146 prior-art: T3.
- #146 graph maps/source refs: T3.
- Universal envelope respected: commands return result payloads only.
- POS/DOR boundary: hard constraints and T5 audit.
- Backward compatibility: shallow `find-databases` and plain `sync` unchanged.
- No placeholders: all tasks include concrete tests/commands/implementation snippets.
