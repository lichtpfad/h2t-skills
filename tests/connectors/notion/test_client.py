import pytest
from h2t_ops.connectors.notion.client import NotionClient
from h2t_ops.core.errors import ConfigError


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
    monkeypatch.setattr("h2t_ops.core.secrets.Path.home",
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


import pytest
from h2t_ops.connectors.notion.client import _map_http_status, _map_sdk_exc
from h2t_ops.core.errors import AuthError, NetworkError, NotFoundError, ProviderError, UsageError


@pytest.mark.parametrize("status,expected", [
    (401, AuthError), (403, AuthError), (404, NotFoundError),
    (500, ProviderError), (503, ProviderError), (400, ProviderError),
])
def test_map_http_status(status, expected):
    assert isinstance(_map_http_status(status, "err"), expected)


@pytest.mark.parametrize("msg,expected", [
    ("insufficient permission to access", AuthError),
    ("could not find page with id", NotFoundError),
    ("connection refused", NetworkError),
    ("request to notion api has timed out", NetworkError),
    ("some other api error", ProviderError),
])
def test_map_sdk_exc_substring(msg, expected):
    assert isinstance(_map_sdk_exc(Exception(msg), op="op"), expected)


def test_map_sdk_exc_passthrough_typed():
    e = NotFoundError("already typed")
    assert _map_sdk_exc(e, op="op") is e          # same object, not re-wrapped


class _FakeAPIErr(Exception):
    def __init__(self, code, status): super().__init__("opaque message"); self.code=code; self.status=status


@pytest.mark.parametrize("code,status,expected", [
    ("unauthorized", 401, AuthError),
    ("restricted_resource", 403, AuthError),
    ("object_not_found", 404, NotFoundError),
    ("rate_limited", 429, ProviderError),
])
def test_map_sdk_exc_structured_code(code, status, expected):
    assert isinstance(_map_sdk_exc(_FakeAPIErr(code, status), op="op"), expected)


def test_block_to_markdown_video_external_with_caption(conv):
    """Audit #144: video block must render as a Markdown link, not be dropped."""
    block = {
        "type": "video",
        "video": {
            "external": {"url": "https://example.com/demo.mp4"},
            "caption": [{"type": "text", "text": {"content": "Demo clip"}}],
        },
    }
    out = conv._block_to_markdown(block)
    assert out == "[Demo clip](https://example.com/demo.mp4)\n\n"


def test_block_to_markdown_video_file_url_default_title(conv):
    """No caption → default title 'video' (English; legacy used Russian — we
    intentionally normalize to the same fallback string the image branch uses)."""
    block = {
        "type": "video",
        "video": {
            "file": {"url": "https://files.notion.so/v.mp4"},
            "caption": [],
        },
    }
    out = conv._block_to_markdown(block)
    assert out == "[video](https://files.notion.so/v.mp4)\n\n"


def test_iter_blocks_recursive_paginates_and_respects_depth(conv):
    calls = []
    pages = {
        ("root", None): {
            "results": [
                {
                    "id": "child-page",
                    "type": "child_page",
                    "has_children": True,
                    "child_page": {"title": "Child"},
                },
            ],
            "has_more": False,
            "next_cursor": None,
        },
        ("child-page", None): {
            "results": [
                {
                    "id": "db1",
                    "type": "child_database",
                    "has_children": False,
                    "child_database": {"title": "DB"},
                },
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


def test_iter_blocks_recursive_paginates_parent_after_child_walk(conv):
    calls = []
    pages = {
        ("root", None): {
            "results": [{"id": "child-page", "type": "child_page", "has_children": True}],
            "has_more": True,
            "next_cursor": "page-2",
        },
        ("child-page", None): {
            "results": [{"id": "grandchild", "type": "paragraph", "has_children": False}],
            "has_more": False,
            "next_cursor": None,
        },
        ("root", "page-2"): {
            "results": [{"id": "sibling", "type": "paragraph", "has_children": False}],
            "has_more": False,
            "next_cursor": None,
        },
    }

    def _page(block_id, start_cursor=None):
        calls.append((block_id, start_cursor))
        return pages[(block_id, start_cursor)]

    conv._list_block_children_page = _page

    rows = list(conv.iter_blocks_recursive("root", max_depth=2))

    assert [r["block"]["id"] for r in rows] == ["child-page", "grandchild", "sibling"]
    assert calls == [("root", None), ("child-page", None), ("root", "page-2")]


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
        "root": {
            "results": [
                {"id": "bad-child", "type": "child_page", "has_children": True},
                {"id": "sibling", "type": "paragraph", "has_children": False},
            ],
            "has_more": False,
            "next_cursor": None,
        },
    }

    def _page(block_id, start_cursor=None):
        if block_id == "bad-child":
            raise ProviderError("restricted")
        return pages[block_id]

    conv._list_block_children_page = _page

    rows = list(conv.iter_blocks_recursive("root", max_depth=2))

    assert [r["block"]["id"] for r in rows] == ["bad-child", "sibling"]
    assert conv._last_traversal_errors == [{"block_id": "bad-child", "error": "restricted"}]


def test_iter_blocks_recursive_root_listing_failure_raises(conv):
    def _page(block_id, start_cursor=None):
        raise ProviderError("root blocked")

    conv._list_block_children_page = _page

    with pytest.raises(ProviderError, match="root blocked"):
        list(conv.iter_blocks_recursive("root", max_depth=2))
    assert conv._last_traversal_errors == []


def test_iter_blocks_recursive_rejects_negative_args(conv):
    with pytest.raises(UsageError):
        list(conv.iter_blocks_recursive("root", max_depth=-1))
    with pytest.raises(UsageError):
        list(conv.iter_blocks_recursive("root", limit_blocks=-1))


def test_find_databases_recursive_collects_child_database_and_rows(conv):
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "db1",
                "type": "child_database",
                "child_database": {"title": "Tasks"},
                "parent": {"type": "page_id", "page_id": "root"},
                "last_edited_time": "2026-05-22T00:00:00Z",
            },
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
            "block": {
                "id": "ld1",
                "type": "linked_database",
                "linked_database": {"database_id": "db2"},
                "parent": {"type": "page_id", "page_id": "root"},
            },
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
        {
            "block": {
                "id": "db1",
                "type": "child_database",
                "child_database": {"title": "Tasks"},
            },
            "depth": 1,
            "path": [],
        },
    ])
    conv.query_database = lambda database_id, limit=None: pytest.fail("row_limit=0 must not query rows")

    result = conv.find_databases_on_page("root", recursive=True, with_rows=True, row_limit=0)

    assert result["databases"][0]["rows"] == []
    assert result["databases"][0]["row_count"] == 0
    assert result["stats"]["databases_queried"] == 0


def test_find_databases_with_rows_non_recursive_stays_shallow(conv):
    calls = []
    pages = {
        "root": {
            "results": [{"id": "child-page", "type": "child_page", "has_children": True}],
            "has_more": False,
            "next_cursor": None,
        },
        "child-page": {
            "results": [
                {
                    "id": "nested-db",
                    "type": "child_database",
                    "child_database": {"title": "Nested"},
                    "has_children": False,
                },
            ],
            "has_more": False,
            "next_cursor": None,
        },
    }

    def _page(block_id, start_cursor=None):
        calls.append(block_id)
        return pages[block_id]

    conv._list_block_children_page = _page
    conv.query_database = lambda database_id, limit=None: pytest.fail("nested database must not be discovered")

    result = conv.find_databases_on_page("root", recursive=False, with_rows=True, max_depth=3)

    assert calls == ["root"]
    assert result["recursive"] is False
    assert result["max_depth"] == 1
    assert result["databases"] == []


def test_find_databases_rejects_negative_row_limit(conv):
    with pytest.raises(UsageError):
        conv.find_databases_on_page("root", recursive=True, row_limit=-1)


def test_search_workspace_preserves_parent_shapes(conv):
    page = {
        "id": "page-1",
        "object": "page",
        "parent": {"type": "workspace"},
    }

    class _Client:
        def search(self, **kwargs):
            assert kwargs == {"filter": {"property": "object", "value": "page"}}
            return {"results": [page], "has_more": False, "next_cursor": None}

    conv.client = _Client()

    result = conv.search_workspace(object_type="page")

    assert result["kind"] == "notion_workspace_search/v1"
    assert result["results"][0]["parent"] == {"type": "workspace"}


def test_search_workspace_rejects_negative_limit(conv):
    with pytest.raises(UsageError):
        conv.search_workspace(object_type="page", limit=-1)


def test_search_workspace_zero_limit_returns_empty_without_search(conv):
    class _Client:
        def search(self, **kwargs):
            raise AssertionError("limit=0 must not call Notion search")

    conv.client = _Client()

    result = conv.search_workspace(object_type="page", limit=0)

    assert result["kind"] == "notion_workspace_search/v1"
    assert result["results"] == []
