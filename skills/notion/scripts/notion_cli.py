#!/usr/bin/env python3
"""
Notion CLI - Command-line interface for Notion API
Supports getting, creating, updating pages and converting to/from Markdown
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

try:
    from notion_client import Client
except ImportError:
    print("Error: notion-client library not installed")
    print("Install it with: pip3 install notion-client")
    sys.exit(1)


class NotionClient:
    """Wrapper for Notion API with Markdown conversion"""

    def __init__(self, token: Optional[str] = None):
        """Initialize Notion client with token from env or file"""
        self.token = token or self._get_token()
        if not self.token:
            raise ValueError(
                "Notion API token not found. Set NOTION_API_TOKEN environment variable "
                "or create ~/.config/notion/token file"
            )
        self.client = Client(auth=self.token)

    def _get_token(self) -> Optional[str]:
        """Get token from environment variable or config file"""
        # Try environment variable
        token = os.getenv('NOTION_API_TOKEN')
        if token:
            return token

        # Try config file
        config_file = Path.home() / '.config' / 'notion' / 'token'
        if config_file.exists():
            return config_file.read_text().strip()

        return None

    # === Page Operations ===

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """Get page metadata"""
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            raise Exception(f"Failed to get page {page_id}: {str(e)}")

    def get_blocks(self, page_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all blocks from a page"""
        blocks = []
        start_cursor = None

        try:
            while True:
                response = self.client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=start_cursor,
                    page_size=min(limit or 100, 100)
                )

                blocks.extend(response['results'])

                if not response['has_more'] or (limit and len(blocks) >= limit):
                    break

                start_cursor = response['next_cursor']

            return blocks[:limit] if limit else blocks

        except Exception as e:
            raise Exception(f"Failed to get blocks from {page_id}: {str(e)}")

    def create_page(self, parent_id: str, title: str, content: Optional[str] = None,
                   is_database: bool = False) -> Dict[str, Any]:
        """Create a new page"""
        try:
            # Prepare parent
            parent = {
                "type": "database_id" if is_database else "page_id",
                ("database_id" if is_database else "page_id"): parent_id
            }

            # Prepare properties
            properties = {
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            }

            # Create page
            page = self.client.pages.create(
                parent=parent,
                properties=properties
            )

            # Add content if provided
            if content:
                blocks = self.markdown_to_blocks(content)
                if blocks:
                    self.client.blocks.children.append(
                        block_id=page['id'],
                        children=blocks
                    )

            return page

        except Exception as e:
            raise Exception(f"Failed to create page: {str(e)}")

    def update_page(self, page_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Update page metadata"""
        try:
            properties = {}
            if title:
                properties["title"] = {
                    "title": [{"text": {"content": title}}]
                }

            return self.client.pages.update(
                page_id=page_id,
                properties=properties
            )

        except Exception as e:
            raise Exception(f"Failed to update page {page_id}: {str(e)}")

    def append_blocks(self, page_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Append blocks to a page"""
        try:
            return self.client.blocks.children.append(
                block_id=page_id,
                children=blocks
            )
        except Exception as e:
            raise Exception(f"Failed to append blocks to {page_id}: {str(e)}")

    def delete_block(self, block_id: str) -> Dict[str, Any]:
        """Delete a block"""
        try:
            return self.client.blocks.delete(block_id=block_id)
        except Exception as e:
            raise Exception(f"Failed to delete block {block_id}: {str(e)}")

    def replace_page_content(self, page_id: str, markdown: str) -> None:
        """Replace all content of a page with new markdown"""
        try:
            # Get all existing blocks
            existing_blocks = self.get_blocks(page_id)

            # Delete all existing blocks
            for block in existing_blocks:
                try:
                    self.delete_block(block['id'])
                except Exception as e:
                    print(f"Warning: Failed to delete block {block['id']}: {e}", file=sys.stderr)

            # Convert markdown to blocks
            new_blocks = self.markdown_to_blocks(markdown)

            # Append new blocks in batches (Notion API limit: 100 blocks per request)
            batch_size = 100
            for i in range(0, len(new_blocks), batch_size):
                batch = new_blocks[i:i + batch_size]
                self.append_blocks(page_id, batch)

        except Exception as e:
            raise Exception(f"Failed to replace page content for {page_id}: {str(e)}")

    # === Database Operations ===

    def query_database(self, database_id: str, filter_dict: Optional[Dict] = None,
                      sorts: Optional[List] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query a database with optional filters and sorts"""
        try:
            import httpx

            results = []
            start_cursor = None

            while True:
                body = {}
                if filter_dict:
                    body["filter"] = filter_dict
                if sorts:
                    body["sorts"] = sorts
                if start_cursor:
                    body["start_cursor"] = start_cursor

                # Use direct HTTP request for database query
                url = f"https://api.notion.com/v1/databases/{database_id}/query"
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }

                response = httpx.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()

                results.extend(data['results'])

                if not data['has_more'] or (limit and len(results) >= limit):
                    break

                start_cursor = data.get('next_cursor')

            return results[:limit] if limit else results

        except Exception as e:
            raise Exception(f"Failed to query database {database_id}: {str(e)}")

    def get_database(self, database_id: str) -> Dict[str, Any]:
        """Get database metadata including properties schema"""
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            raise Exception(f"Failed to get database {database_id}: {str(e)}")

    def find_databases_on_page(self, page_id: str) -> List[Dict[str, Any]]:
        """Find all databases (child and linked) on a page"""
        try:
            databases = []
            blocks = self.get_blocks(page_id)

            for block in blocks:
                block_type = block.get('type')
                block_id = block.get('id')

                # Child database (inline)
                if block_type == 'child_database':
                    db_title = block.get('child_database', {}).get('title', 'Untitled')
                    databases.append({
                        'type': 'child_database',
                        'database_id': block_id,
                        'title': db_title,
                        'block': block
                    })

                # Linked database (view)
                elif block_type == 'linked_database':
                    db_id = block.get('linked_database', {}).get('database_id')
                    if db_id:
                        # Get database info
                        try:
                            db_info = self.get_database(db_id)
                            db_title = db_info.get('title', [{}])[0].get('plain_text', 'Untitled')
                            databases.append({
                                'type': 'linked_database',
                                'database_id': db_id,
                                'title': db_title,
                                'block': block
                            })
                        except:
                            databases.append({
                                'type': 'linked_database',
                                'database_id': db_id,
                                'title': 'Unknown',
                                'block': block
                            })

            return databases
        except Exception as e:
            raise Exception(f"Failed to find databases on page {page_id}: {str(e)}")

    def _extract_property_value(self, prop_data: Dict[str, Any], prop_type: str) -> Any:
        """Extract value from property based on its type"""
        if not prop_data:
            return None

        if prop_type == "title":
            rich_text = prop_data.get("title", [])
            return self._rich_text_to_markdown(rich_text)

        elif prop_type == "rich_text":
            rich_text = prop_data.get("rich_text", [])
            return self._rich_text_to_markdown(rich_text)

        elif prop_type == "select":
            select = prop_data.get("select")
            return select.get("name") if select else None

        elif prop_type == "multi_select":
            items = prop_data.get("multi_select", [])
            return ", ".join([item.get("name", "") for item in items])

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

        elif prop_type == "url":
            return prop_data.get("url")

        elif prop_type == "email":
            return prop_data.get("email")

        elif prop_type == "phone_number":
            return prop_data.get("phone_number")

        elif prop_type == "status":
            status = prop_data.get("status")
            return status.get("name") if status else None

        elif prop_type == "people":
            people = prop_data.get("people", [])
            return ", ".join([p.get("name", p.get("id", "")) for p in people])

        elif prop_type == "created_time":
            return prop_data.get("created_time")

        elif prop_type == "last_edited_time":
            return prop_data.get("last_edited_time")

        elif prop_type == "relation":
            relations = prop_data.get("relation", [])
            if not relations:
                return None
            count = len(relations)
            has_more = prop_data.get("has_more", False)
            suffix = "+" if has_more else ""
            return f"{count} linked item{'s' if count != 1 else ''}{suffix}"

        elif prop_type == "formula":
            formula = prop_data.get("formula", {})
            formula_type = formula.get("type")
            if formula_type == "string":
                return formula.get("string")
            elif formula_type == "number":
                return formula.get("number")
            elif formula_type == "boolean":
                return "✓" if formula.get("boolean") else "✗"
            elif formula_type == "date":
                date = formula.get("date")
                if date:
                    start = date.get("start", "")
                    end = date.get("end")
                    return f"{start} → {end}" if end else start
            return None

        elif prop_type == "rollup":
            rollup = prop_data.get("rollup", {})
            rollup_type = rollup.get("type")
            if rollup_type == "number":
                return rollup.get("number")
            elif rollup_type == "array":
                return f"{len(rollup.get('array', []))} items"
            return None

        elif prop_type == "files":
            files = prop_data.get("files", [])
            if not files:
                return None
            return ", ".join([f.get("name", "file") for f in files])

        else:
            return None

    def database_items_to_markdown(self, items: List[Dict[str, Any]],
                                   db_metadata: Dict[str, Any]) -> str:
        """Convert database items to markdown format"""
        if not items:
            return "_No items in database_\n"

        # Build markdown
        markdown = []

        for i, item in enumerate(items, 1):
            markdown.append(f"## {i}. ")

            # Get properties from the item itself
            item_props = item.get("properties", {})

            # Find and display title first
            title_displayed = False
            for prop_name, prop_data in item_props.items():
                prop_type = prop_data.get("type")
                if prop_type == "title":
                    title_value = self._extract_property_value(prop_data, "title")
                    markdown.append(f"{title_value or '(без названия)'}\n\n")
                    title_displayed = True
                    break

            if not title_displayed:
                markdown.append("(без названия)\n\n")

            # Display other properties
            for prop_name, prop_data in item_props.items():
                prop_type = prop_data.get("type")

                # Skip title (already displayed)
                if prop_type == "title":
                    continue

                value = self._extract_property_value(prop_data, prop_type)

                if value:
                    markdown.append(f"- **{prop_name}:** {value}\n")

            markdown.append("\n")

        return ''.join(markdown)

    # === Markdown Conversion ===

    def blocks_to_markdown(self, blocks: List[Dict[str, Any]]) -> str:
        """Convert Notion blocks to Markdown"""
        markdown = []

        for block in blocks:
            md_text = self._block_to_markdown(block)
            if md_text:
                markdown.append(md_text)

        return ''.join(markdown)

    def _block_to_markdown(self, block: Dict[str, Any]) -> str:
        """Convert a single Notion block to Markdown"""
        block_type = block.get('type')

        if block_type == 'paragraph':
            text = self._rich_text_to_markdown(block['paragraph']['rich_text'])
            return f"{text}\n\n" if text else "\n"

        elif block_type == 'heading_1':
            text = self._rich_text_to_markdown(block['heading_1']['rich_text'])
            return f"# {text}\n\n" if text else ""

        elif block_type == 'heading_2':
            text = self._rich_text_to_markdown(block['heading_2']['rich_text'])
            return f"## {text}\n\n" if text else ""

        elif block_type == 'heading_3':
            text = self._rich_text_to_markdown(block['heading_3']['rich_text'])
            return f"### {text}\n\n" if text else ""

        elif block_type == 'bulleted_list_item':
            text = self._rich_text_to_markdown(block['bulleted_list_item']['rich_text'])
            return f"- {text}\n" if text else ""

        elif block_type == 'numbered_list_item':
            text = self._rich_text_to_markdown(block['numbered_list_item']['rich_text'])
            return f"1. {text}\n" if text else ""

        elif block_type == 'quote':
            text = self._rich_text_to_markdown(block['quote']['rich_text'])
            return f"> {text}\n\n" if text else ""

        elif block_type == 'code':
            code_block = block['code']
            text = self._rich_text_to_markdown(code_block['rich_text'])
            language = code_block.get('language', '')
            return f"```{language}\n{text}\n```\n\n" if text else ""

        elif block_type == 'image':
            image = block['image']
            caption = self._rich_text_to_markdown(image.get('caption', []))
            url = image.get('file', {}).get('url') or image.get('external', {}).get('url', '')
            if url:
                alt = caption or 'image'
                return f"![{alt}]({url})\n\n"

        elif block_type == 'video':
            video = block['video']
            caption = self._rich_text_to_markdown(video.get('caption', []))
            url = video.get('file', {}).get('url') or video.get('external', {}).get('url', '')
            if url:
                title = caption or 'Видео'
                return f"[{title}]({url})\n\n"

        elif block_type == 'divider':
            return "---\n\n"

        elif block_type == 'callout':
            text = self._rich_text_to_markdown(block['callout']['rich_text'])
            icon = block['callout'].get('icon', {})
            emoji = ''
            if icon.get('type') == 'emoji':
                emoji = icon.get('emoji', '💡')
            return f"> {emoji} {text}\n\n" if text else ""

        elif block_type == 'toggle':
            text = self._rich_text_to_markdown(block['toggle']['rich_text'])
            return f"<details>\n<summary>{text}</summary>\n\n</details>\n\n" if text else ""

        elif block_type == 'bookmark':
            url = block['bookmark'].get('url', '')
            caption = self._rich_text_to_markdown(block['bookmark'].get('caption', []))
            title = caption or url
            return f"[{title}]({url})\n\n" if url else ""

        elif block_type == 'table':
            block_id = block.get('id', '')
            if not block_id:
                return ""
            try:
                row_blocks = self.get_blocks(block_id)
            except Exception:
                return ""
            rows = []
            for row_block in row_blocks:
                if row_block.get('type') == 'table_row':
                    cells = row_block['table_row']['cells']
                    rows.append([self._rich_text_to_markdown(cell) for cell in cells])
            if not rows:
                return ""
            col_count = len(rows[0])
            lines = ['| ' + ' | '.join(rows[0]) + ' |']
            lines.append('| ' + ' | '.join(['---'] * col_count) + ' |')
            for row in rows[1:]:
                padded = row + [''] * (col_count - len(row))
                lines.append('| ' + ' | '.join(padded[:col_count]) + ' |')
            return '\n'.join(lines) + '\n\n'

        return ""

    def _rich_text_to_markdown(self, rich_text: List[Dict[str, Any]]) -> str:
        """Convert Notion rich text to Markdown"""
        if not rich_text:
            return ""

        result = []
        for item in rich_text:
            if item.get('type') == 'text':
                text = item['text']['content']
                annotations = item.get('annotations', {})

                # Apply formatting
                if annotations.get('code'):
                    text = f"`{text}`"
                if annotations.get('bold'):
                    text = f"**{text}**"
                if annotations.get('italic'):
                    text = f"*{text}*"
                if annotations.get('strikethrough'):
                    text = f"~~{text}~~"

                # Add link
                link = item['text'].get('link')
                if link and link.get('url'):
                    text = f"[{text}]({link['url']})"

                result.append(text)

        return ''.join(result)

    def parse_inline(self, text: str) -> List[Dict[str, Any]]:
        """Parse inline markdown (bold, italic, code) into Notion rich_text spans."""
        spans = []
        pattern = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|([^*`]+)', re.DOTALL)
        for m in pattern.finditer(text):
            if m.group(1):  # **bold**
                spans.append({'type': 'text', 'text': {'content': m.group(1)},
                              'annotations': {'bold': True}})
            elif m.group(2):  # *italic*
                spans.append({'type': 'text', 'text': {'content': m.group(2)},
                              'annotations': {'italic': True}})
            elif m.group(3):  # `code`
                spans.append({'type': 'text', 'text': {'content': m.group(3)},
                              'annotations': {'code': True}})
            elif m.group(4):  # plain text
                spans.append({'type': 'text', 'text': {'content': m.group(4)}})
        return spans if spans else [{'type': 'text', 'text': {'content': text}}]

    def markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:
        """Convert Markdown to Notion blocks"""
        blocks = []
        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Heading 1
            if line.startswith('# '):
                blocks.append({
                    'type': 'heading_1',
                    'heading_1': {'rich_text': self.parse_inline(line[2:])}
                })
                i += 1

            # Heading 2
            elif line.startswith('## '):
                blocks.append({
                    'type': 'heading_2',
                    'heading_2': {'rich_text': self.parse_inline(line[3:])}
                })
                i += 1

            # Heading 3
            elif line.startswith('### '):
                blocks.append({
                    'type': 'heading_3',
                    'heading_3': {'rich_text': self.parse_inline(line[4:])}
                })
                i += 1

            # Bulleted list
            elif line.startswith('- '):
                blocks.append({
                    'type': 'bulleted_list_item',
                    'bulleted_list_item': {'rich_text': self.parse_inline(line[2:])}
                })
                i += 1

            # Numbered list
            elif re.match(r'^\d+\. ', line):
                text = re.sub(r'^\d+\. ', '', line)
                blocks.append({
                    'type': 'numbered_list_item',
                    'numbered_list_item': {'rich_text': self.parse_inline(text)}
                })
                i += 1

            # Quote
            elif line.startswith('> '):
                blocks.append({
                    'type': 'quote',
                    'quote': {'rich_text': self.parse_inline(line[2:])}
                })
                i += 1

            # Code block
            elif line.startswith('```'):
                language = line[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append({
                    'type': 'code',
                    'code': {
                        'rich_text': [{'type': 'text', 'text': {'content': '\n'.join(code_lines)}}],
                        'language': language or 'plain text'
                    }
                })
                i += 1

            # Divider
            elif line.strip() == '---':
                blocks.append({'type': 'divider', 'divider': {}})
                i += 1

            # Table: collect consecutive | rows, skip separator rows
            elif line.startswith('|'):
                table_rows = []
                while i < len(lines) and lines[i].startswith('|'):
                    row = lines[i]
                    # Skip separator rows (|---|---|)
                    if re.match(r'^[\|\-\:\s]+$', row):
                        i += 1
                        continue
                    cells = [c.strip() for c in row.strip('|').split('|')]
                    table_rows.append(cells)
                    i += 1

                if table_rows:
                    table_width = max(len(row) for row in table_rows)
                    row_blocks = []
                    for row in table_rows:
                        padded = row + [''] * (table_width - len(row))
                        row_blocks.append({
                            'type': 'table_row',
                            'table_row': {
                                'cells': [self.parse_inline(cell) for cell in padded]
                            }
                        })
                    blocks.append({
                        'type': 'table',
                        'table': {
                            'table_width': table_width,
                            'has_column_header': True,
                            'has_row_header': False,
                            'children': row_blocks
                        }
                    })

            # Paragraph
            elif line.strip():
                blocks.append({
                    'type': 'paragraph',
                    'paragraph': {'rich_text': self.parse_inline(line)}
                })
                i += 1

            else:
                i += 1

        return blocks


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Notion CLI - Work with Notion API from command line',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Get page command
    get_parser = subparsers.add_parser('get', help='Get page metadata')
    get_parser.add_argument('page_id', help='Page ID')
    get_parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                           help='Output format')

    # Get blocks command
    blocks_parser = subparsers.add_parser('blocks', help='Get page blocks')
    blocks_parser.add_argument('page_id', help='Page ID')
    blocks_parser.add_argument('--limit', type=int, help='Limit number of blocks')
    blocks_parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                              help='Output format')

    # Create page command
    create_parser = subparsers.add_parser('create', help='Create new page')
    create_parser.add_argument('parent_id', help='Parent page or database ID')
    create_parser.add_argument('title', help='Page title')
    create_parser.add_argument('--content', help='Page content (Markdown)')
    create_parser.add_argument('--file', help='Read content from file')
    create_parser.add_argument('--database', action='store_true',
                              help='Parent is a database')

    # Update page command
    update_parser = subparsers.add_parser('update', help='Update page')
    update_parser.add_argument('page_id', help='Page ID')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--append', help='Append content (Markdown)')
    update_parser.add_argument('--file', help='Read content from file')
    update_parser.add_argument('--replace', action='store_true',
                              help='Replace all page content (use with --file or --append)')

    # Search database command
    search_parser = subparsers.add_parser('search', help='Search database')
    search_parser.add_argument('database_id', help='Database ID')
    search_parser.add_argument('--filter', help='Simple filter (e.g., "Status=Done")')
    search_parser.add_argument('--filter-json', help='JSON filter for complex queries')
    search_parser.add_argument('--limit', type=int, help='Limit results')
    search_parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                              help='Output format')

    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync page to Markdown file')
    sync_parser.add_argument('page_id', help='Page ID')
    sync_parser.add_argument('output_file', help='Output Markdown file')
    sync_parser.add_argument('--preserve-metadata', action='store_true',
                            help='Preserve frontmatter metadata')

    # Get database command
    get_db_parser = subparsers.add_parser('get-database', help='Get database items')
    get_db_parser.add_argument('database_id', help='Database ID')
    get_db_parser.add_argument('--format', choices=['json', 'markdown'], default='markdown',
                              help='Output format')
    get_db_parser.add_argument('--limit', type=int, help='Limit number of items')

    # Find databases command
    find_db_parser = subparsers.add_parser('find-databases', help='Find databases on a page')
    find_db_parser.add_argument('page_id', help='Page ID')
    find_db_parser.add_argument('--format', choices=['json', 'markdown'], default='markdown',
                              help='Output format')

    # Find project tasks command
    find_tasks_parser = subparsers.add_parser('find-project-tasks',
                                             help='Find all tasks related to a project page')
    find_tasks_parser.add_argument('project_page_id', help='Project page ID')
    find_tasks_parser.add_argument('--database-id',
                                  default='beabac7bf4314952a9327759c638d89f',
                                  help='Tasks database ID (default: workspace tasks DB)')
    find_tasks_parser.add_argument('--format', choices=['json', 'markdown'], default='markdown',
                                  help='Output format')
    find_tasks_parser.add_argument('--limit', type=int, help='Limit number of tasks')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        client = NotionClient()

        if args.command == 'get':
            page = client.get_page(args.page_id)
            if args.format == 'json':
                print(json.dumps(page, indent=2, ensure_ascii=False))
            else:
                blocks = client.get_blocks(args.page_id)
                markdown = client.blocks_to_markdown(blocks)
                print(markdown)

        elif args.command == 'blocks':
            blocks = client.get_blocks(args.page_id, limit=args.limit)
            if args.format == 'json':
                print(json.dumps(blocks, indent=2, ensure_ascii=False))
            else:
                markdown = client.blocks_to_markdown(blocks)
                print(markdown)

        elif args.command == 'create':
            content = args.content
            if args.file:
                with open(args.file, 'r', encoding='utf-8') as f:
                    content = f.read()

            page = client.create_page(
                args.parent_id,
                args.title,
                content=content,
                is_database=args.database
            )
            print(json.dumps(page, indent=2, ensure_ascii=False))

        elif args.command == 'update':
            if args.title:
                result = client.update_page(args.page_id, title=args.title)
                print(json.dumps(result, indent=2, ensure_ascii=False))

            if args.append or args.file:
                content = args.append
                if args.file:
                    with open(args.file, 'r', encoding='utf-8') as f:
                        content = f.read()

                if args.replace:
                    # Replace all page content
                    client.replace_page_content(args.page_id, content)
                    print(f"✓ Page content replaced successfully")
                else:
                    # Append to existing content
                    blocks = client.markdown_to_blocks(content)
                    result = client.append_blocks(args.page_id, blocks)
                    print(json.dumps(result, indent=2, ensure_ascii=False))

        elif args.command == 'search':
            # Parse filter
            filter_dict = None
            if args.filter_json:
                # Use JSON filter directly
                filter_dict = json.loads(args.filter_json)
            elif args.filter:
                # Simple filter parser: "Property=Value"
                parts = args.filter.split('=')
                if len(parts) == 2:
                    filter_dict = {
                        'property': parts[0].strip(),
                        'select': {'equals': parts[1].strip()}
                    }

            results = client.query_database(args.database_id, filter_dict=filter_dict,
                                          limit=args.limit)

            if args.format == 'json':
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                # Markdown format - get database metadata first
                db_metadata = client.get_database(args.database_id)
                markdown = client.database_items_to_markdown(results, db_metadata)
                print(markdown)

        elif args.command == 'sync':
            # Get page content
            blocks = client.get_blocks(args.page_id)
            markdown = client.blocks_to_markdown(blocks)

            # Add metadata if requested
            if args.preserve_metadata:
                page = client.get_page(args.page_id)
                created = page.get('created_time', '')
                modified = page.get('last_edited_time', '')

                frontmatter = f"""---
notion_id: {args.page_id}
created: {created}
modified: {modified}
---

"""
                markdown = frontmatter + markdown

            # Write to file
            output_path = Path(args.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding='utf-8')

            print(f"Synced to {output_path}")

        elif args.command == 'get-database':
            # Get database metadata
            db_metadata = client.get_database(args.database_id)

            # Query database items
            items = client.query_database(args.database_id, limit=args.limit)

            if args.format == 'json':
                # Return raw JSON
                print(json.dumps(items, indent=2, ensure_ascii=False))
            else:
                # Convert to markdown
                markdown = client.database_items_to_markdown(items, db_metadata)
                print(markdown)

        elif args.command == 'find-databases':
            # Find databases on page
            databases = client.find_databases_on_page(args.page_id)

            if args.format == 'json':
                print(json.dumps(databases, indent=2, ensure_ascii=False))
            else:
                # Print in markdown format
                if not databases:
                    print("No databases found on this page")
                else:
                    print(f"Found {len(databases)} database(s) on page:\n")
                    for i, db in enumerate(databases, 1):
                        print(f"{i}. **{db['title']}**")
                        print(f"   - Type: {db['type']}")
                        print(f"   - Database ID: `{db['database_id']}`")
                        print()

        elif args.command == 'find-project-tasks':
            # Find all tasks related to a project page
            # Use relation filter to find tasks where Project contains the page ID
            filter_dict = {
                'property': 'Project',
                'relation': {
                    'contains': args.project_page_id
                }
            }

            tasks = client.query_database(args.database_id, filter_dict=filter_dict,
                                        limit=args.limit)

            if args.format == 'json':
                print(json.dumps(tasks, indent=2, ensure_ascii=False))
            else:
                # Convert to markdown
                if not tasks:
                    print(f"No tasks found for project {args.project_page_id}")
                else:
                    db_metadata = client.get_database(args.database_id)
                    markdown = client.database_items_to_markdown(tasks, db_metadata)
                    print(f"Found {len(tasks)} task(s) for project:\n")
                    print(markdown)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
