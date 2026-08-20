"""Unit tests for NotionClient markdown helpers (no network calls)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import pytest
from clients.notion import NotionClient


@pytest.fixture
def client():
    # object.__new__ bypasses __init__ (skips OAuth) — safe here because
    # all tested methods are pure converters that don't use self.client
    c = object.__new__(NotionClient)
    c.token = "fake"
    return c


def test_rich_text_empty(client):
    assert client._rich_text_to_markdown([]) == ""


def test_rich_text_bold(client):
    rich = [{"type": "text", "text": {"content": "hello"}, "annotations": {"bold": True}}]
    assert client._rich_text_to_markdown(rich) == "**hello**"


def test_rich_text_italic(client):
    rich = [{"type": "text", "text": {"content": "hi"}, "annotations": {"italic": True}}]
    assert client._rich_text_to_markdown(rich) == "*hi*"


def test_rich_text_code(client):
    rich = [{"type": "text", "text": {"content": "x"}, "annotations": {"code": True}}]
    assert client._rich_text_to_markdown(rich) == "`x`"


def test_block_heading_2(client):
    block = {
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Title"}, "annotations": {}}]},
    }
    assert client._block_to_markdown(block) == "## Title\n\n"


def test_block_divider(client):
    assert client._block_to_markdown({"type": "divider", "divider": {}}) == "---\n\n"


def test_block_paragraph(client):
    block = {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Hello"}, "annotations": {}}]},
    }
    result = client._block_to_markdown(block)
    assert result == "Hello\n\n"


def test_parse_inline_bold(client):
    spans = client.parse_inline("**bold**")
    assert any(s.get("annotations", {}).get("bold") for s in spans)


def test_parse_inline_plain(client):
    spans = client.parse_inline("plain text")
    assert spans[0]["text"]["content"] == "plain text"


def test_markdown_to_blocks_heading(client):
    blocks = client.markdown_to_blocks("# Hello")
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Hello"


def test_markdown_to_blocks_list(client):
    blocks = client.markdown_to_blocks("- item one\n- item two")
    assert len(blocks) == 2
    assert all(b["type"] == "bulleted_list_item" for b in blocks)


def test_blocks_to_markdown_roundtrip(client):
    md = "# Heading\n\nSome text.\n\n- list item\n\n"
    blocks = client.markdown_to_blocks(md)
    result = client.blocks_to_markdown(blocks)
    assert result.strip() == md.strip()


# --- relation resolution and page links -------------------------------------

def _task(title: str, relation_id: str | None = None, url: str = "") -> dict:
    props: dict = {
        "Task name": {"type": "title", "title": [{"type": "text", "text": {"content": title},
                                                  "annotations": {}, "plain_text": title}]},
    }
    if relation_id:
        props["Project"] = {"type": "relation", "relation": [{"id": relation_id}], "has_more": False}
    return {"properties": props, "url": url}


def test_unresolved_relation_is_labelled_not_silent(client):
    """`1 linked item` alone reads like data; it must say it is unresolved."""
    prop = {"type": "relation", "relation": [{"id": "abc"}], "has_more": False}
    assert client._extract_property_value(prop, "relation") == "1 linked item (unresolved)"


def test_resolved_relation_renders_title_and_link(client):
    prop = {"type": "relation", "relation": [{"id": "abc"}], "has_more": False}
    resolved = {"abc": {"title": "Qatal Yiktol", "url": "https://notion.so/qy"}}
    out = client._extract_property_value(prop, "relation", resolved)
    assert out == "[Qatal Yiktol](https://notion.so/qy)"


def test_markdown_includes_page_url(client):
    md = client.database_items_to_markdown([_task("Do it", url="https://notion.so/t1")], {})
    assert "https://notion.so/t1" in md


def test_markdown_uses_resolved_relations(client):
    items = [_task("Do it", relation_id="abc", url="https://notion.so/t1")]
    resolved = {"abc": {"title": "Qatal Yiktol", "url": "https://notion.so/qy"}}
    md = client.database_items_to_markdown(items, {}, resolved)
    assert "[Qatal Yiktol](https://notion.so/qy)" in md
    assert "linked item" not in md


def test_resolve_relations_fetches_each_unique_id_once(client, monkeypatch):
    calls = []

    def fake_get_page(page_id):
        calls.append(page_id)
        return {
            "url": f"https://notion.so/{page_id}",
            "properties": {"Name": {"type": "title",
                                    "title": [{"type": "text", "text": {"content": "P"},
                                               "annotations": {}, "plain_text": "P"}]}},
        }

    monkeypatch.setattr(client, "get_page", fake_get_page)
    items = [_task("a", "same"), _task("b", "same"), _task("c", "other")]
    resolved = client.resolve_relations(items)
    assert sorted(calls) == ["other", "same"]
    assert resolved["same"]["title"] == "P"


def test_resolve_relations_skips_unreachable_page(client, monkeypatch):
    def boom(page_id):
        raise Exception("404")

    monkeypatch.setattr(client, "get_page", boom)
    assert client.resolve_relations([_task("a", "gone")]) == {}
