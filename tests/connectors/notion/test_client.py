import pytest
from h2t.connectors.notion.client import NotionClient
from h2t.core.errors import ConfigError


@pytest.fixture
def conv():
    c = object.__new__(NotionClient)  # bypass __init__ (no token / no SDK)
    c.token = "fake"
    return c


def test_rich_text_bold(conv):
    rich = [{"type": "text", "text": {"content": "hello"}, "annotations": {"bold": True}}]
    assert conv._rich_text_to_markdown(rich) == "**hello**"


def test_markdown_to_blocks_heading(conv):
    blocks = conv.markdown_to_blocks("# Hello")
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Hello"


def test_blocks_to_markdown_roundtrip(conv):
    md = "# Heading\n\nSome text.\n\n- list item\n\n"
    assert conv.blocks_to_markdown(conv.markdown_to_blocks(md)).strip() == md.strip()


def test_missing_token_raises_configerror(monkeypatch):
    import pathlib
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr("h2t.core.secrets.Path.home",
                        lambda: pathlib.Path("/nonexistent-xyz"))
    with pytest.raises(ConfigError):
        NotionClient()


def test_missing_sdk_raises_configerror(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "tok")
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name == "notion_client":
            raise ImportError("no notion_client")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    with pytest.raises(ConfigError) as ei:
        NotionClient()
    assert "notion-client" in (ei.value.hint or "")
