"""NotionClient — bidirectional Notion adapter (re-wrapped, typed errors).

API logic is identical to lib/clients/notion.py; only side effects and error
types changed per spec §10 (re-wrap not rewrite).
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    H2TError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import resolve_notion_token

# The Views API landed in this version; the rest of this client speaks 2022-06-28,
# where the data-source model differs. Sent per-request, never globally (#372).
VIEWS_API_VERSION = "2025-09-03"


def _map_http_status(status: int, msg: str):
    if status in (401, 403):
        return AuthError(f"Notion auth/permission denied (HTTP {status}): {msg}")
    if status == 404:
        return NotFoundError(f"Notion resource not found (HTTP {status}): {msg}")
    if status >= 500:
        return ProviderError(f"Notion server error (HTTP {status}): {msg}")
    return ProviderError(f"Notion API error (HTTP {status}): {msg}")


def _map_sdk_exc(e: Exception, *, op: str):
    if isinstance(e, H2TError):
        return e  # already typed (e.g. from _http_post / get_blocks) — don't re-classify
    code = getattr(e, "code", None)
    if hasattr(code, "value"):           # notion_client APIErrorCode enum → str
        code = code.value
    status = getattr(e, "status", 0)
    if code in ("unauthorized", "restricted_resource") or status in (401, 403):
        return AuthError(f"Failed to {op}: {e}")
    if code == "object_not_found" or status == 404:
        return NotFoundError(f"Failed to {op}: {e}")
    s = str(e).lower()
    if "unauthorized" in s or "restricted" in s or "permission" in s:
        return AuthError(f"Failed to {op}: {e}")
    if "could not find" in s:
        return NotFoundError(f"Failed to {op}: {e}")
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(f"Failed to {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")


class NotionClient:
    """Notion API client — read and write pages and databases."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or resolve_notion_token()  # raises ConfigError if missing
        try:
            from notion_client import Client  # optional dep — lazy (spec §4.1)
        except ImportError as e:
            raise ConfigError(
                "notion-client library not installed.",
                hint="pip install notion-client httpx  (or run /h2t-core:setup)",
            ) from e
        self.client = Client(auth=self.token)

    def _http_post(self, url: str, headers: dict, json_body: dict):
        return self._http_request("POST", url, headers, json_body)

    def _http_request(self, method: str, url: str, headers: dict,
                      json_body: dict | None = None):
        """One HTTP call. Views needs GET/PATCH/DELETE, which the SDK does not carry."""
        try:
            import httpx  # optional dep — lazy (spec §4.1)
        except ImportError as e:
            raise ConfigError(
                "httpx library not installed.",
                hint="pip install httpx  (or run /h2t-core:setup)",
            ) from e
        try:
            resp = httpx.request(method, url, headers=headers, json=json_body)
            resp.raise_for_status()
            # DELETE answers 200 with an empty body; that is success, not a parse error.
            return resp.json() if resp.content else {}
        except httpx.HTTPStatusError as e:
            raise _map_http_status(e.response.status_code, str(e)) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Notion request failed: {e}") from e

    # --- Views (API 2025-09-03) ---

    def _views_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": VIEWS_API_VERSION,
            "Content-Type": "application/json",
        }

    def list_views(
        self,
        *,
        database_id: str | None = None,
        data_source_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Views of one database or data source, plus Notion's own has_more.

        Rows come back as stubs — ``{"object": "view", "id": ...}`` and nothing
        else. Name, type, sorts and configuration live behind get_view.
        """
        if bool(database_id) == bool(data_source_id):
            raise UsageError(
                "notion views: pass exactly one of --database-id / --data-source-id"
            )
        key, value = (("database_id", database_id) if database_id
                      else ("data_source_id", data_source_id))
        results: list[dict[str, Any]] = []
        has_more = False
        cursor = None
        while True:
            url = f"https://api.notion.com/v1/views?{key}={value}"
            if cursor:
                url += f"&start_cursor={cursor}"
            data = self._http_request("GET", url, self._views_headers())
            results.extend(data.get("results", []))
            has_more = bool(data.get("has_more"))
            if not has_more or (limit and len(results) >= limit):
                break
            cursor = data.get("next_cursor")
        items = results[:limit] if limit else results
        return {"items": items, "truncated": has_more or len(items) < len(results)}

    def get_view(self, view_id: str) -> dict[str, Any]:
        return self._http_request(
            "GET", f"https://api.notion.com/v1/views/{view_id}", self._views_headers()
        )

    def patch_view(self, view_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Send *spec* verbatim: the payload shape is Notion's, not ours.

        ``sorts[].property`` and ``configuration.properties[].property_id`` accept a
        property *name*, which Notion resolves — that is what makes one spec portable
        across copies of a database whose property ids all differ.
        """
        return self._http_request(
            "PATCH", f"https://api.notion.com/v1/views/{view_id}",
            self._views_headers(), spec,
        )

    def create_view(
        self,
        spec: dict[str, Any],
        *,
        database_id: str | None = None,
        data_source_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a view from *spec*; the parent is filled in only if spec omits it."""
        body = dict(spec)
        if "parent" not in body:
            if bool(database_id) == bool(data_source_id):
                raise UsageError(
                    "notion views create: spec has no parent — pass exactly one of "
                    "--database-id / --data-source-id"
                )
            body["parent"] = ({"type": "database_id", "database_id": database_id}
                              if database_id else
                              {"type": "data_source_id", "data_source_id": data_source_id})
        return self._http_request(
            "POST", "https://api.notion.com/v1/views", self._views_headers(), body
        )

    def delete_view(self, view_id: str, *, confirm_name: str) -> dict[str, Any]:
        """Delete a view after checking its name — mirrors archive_page's gate."""
        actual = (self.get_view(view_id) or {}).get("name", "")
        if actual != confirm_name:
            raise UsageError(
                f'delete aborted: view name mismatch — expected "{confirm_name}", '
                f'got "{actual}"'
            )
        return self._http_request(
            "DELETE", f"https://api.notion.com/v1/views/{view_id}", self._views_headers()
        )

    # --- Read ---

    def get_page(self, page_id: str) -> dict[str, Any]:
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get page {page_id}") from e

    def get_block(self, block_id: str) -> dict[str, Any]:
        try:
            return self.client.blocks.retrieve(block_id=block_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get block {block_id}") from e

    def get_blocks(self, page_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        start_cursor = None
        try:
            while True:
                response = self.client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=start_cursor,
                    page_size=min(limit or 100, 100),
                )
                blocks.extend(response["results"])
                if not response["has_more"] or (limit and len(blocks) >= limit):
                    break
                start_cursor = response["next_cursor"]
            return blocks[:limit] if limit else blocks
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get blocks from {page_id}") from e

    def _list_block_children_page(
        self,
        block_id: str,
        *,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
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
        limit_blocks: int | None = None,
    ) -> Iterable[dict[str, Any]]:
        if max_depth < 0:
            raise UsageError("max_depth must be non-negative")
        if limit_blocks is not None and limit_blocks < 0:
            raise UsageError("limit_blocks must be non-negative")

        self._last_traversal_errors: list[dict[str, str]] = []
        if max_depth == 0:
            return

        seen: set[str] = set()
        emitted = 0

        def walk(block_id: str, depth: int, path: list[str]):
            nonlocal emitted
            if limit_blocks is not None and emitted >= limit_blocks:
                return
            cursor = None
            while True:
                try:
                    response = self._list_block_children_page(block_id, start_cursor=cursor)
                except Exception as exc:
                    if depth == 0:
                        raise
                    self._last_traversal_errors.append({"block_id": block_id, "error": str(exc)})
                    return
                for block in response.get("results", []):
                    if limit_blocks is not None and emitted >= limit_blocks:
                        return
                    child_id = block.get("id", "")
                    if child_id in seen:
                        continue
                    seen.add(child_id)
                    emitted += 1
                    emitted_depth = depth + 1
                    yield {"block": block, "depth": emitted_depth, "path": list(path)}
                    if limit_blocks is not None and emitted >= limit_blocks:
                        return
                    if block.get("has_children") and emitted_depth < max_depth:
                        title = (
                            block.get("child_page", {}).get("title")
                            or block.get("child_database", {}).get("title")
                            or block.get("type", "")
                        )
                        child_path = path + ([title] if title else [])
                        yield from walk(child_id, emitted_depth, child_path)
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")

        yield from walk(root_page_id, 0, [])

    def query_database(
        self,
        database_id: str,
        filter_dict: dict | None = None,
        sorts: list | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.query_database_page(
            database_id, filter_dict=filter_dict, sorts=sorts, limit=limit
        )["items"]

    def query_database_page(
        self,
        database_id: str,
        filter_dict: dict | None = None,
        sorts: list | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Same as query_database, plus Notion's own has_more flag.

        A page that exactly fills ``limit`` is otherwise indistinguishable from
        a complete result (#351).
        """
        try:
            results: list[dict[str, Any]] = []
            has_more = False
            start_cursor = None
            while True:
                body: dict[str, Any] = {}
                if filter_dict:
                    body["filter"] = filter_dict
                if sorts:
                    body["sorts"] = sorts
                if start_cursor:
                    body["start_cursor"] = start_cursor

                url = f"https://api.notion.com/v1/databases/{database_id}/query"
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                }
                data = self._http_post(url, headers, body)
                results.extend(data["results"])
                has_more = data["has_more"]
                if not has_more or (limit and len(results) >= limit):
                    break
                start_cursor = data.get("next_cursor")
            items = results[:limit] if limit else results
            return {
                "items": items,
                # Trimming to `limit` also truncates, even if Notion had no more.
                "truncated": has_more or len(items) < len(results),
            }
        except Exception as e:
            raise _map_sdk_exc(e, op=f"query database {database_id}") from e

    def get_database(self, database_id: str) -> dict[str, Any]:
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get database {database_id}") from e

    def search_workspace(
        self,
        object_type: str = "all",
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        if limit is not None and limit < 0:
            raise UsageError("limit must be non-negative")
        if limit == 0:
            return {"kind": "notion_workspace_search/v1", "object": object_type, "results": []}
        query_filter = None
        if object_type in ("page", "database", "data_source"):
            # Notion search API now filters databases as "data_source".
            # Keep "database" as the CLI/user-facing compatibility alias.
            filter_value = "data_source" if object_type == "database" else object_type
            query_filter = {"property": "object", "value": filter_value}
        elif object_type != "all":
            raise UsageError("object_type must be one of: page, database, data_source, all")
        results = []
        start_cursor = None
        while True:
            kwargs = {}
            if query_filter:
                kwargs["filter"] = query_filter
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            if limit is not None:
                kwargs["page_size"] = min(limit - len(results), 100)
            try:
                response = self.client.search(**kwargs)
            except Exception as e:
                raise _map_sdk_exc(e, op="search workspace") from e
            results.extend(response.get("results", []))
            if limit is not None and len(results) >= limit:
                results = results[:limit]
                break
            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")
        return {"kind": "notion_workspace_search/v1", "object": object_type, "results": results}

    def _title_from_object(self, obj: dict[str, Any]) -> str:
        properties = obj.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "title":
                return self._rich_text_to_markdown(prop.get("title", [])) or "Untitled"
            if "title" in prop and isinstance(prop.get("title"), list):
                return self._rich_text_to_markdown(prop.get("title", [])) or "Untitled"

        obj_type = obj.get("type")
        if obj_type == "child_database":
            return obj.get("child_database", {}).get("title") or "Untitled"
        if obj_type == "child_page":
            return obj.get("child_page", {}).get("title") or "Untitled"
        if obj_type and obj_type in obj:
            typed = obj.get(obj_type, {})
            if isinstance(typed, dict):
                rich_text = typed.get("rich_text")
                if isinstance(rich_text, list):
                    return self._rich_text_to_markdown(rich_text) or obj_type
        return obj.get("object") or obj_type or "Untitled"

    def _resolve_block_owner(self, block_id: str) -> dict[str, Any]:
        seen: set[str] = set()
        chain: list[str] = []
        current_id = block_id

        for _ in range(100):
            if current_id in seen:
                raise ProviderError(f"Cycle resolving Notion block owner at {current_id}")
            seen.add(current_id)
            chain.append(current_id)

            block = self.get_block(current_id)
            parent = block.get("parent", {})
            parent_type = parent.get("type")
            if parent_type == "page_id":
                return {
                    "owner_block_id": block_id,
                    "owner_page_id": parent.get("page_id"),
                    "chain": chain,
                    "source_refs": [f"notion:block:{item}" for item in chain],
                    "owner_page_source_ref": (
                        f"notion:page:{parent.get('page_id')}" if parent.get("page_id") else None
                    ),
                }
            if parent_type == "block_id" and parent.get("block_id"):
                current_id = parent["block_id"]
                continue
            return {
                "owner_block_id": block_id,
                "owner_page_id": None,
                "chain": chain,
                "source_refs": [f"notion:block:{item}" for item in chain],
                "owner_page_source_ref": None,
            }

        raise ProviderError(f"Exceeded Notion block owner chain limit at {current_id}")

    def graph_page(
        self,
        root_page_id: str,
        *,
        max_depth: int = 3,
        include_databases: bool = True,
        root_label: str | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        parent_map: dict[str, str] = {}
        owner_map: dict[str, dict[str, Any]] = {}
        owner_cache: dict[str, dict[str, Any]] = {}
        owner_error_keys: set[tuple[str, str, str, str]] = set()
        children_map: dict[str, list[str]] = {}
        errors: list[dict[str, Any]] = []

        root = self.get_page(root_page_id)
        root_id = root.get("id", root_page_id)
        children_map[root_id] = []
        nodes.append({
            "id": root_id,
            "object": root.get("object", "page"),
            "type": root.get("object", "page"),
            "title": root_label or self._title_from_object(root),
            "parent": root.get("parent", {}),
            "parent_chain": [],
            "source_ref": f"notion:page:{root_id}",
            "notion_url": root.get("url", ""),
            "created_time": root.get("created_time", ""),
            "last_edited_time": root.get("last_edited_time", ""),
        })

        for item in self.iter_blocks_recursive(root_page_id, max_depth=max_depth):
            block = item["block"]
            block_id = block.get("id", "")
            if not block_id:
                continue
            block_type = block.get("type", "")
            if block_type == "child_database" and not include_databases:
                continue

            parent = block.get("parent", {})
            parent_id = parent.get("page_id") or parent.get("block_id") or root_id
            object_type = "database" if block_type == "child_database" else "block"
            if parent.get("type") == "block_id" and parent.get("block_id"):
                owner_block_id = parent["block_id"]
                if owner_block_id not in owner_cache:
                    try:
                        owner_cache[owner_block_id] = {
                            "ok": True,
                            "owner": self._resolve_block_owner(owner_block_id),
                        }
                    except Exception as exc:
                        error_type = type(exc).__name__
                        owner_cache[owner_block_id] = {
                            "ok": False,
                            "owner": {
                                "owner_block_id": owner_block_id,
                                "owner_page_id": None,
                                "chain": [owner_block_id],
                                "source_refs": [f"notion:block:{owner_block_id}"],
                                "owner_page_source_ref": None,
                                "error": str(exc),
                                "error_type": error_type,
                            },
                            "error": str(exc),
                            "error_type": error_type,
                        }

                cached_owner = owner_cache[owner_block_id]
                owner_map[block_id] = dict(cached_owner["owner"])
                if not cached_owner["ok"]:
                    error_entry = {
                        "block_id": block_id,
                        "owner_block_id": owner_block_id,
                        "error": cached_owner["error"],
                        "error_type": cached_owner["error_type"],
                    }
                    error_key = (
                        block_id,
                        owner_block_id,
                        cached_owner["error"],
                        cached_owner["error_type"],
                    )
                    if error_key not in owner_error_keys:
                        owner_error_keys.add(error_key)
                        errors.append(error_entry)

            nodes.append({
                "id": block_id,
                "object": object_type,
                "type": block_type,
                "title": self._title_from_object(block),
                "parent": parent,
                "parent_chain": [root_id] + item.get("path", []),
                "source_ref": f"notion:{object_type}:{block_id}",
                "notion_url": block.get("url", ""),
                "created_time": block.get("created_time", ""),
                "last_edited_time": block.get("last_edited_time", ""),
            })
            parent_map[block_id] = parent_id
            children_map.setdefault(parent_id, []).append(block_id)
            children_map.setdefault(block_id, [])
            edges.append({"from": parent_id, "to": block_id, "relation": "contains"})

        return {
            "kind": "notion_workspace_graph/v1",
            "root_page_id": root_id,
            "requested_root_page_id": root_page_id,
            "root_label": root_label,
            "nodes": nodes,
            "edges": edges,
            "parent_map": parent_map,
            "owner_map": owner_map,
            "children_map": children_map,
            "errors": errors + list(getattr(self, "_last_traversal_errors", [])),
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "blocks_seen": len(parent_map),
            },
        }

    def find_databases_on_page(
        self,
        page_id: str,
        *,
        recursive: bool = False,
        max_depth: int = 3,
        limit_blocks: int | None = None,
        with_rows: bool = False,
        row_limit: int = 100,
    ):
        if row_limit < 0:
            raise UsageError("row_limit must be non-negative")

        if not recursive and not with_rows:
            try:
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
            except Exception as e:
                raise _map_sdk_exc(e, op=f"find databases on page {page_id}") from e

        seen_databases: set[str] = set()
        databases: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        blocks_seen = 0
        duplicate_refs = 0
        queried = 0
        rows_returned = 0
        traversal_max_depth = max_depth if recursive else 1

        for item in self.iter_blocks_recursive(
            page_id,
            max_depth=traversal_max_depth,
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
                        metadata = self.get_database(database_id)
                        title = metadata.get("title", [{}])[0].get("plain_text", "Untitled")
                    except Exception as exc:
                        title = "Unknown"
                        accessible = False
                        reason = str(exc)
                        errors.append({"database_id": database_id, "error": reason})

            if not database_id or not kind:
                continue
            if database_id in seen_databases:
                duplicate_refs += 1
                continue
            seen_databases.add(database_id)

            rows: list[dict[str, Any]] = []
            if with_rows:
                if row_limit == 0:
                    rows = []
                else:
                    try:
                        rows = self.query_database(database_id, limit=row_limit)
                        queried += 1
                    except Exception as exc:
                        accessible = False
                        reason = str(exc)
                        errors.append({"database_id": database_id, "error": reason})
                rows_returned += len(rows)

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
            "max_depth": traversal_max_depth,
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

    # --- Write ---

    def create_page(
        self,
        parent_id: str,
        title: str,
        content: str | None = None,
        is_database: bool = False,
    ) -> dict[str, Any]:
        try:
            parent = {
                "type": "database_id" if is_database else "page_id",
                ("database_id" if is_database else "page_id"): parent_id,
            }
            properties = {"title": {"title": [{"text": {"content": title}}]}}
            page = self.client.pages.create(parent=parent, properties=properties)
            if content:
                blocks = self.markdown_to_blocks(content)
                if blocks:
                    self.client.blocks.children.append(block_id=page["id"], children=blocks)
            return page
        except Exception as e:
            raise _map_sdk_exc(e, op="create page") from e

    def update_page(self, page_id: str, title: str | None = None) -> dict[str, Any]:
        try:
            properties: dict[str, Any] = {}
            if title:
                properties["title"] = {"title": [{"text": {"content": title}}]}
            return self.client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"update page {page_id}") from e

    def append_blocks(self, page_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            return self.client.blocks.children.append(block_id=page_id, children=blocks)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"append blocks to {page_id}") from e

    def delete_block(self, block_id: str) -> dict[str, Any]:
        try:
            return self.client.blocks.delete(block_id=block_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"delete block {block_id}") from e

    def replace_page_content(self, page_id: str, markdown: str) -> None:
        try:
            for block in self.get_blocks(page_id):
                try:
                    self.delete_block(block["id"])
                except Exception:
                    pass
            new_blocks = self.markdown_to_blocks(markdown)
            for i in range(0, len(new_blocks), 100):
                self.append_blocks(page_id, new_blocks[i : i + 100])
        except Exception as e:
            raise _map_sdk_exc(e, op=f"replace page content for {page_id}") from e

    # --- P0 lifecycle ops ---

    def _default_data_source_id(self, database_id: str) -> str:
        """Return the first data source id of a database (API 2025-09-03).

        Databases no longer carry ``properties`` directly; the schema lives on
        one or more data sources. Most databases have exactly one.
        """
        db = self.get_database(database_id)
        sources = db.get("data_sources") or []
        if not sources:
            raise UsageError(
                f"database {database_id} has no data sources — cannot resolve schema"
            )
        return sources[0]["id"]

    def _resolve_title_property_name(self, database_id: str) -> str:
        """Resolve the name of the title-typed property (the DB has exactly one).

        The title column can be renamed in Notion, so it must be looked up by
        ``type == "title"`` rather than assumed to be ``"Name"``.
        """
        ds_id = self._default_data_source_id(database_id)
        try:
            ds = self.client.data_sources.retrieve(data_source_id=ds_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"retrieve data source {ds_id}") from e
        for name, prop in (ds.get("properties") or {}).items():
            if prop.get("type") == "title":
                return name
        raise UsageError(
            f"data source {ds_id} has no title-typed property"
        )

    @staticmethod
    def _has_title_property(properties: dict[str, Any]) -> bool:
        return any(
            isinstance(v, dict) and "title" in v for v in properties.values()
        )

    def create_db_item(
        self,
        database_id: str,
        *,
        title: str,
        property_json: str | None = None,
    ) -> dict[str, Any]:
        import json
        properties: dict[str, Any] = json.loads(property_json) if property_json else {}
        # Resolve the title property by type (it may be renamed from "Name").
        # Only hit the API when the caller did not already supply a title value.
        if not self._has_title_property(properties):
            title_prop = self._resolve_title_property_name(database_id)
            properties[title_prop] = {"title": [{"text": {"content": title}}]}
        try:
            return self.client.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"create db item in {database_id}") from e

    def create_database(
        self,
        parent_page_id: str,
        *,
        title: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a typed database under a page (API 2025-09-03).

        ``properties`` is a Notion properties map and must include exactly one
        title-typed property (``{"<name>": {"title": {}}}``). Columns are passed
        through ``initial_data_source`` per the current API shape.
        """
        if not self._has_title_property(properties):
            raise UsageError(
                "create-database: properties must include one title property, "
                'e.g. {"Name": {"title": {}}}'
            )
        try:
            return self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": title}}],
                initial_data_source={"properties": properties},
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"create database under {parent_page_id}") from e

    def patch_db_schema(
        self,
        database_id: str,
        *,
        properties: dict[str, Any],
        data_source_id: str | None = None,
    ) -> dict[str, Any]:
        """Add/rename/remove columns on a database's data source (API 2025-09-03).

        Schema changes now target the data source, not the database. When
        ``data_source_id`` is omitted the database's first data source is used.
        """
        ds_id = data_source_id or self._default_data_source_id(database_id)
        try:
            return self.client.data_sources.update(
                data_source_id=ds_id,
                properties=properties,
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"patch schema of data source {ds_id}") from e

    def update_db_item(self, page_id: str, *, property_json: str) -> dict[str, Any]:
        import json
        try:
            return self.client.pages.update(
                page_id=page_id,
                properties=json.loads(property_json),
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"update db item {page_id}") from e

    def archive_page(self, page_id: str, *, confirm_title: str) -> dict[str, Any]:
        try:
            page = self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"retrieve page {page_id} for archive") from e
        actual = self._title_from_object(page)
        if actual != confirm_title:
            raise UsageError(
                f'archive aborted: title mismatch — expected "{confirm_title}", got "{actual}"'
            )
        try:
            return self.client.pages.update(page_id=page_id, archived=True)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"archive page {page_id}") from e

    def append_blocks_from_file(self, page_id: str, content_file: str) -> dict[str, Any]:
        from pathlib import Path as _P
        markdown = _P(content_file).read_text(encoding="utf-8")
        blocks = self.markdown_to_blocks(markdown)
        try:
            return self.client.blocks.children.append(block_id=page_id, children=blocks)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"append blocks to {page_id}") from e

    def replace_page_content_safe(
        self, page_id: str, content_file: str, *, confirm_title: str
    ) -> None:
        """Replace page content with title verification before any mutation."""
        from pathlib import Path as _P
        # 1. Verify title BEFORE any mutation
        try:
            page = self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"retrieve page {page_id} for replace-content") from e
        actual = self._title_from_object(page)
        if actual != confirm_title:
            raise UsageError(
                f'replace-content aborted: title mismatch — expected "{confirm_title}", got "{actual}"'
            )
        # 2. Read file
        markdown = _P(content_file).read_text(encoding="utf-8")
        # 3. Delete existing blocks — fail-fast: any error stops immediately, no append
        try:
            existing = self.get_blocks(page_id)
            for block in existing:
                self.delete_block(block["id"])
        except Exception as e:
            raise _map_sdk_exc(e, op=f"clear blocks for {page_id}") from e
        # 4. Append new blocks (only if all deletions succeeded)
        new_blocks = self.markdown_to_blocks(markdown)
        try:
            for i in range(0, len(new_blocks), 100):
                self.append_blocks(page_id, new_blocks[i : i + 100])
        except Exception as e:
            raise _map_sdk_exc(e, op=f"append new blocks for {page_id}") from e

    # --- Comments ---

    def _rich_text_to_plain(self, rich_text: list[dict[str, Any]]) -> str:
        return "".join(item.get("text", {}).get("content", "") for item in rich_text)

    def _normalize_comment(self, comment: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": comment.get("id", ""),
            "text": self._rich_text_to_plain(comment.get("rich_text", [])),
            "created_time": comment.get("created_time", ""),
            "created_by_id": comment.get("created_by", {}).get("id", ""),
        }

    def list_comments(self, page_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        start_cursor = None
        try:
            while True:
                kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
                if start_cursor:
                    kwargs["start_cursor"] = start_cursor
                response = self.client.comments.list(**kwargs)
                for c in response.get("results", []):
                    results.append(self._normalize_comment(c))
                if not response.get("has_more"):
                    break
                start_cursor = response.get("next_cursor")
        except Exception as e:
            raise _map_sdk_exc(e, op=f"list comments for {page_id}") from e
        return results

    def create_comment(self, page_id: str, body: str) -> dict[str, Any]:
        try:
            result = self.client.comments.create(
                parent={"page_id": page_id},
                rich_text=[{"type": "text", "text": {"content": body}}],
            )
        except Exception as e:
            raise _map_sdk_exc(e, op=f"create comment on {page_id}") from e
        return self._normalize_comment(result)

    # --- Conversion ---

    def blocks_to_markdown(self, blocks: list[dict[str, Any]]) -> str:
        return "".join(self._block_to_markdown(b) for b in blocks)

    def _block_to_markdown(self, block: dict[str, Any]) -> str:  # noqa: C901
        t = block.get("type")
        if t == "paragraph":
            text = self._rich_text_to_markdown(block["paragraph"]["rich_text"])
            return f"{text}\n\n" if text else "\n"
        elif t == "heading_1":
            return f"# {self._rich_text_to_markdown(block['heading_1']['rich_text'])}\n\n"
        elif t == "heading_2":
            return f"## {self._rich_text_to_markdown(block['heading_2']['rich_text'])}\n\n"
        elif t == "heading_3":
            return f"### {self._rich_text_to_markdown(block['heading_3']['rich_text'])}\n\n"
        elif t == "bulleted_list_item":
            return f"- {self._rich_text_to_markdown(block['bulleted_list_item']['rich_text'])}\n"
        elif t == "numbered_list_item":
            return f"1. {self._rich_text_to_markdown(block['numbered_list_item']['rich_text'])}\n"
        elif t == "quote":
            return f"> {self._rich_text_to_markdown(block['quote']['rich_text'])}\n\n"
        elif t == "code":
            cb = block["code"]
            text = self._rich_text_to_markdown(cb["rich_text"])
            lang = cb.get("language", "")
            return f"```{lang}\n{text}\n```\n\n" if text else ""
        elif t == "image":
            img = block["image"]
            caption = self._rich_text_to_markdown(img.get("caption", []))
            url = img.get("file", {}).get("url") or img.get("external", {}).get("url", "")
            return f"![{caption or 'image'}]({url})\n\n" if url else ""
        elif t == "video":
            vid = block["video"]
            caption = self._rich_text_to_markdown(vid.get("caption", []))
            url = vid.get("file", {}).get("url") or vid.get("external", {}).get("url", "")
            return f"[{caption or 'video'}]({url})\n\n" if url else ""
        elif t == "divider":
            return "---\n\n"
        elif t == "callout":
            text = self._rich_text_to_markdown(block["callout"]["rich_text"])
            emoji = block["callout"].get("icon", {}).get("emoji", "💡") if block["callout"].get("icon", {}).get("type") == "emoji" else ""
            return f"> {emoji} {text}\n\n" if text else ""
        elif t == "toggle":
            text = self._rich_text_to_markdown(block["toggle"]["rich_text"])
            return f"<details>\n<summary>{text}</summary>\n\n</details>\n\n" if text else ""
        elif t == "bookmark":
            url = block["bookmark"].get("url", "")
            caption = self._rich_text_to_markdown(block["bookmark"].get("caption", []))
            return f"[{caption or url}]({url})\n\n" if url else ""
        elif t == "table":
            block_id = block.get("id", "")
            if not block_id:
                return ""
            try:
                row_blocks = self.get_blocks(block_id)
            except Exception:
                return ""
            rows = []
            for rb in row_blocks:
                if rb.get("type") == "table_row":
                    rows.append([self._rich_text_to_markdown(c) for c in rb["table_row"]["cells"]])
            if not rows:
                return ""
            col = len(rows[0])
            lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * col) + " |"]
            for row in rows[1:]:
                padded = row + [""] * (col - len(row))
                lines.append("| " + " | ".join(padded[:col]) + " |")
            return "\n".join(lines) + "\n\n"
        return ""

    def _rich_text_to_markdown(self, rich_text: list[dict[str, Any]]) -> str:
        if not rich_text:
            return ""
        result = []
        for item in rich_text:
            if item.get("type") == "text":
                text = item["text"]["content"]
                ann = item.get("annotations", {})
                if ann.get("code"):
                    text = f"`{text}`"
                if ann.get("bold"):
                    text = f"**{text}**"
                if ann.get("italic"):
                    text = f"*{text}*"
                if ann.get("strikethrough"):
                    text = f"~~{text}~~"
                link = item["text"].get("link")
                if link and link.get("url"):
                    text = f"[{text}]({link['url']})"
                result.append(text)
        return "".join(result)

    def parse_inline(self, text: str) -> list[dict[str, Any]]:
        spans = []
        pattern = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|([^*`]+)", re.DOTALL)
        for m in pattern.finditer(text):
            if m.group(1):
                spans.append({"type": "text", "text": {"content": m.group(1)}, "annotations": {"bold": True}})
            elif m.group(2):
                spans.append({"type": "text", "text": {"content": m.group(2)}, "annotations": {"italic": True}})
            elif m.group(3):
                spans.append({"type": "text", "text": {"content": m.group(3)}, "annotations": {"code": True}})
            elif m.group(4):
                spans.append({"type": "text", "text": {"content": m.group(4)}})
        return spans or [{"type": "text", "text": {"content": text}}]

    def markdown_to_blocks(self, markdown: str) -> list[dict[str, Any]]:  # noqa: C901
        blocks = []
        lines = markdown.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("# "):
                blocks.append({"type": "heading_1", "heading_1": {"rich_text": self.parse_inline(line[2:])}})
                i += 1
            elif line.startswith("## "):
                blocks.append({"type": "heading_2", "heading_2": {"rich_text": self.parse_inline(line[3:])}})
                i += 1
            elif line.startswith("### "):
                blocks.append({"type": "heading_3", "heading_3": {"rich_text": self.parse_inline(line[4:])}})
                i += 1
            elif line.startswith("- "):
                blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": self.parse_inline(line[2:])}})
                i += 1
            elif re.match(r"^\d+\. ", line):
                text = re.sub(r"^\d+\. ", "", line)
                blocks.append({"type": "numbered_list_item", "numbered_list_item": {"rich_text": self.parse_inline(text)}})
                i += 1
            elif line.startswith("> "):
                blocks.append({"type": "quote", "quote": {"rich_text": self.parse_inline(line[2:])}})
                i += 1
            elif line.startswith("```"):
                language = line[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append({"type": "code", "code": {"rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}], "language": language or "plain text"}})
                i += 1
            elif line.strip() == "---":
                blocks.append({"type": "divider", "divider": {}})
                i += 1
            elif line.startswith("|"):
                table_rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    row = lines[i]
                    if re.match(r"^[\|\-\:\s]+$", row):
                        i += 1
                        continue
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    table_rows.append(cells)
                    i += 1
                if table_rows:
                    w = max(len(r) for r in table_rows)
                    row_blocks = []
                    for row in table_rows:
                        padded = row + [""] * (w - len(row))
                        row_blocks.append({"type": "table_row", "table_row": {"cells": [self.parse_inline(c) for c in padded]}})
                    blocks.append({"type": "table", "table": {"table_width": w, "has_column_header": True, "has_row_header": False, "children": row_blocks}})
            elif line.strip():
                blocks.append({"type": "paragraph", "paragraph": {"rich_text": self.parse_inline(line)}})
                i += 1
            else:
                i += 1
        return blocks

    def _extract_property_value(
        self,
        prop_data: dict[str, Any],
        prop_type: str,
        resolved_relations: dict[str, dict[str, str]] | None = None,
    ) -> Any:
        if not prop_data:
            return None
        if prop_type == "title":
            return self._rich_text_to_markdown(prop_data.get("title", []))
        elif prop_type == "rich_text":
            return self._rich_text_to_markdown(prop_data.get("rich_text", []))
        elif prop_type == "select":
            sel = prop_data.get("select")
            return sel.get("name") if sel else None
        elif prop_type == "multi_select":
            return ", ".join(i.get("name", "") for i in prop_data.get("multi_select", []))
        elif prop_type == "date":
            date = prop_data.get("date")
            if not date:
                return None
            start = date.get("start", "")
            end = date.get("end")
            return f"{start} → {end}" if end else start
        elif prop_type == "number":
            return prop_data.get("number")
        elif prop_type == "checkbox":
            return "✓" if prop_data.get("checkbox") else "✗"
        elif prop_type in ("url", "email", "phone_number"):
            return prop_data.get(prop_type)
        elif prop_type == "status":
            st = prop_data.get("status")
            return st.get("name") if st else None
        elif prop_type == "people":
            return ", ".join(p.get("name", p.get("id", "")) for p in prop_data.get("people", []))
        elif prop_type in ("created_time", "last_edited_time"):
            return prop_data.get(prop_type)
        elif prop_type == "relation":
            relations = prop_data.get("relation", [])
            if not relations:
                return None
            named = [resolved_relations.get(r["id"]) for r in relations] if resolved_relations else []
            named = [n for n in named if n]
            if named:
                return ", ".join(f"[{n['title']}]({n['url']})" for n in named)
            suffix = "+" if prop_data.get("has_more") else ""
            # Say "unresolved" so a reader cannot mistake it for "no project".
            return (f"{len(relations)} linked item{'s' if len(relations) != 1 else ''}"
                    f"{suffix} (unresolved)")
        elif prop_type == "formula":
            formula = prop_data.get("formula", {})
            ftype = formula.get("type")
            if ftype == "string":
                return formula.get("string")
            elif ftype == "number":
                return formula.get("number")
            elif ftype == "boolean":
                return "✓" if formula.get("boolean") else "✗"
            elif ftype == "date":
                d = formula.get("date")
                if d:
                    return f"{d.get('start', '')} → {d['end']}" if d.get("end") else d.get("start", "")
        elif prop_type == "rollup":
            rollup = prop_data.get("rollup", {})
            rtype = rollup.get("type")
            if rtype == "number":
                return rollup.get("number")
            elif rtype == "array":
                return f"{len(rollup.get('array', []))} items"
        elif prop_type == "files":
            files = prop_data.get("files", [])
            return ", ".join(f.get("name", "file") for f in files) if files else None
        return None

    def resolve_relations(
        self, items: list[dict[str, Any]], prop_names: list[str] | None = None
    ) -> dict[str, dict[str, str]]:
        """Map related page ids to title and url.

        One fetch per unique id, not per row. A deleted or unshared page is
        skipped rather than failing the whole render.
        """
        ids: set[str] = set()
        for item in items:
            for pname, pdata in item.get("properties", {}).items():
                if pdata.get("type") != "relation":
                    continue
                if prop_names and pname not in prop_names:
                    continue
                ids.update(r["id"] for r in pdata.get("relation", []))

        resolved: dict[str, dict[str, str]] = {}
        for page_id in sorted(ids):
            try:
                page = self.get_page(page_id)
            except H2TError:
                continue
            title = "(без названия)"
            for pdata in page.get("properties", {}).values():
                if pdata.get("type") == "title":
                    title = self._extract_property_value(pdata, "title") or title
                    break
            resolved[page_id] = {"title": title, "url": page.get("url", "")}
        return resolved

    def database_items_to_markdown(
        self,
        items: list[dict[str, Any]],
        db_metadata: dict[str, Any],
        resolved_relations: dict[str, dict[str, str]] | None = None,
    ) -> str:
        if not items:
            return "_No items in database_\n"
        md = []
        for i, item in enumerate(items, 1):
            md.append(f"## {i}. ")
            props = item.get("properties", {})
            title_shown = False
            for pname, pdata in props.items():
                ptype = pdata.get("type")
                if ptype == "title":
                    md.append(f"{self._extract_property_value(pdata, 'title') or '(без названия)'}\n\n")
                    title_shown = True
                    break
            if not title_shown:
                md.append("(без названия)\n\n")
            for pname, pdata in props.items():
                ptype = pdata.get("type")
                if ptype == "title":
                    continue
                val = self._extract_property_value(pdata, ptype, resolved_relations)
                if val:
                    md.append(f"- **{pname}:** {val}\n")
            if item.get("url"):
                md.append(f"- **Link:** {item['url']}\n")
            md.append("\n")
        return "".join(md)
