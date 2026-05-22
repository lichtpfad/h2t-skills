"""NotionClient — bidirectional Notion adapter (re-wrapped, typed errors).

API logic is identical to lib/clients/notion.py; only side effects and error
types changed per spec §10 (re-wrap not rewrite).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from h2t_ops.core.errors import (
    AuthError, ConfigError, H2TError, NetworkError, NotFoundError, ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import resolve_notion_token


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

    def __init__(self, token: Optional[str] = None) -> None:
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
        try:
            import httpx  # optional dep — lazy (spec §4.1)
        except ImportError as e:
            raise ConfigError(
                "httpx library not installed.",
                hint="pip install httpx  (or run /h2t-core:setup)",
            ) from e
        try:
            resp = httpx.post(url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise _map_http_status(e.response.status_code, str(e)) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Notion request failed: {e}") from e

    # --- Read ---

    def get_page(self, page_id: str) -> Dict[str, Any]:
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get page {page_id}") from e

    def get_blocks(self, page_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
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

        self._last_traversal_errors: List[Dict[str, str]] = []
        if max_depth == 0:
            return

        seen: set[str] = set()
        emitted = 0

        def walk(block_id: str, depth: int, path: List[str]):
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
        filter_dict: Optional[Dict] = None,
        sorts: Optional[List] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            results: List[Dict[str, Any]] = []
            start_cursor = None
            while True:
                body: Dict[str, Any] = {}
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
                if not data["has_more"] or (limit and len(results) >= limit):
                    break
                start_cursor = data.get("next_cursor")
            return results[:limit] if limit else results
        except Exception as e:
            raise _map_sdk_exc(e, op=f"query database {database_id}") from e

    def get_database(self, database_id: str) -> Dict[str, Any]:
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"get database {database_id}") from e

    def search_workspace(
        self,
        object_type: str = "all",
        *,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        if limit is not None and limit < 0:
            raise UsageError("limit must be non-negative")
        if limit == 0:
            return {"kind": "notion_workspace_search/v1", "object": object_type, "results": []}
        query_filter = None
        if object_type in ("page", "database"):
            query_filter = {"property": "object", "value": object_type}
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
        databases: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
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

            rows: List[Dict[str, Any]] = []
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
        content: Optional[str] = None,
        is_database: bool = False,
    ) -> Dict[str, Any]:
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

    def update_page(self, page_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        try:
            properties: Dict[str, Any] = {}
            if title:
                properties["title"] = {"title": [{"text": {"content": title}}]}
            return self.client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"update page {page_id}") from e

    def append_blocks(self, page_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return self.client.blocks.children.append(block_id=page_id, children=blocks)
        except Exception as e:
            raise _map_sdk_exc(e, op=f"append blocks to {page_id}") from e

    def delete_block(self, block_id: str) -> Dict[str, Any]:
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

    # --- Conversion ---

    def blocks_to_markdown(self, blocks: List[Dict[str, Any]]) -> str:
        return "".join(self._block_to_markdown(b) for b in blocks)

    def _block_to_markdown(self, block: Dict[str, Any]) -> str:  # noqa: C901
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

    def _rich_text_to_markdown(self, rich_text: List[Dict[str, Any]]) -> str:
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

    def parse_inline(self, text: str) -> List[Dict[str, Any]]:
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

    def markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:  # noqa: C901
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

    def _extract_property_value(self, prop_data: Dict[str, Any], prop_type: str) -> Any:
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
            suffix = "+" if prop_data.get("has_more") else ""
            return f"{len(relations)} linked item{'s' if len(relations) != 1 else ''}{suffix}"
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

    def database_items_to_markdown(self, items: List[Dict[str, Any]], db_metadata: Dict[str, Any]) -> str:
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
                val = self._extract_property_value(pdata, ptype)
                if val:
                    md.append(f"- **{pname}:** {val}\n")
            md.append("\n")
        return "".join(md)
