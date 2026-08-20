"""NotionClient — bidirectional Notion adapter (ingest + publish).

Read:  get_page, get_blocks, query_database, find_databases_on_page
Write: create_page, update_page, append_blocks, replace_page_content
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)

try:
    from notion_client import Client
except ImportError as e:
    raise ImportError(
        f"notion-client library not installed: {e}\n"
        "Install: pip install notion-client"
    ) from e

try:
    import httpx
except ImportError as e:
    raise ImportError(
        f"httpx library not installed: {e}\n"
        "Install: pip install httpx"
    ) from e


class NotionClient:
    """Notion API client — read and write pages and databases."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or self._get_token()
        if not self.token:
            raise ValueError(
                "Notion API token not found. Set NOTION_API_TOKEN env var "
                "or create ~/.config/notion/token"
            )
        self.client = Client(auth=self.token)

    def _get_token(self) -> Optional[str]:
        token = os.getenv("NOTION_API_TOKEN")
        if token:
            return token
        config_file = Path.home() / ".config" / "notion" / "token"
        if config_file.exists():
            return config_file.read_text().strip()
        return None

    # --- Read ---

    def get_page(self, page_id: str) -> Dict[str, Any]:
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise Exception(f"Failed to get page {page_id}: {e}") from e

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
            raise Exception(f"Failed to get blocks from {page_id}: {e}") from e

    def query_database(
        self,
        database_id: str,
        filter_dict: Optional[Dict] = None,
        sorts: Optional[List] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self.query_database_page(
            database_id, filter_dict=filter_dict, sorts=sorts, limit=limit
        )["items"]

    def query_database_page(
        self,
        database_id: str,
        filter_dict: Optional[Dict] = None,
        sorts: Optional[List] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Same as query_database, plus whether the database had more to give.

        ``has_more`` is Notion's own flag, so a page that exactly fills ``limit``
        is still reported correctly as complete or truncated.
        """
        try:
            results: List[Dict[str, Any]] = []
            has_more = False
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
                response = httpx.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                results.extend(data["results"])
                has_more = data["has_more"]
                if not has_more or (limit and len(results) >= limit):
                    break
                start_cursor = data.get("next_cursor")
            items = results[:limit] if limit else results
            return {
                "items": items,
                # Trimming to `limit` also truncates, even if Notion had no more.
                "has_more": has_more or len(items) < len(results),
            }
        except Exception as e:
            raise Exception(f"Failed to query database {database_id}: {e}") from e

    def get_database(self, database_id: str) -> Dict[str, Any]:
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            raise Exception(f"Failed to get database {database_id}: {e}") from e

    def find_databases_on_page(self, page_id: str) -> List[Dict[str, Any]]:
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
            raise Exception(f"Failed to find databases on page {page_id}: {e}") from e

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
            raise Exception(f"Failed to create page: {e}") from e

    def update_page(self, page_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        try:
            properties: Dict[str, Any] = {}
            if title:
                properties["title"] = {"title": [{"text": {"content": title}}]}
            return self.client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            raise Exception(f"Failed to update page {page_id}: {e}") from e

    def append_blocks(self, page_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return self.client.blocks.children.append(block_id=page_id, children=blocks)
        except Exception as e:
            raise Exception(f"Failed to append blocks to {page_id}: {e}") from e

    def delete_block(self, block_id: str) -> Dict[str, Any]:
        try:
            return self.client.blocks.delete(block_id=block_id)
        except Exception as e:
            raise Exception(f"Failed to delete block {block_id}: {e}") from e

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
            raise Exception(f"Failed to replace page content for {page_id}: {e}") from e

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

    def _extract_property_value(
        self,
        prop_data: Dict[str, Any],
        prop_type: str,
        resolved_relations: Optional[Dict[str, Dict[str, str]]] = None,
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
            resolved = [resolved_relations.get(r["id"]) for r in relations] if resolved_relations else []
            resolved = [r for r in resolved if r]
            if resolved:
                return ", ".join(f"[{r['title']}]({r['url']})" for r in resolved)
            suffix = "+" if prop_data.get("has_more") else ""
            # Unresolved: say so, so a reader does not mistake it for "no project".
            return f"{len(relations)} linked item{'s' if len(relations) != 1 else ''}{suffix} (unresolved)"
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
        self, items: List[Dict[str, Any]], prop_names: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, str]]:
        """Map related page ids to their title and url.

        One fetch per unique id, not per row. Restrict with ``prop_names`` to
        avoid paying for relations the caller will not display.
        """
        ids = set()
        for item in items:
            for pname, pdata in item.get("properties", {}).items():
                if pdata.get("type") != "relation":
                    continue
                if prop_names and pname not in prop_names:
                    continue
                ids.update(r["id"] for r in pdata.get("relation", []))

        resolved: Dict[str, Dict[str, str]] = {}
        for page_id in sorted(ids):
            try:
                page = self.get_page(page_id)
            except Exception:
                continue  # a deleted or unshared page must not kill the render
            title = "(без названия)"
            for pdata in page.get("properties", {}).values():
                if pdata.get("type") == "title":
                    title = self._extract_property_value(pdata, "title") or title
                    break
            resolved[page_id] = {"title": title, "url": page.get("url", "")}
        return resolved

    def database_items_to_markdown(
        self,
        items: List[Dict[str, Any]],
        db_metadata: Dict[str, Any],
        resolved_relations: Optional[Dict[str, Dict[str, str]]] = None,
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
