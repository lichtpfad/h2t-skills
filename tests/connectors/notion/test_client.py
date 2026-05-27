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


# --- Comments ---

def test_rich_text_to_plain_concatenates_content(conv):
    rich = [
        {"type": "text", "text": {"content": "Hello "}},
        {"type": "text", "text": {"content": "world"}},
    ]
    assert conv._rich_text_to_plain(rich) == "Hello world"


def test_rich_text_to_plain_empty(conv):
    assert conv._rich_text_to_plain([]) == ""


def test_list_comments_returns_normalized(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.comments.list.return_value = {
        "results": [
            {
                "id": "c1",
                "rich_text": [{"type": "text", "text": {"content": "Nice page"}}],
                "created_time": "2026-05-25T10:00:00.000Z",
                "created_by": {"id": "user1"},
            }
        ],
        "has_more": False,
    }
    result = conv.list_comments("page1")
    assert result == [
        {"id": "c1", "text": "Nice page", "created_time": "2026-05-25T10:00:00.000Z", "created_by_id": "user1"}
    ]


def test_list_comments_auto_paginates(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.comments.list.side_effect = [
        {"results": [{"id": "c1", "rich_text": [], "created_time": "", "created_by": {"id": "u"}}],
         "has_more": True, "next_cursor": "cur1"},
        {"results": [{"id": "c2", "rich_text": [], "created_time": "", "created_by": {"id": "u"}}],
         "has_more": False},
    ]
    result = conv.list_comments("page1")
    assert [r["id"] for r in result] == ["c1", "c2"]
    assert conv.client.comments.list.call_count == 2
    second_call_kwargs = conv.client.comments.list.call_args_list[1].kwargs
    assert second_call_kwargs["start_cursor"] == "cur1"


def test_list_comments_empty(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.comments.list.return_value = {"results": [], "has_more": False}
    assert conv.list_comments("page1") == []


def test_list_comments_maps_sdk_exc(conv):
    from unittest.mock import MagicMock
    from h2t_ops.core.errors import ProviderError
    conv.client = MagicMock()
    conv.client.comments.list.side_effect = RuntimeError("boom")
    with pytest.raises(ProviderError):
        conv.list_comments("page1")


def test_create_comment_wraps_text_in_rich_text(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.comments.create.return_value = {
        "id": "c1",
        "rich_text": [{"type": "text", "text": {"content": "Hello"}}],
        "created_time": "2026-05-25T10:00:00.000Z",
        "created_by": {"id": "user1"},
    }
    result = conv.create_comment("page1", "Hello")
    kw = conv.client.comments.create.call_args.kwargs
    assert kw["parent"] == {"page_id": "page1"}
    assert kw["rich_text"] == [{"type": "text", "text": {"content": "Hello"}}]
    assert result["text"] == "Hello"
    assert result["created_by_id"] == "user1"


def test_create_comment_maps_sdk_exc(conv):
    from unittest.mock import MagicMock
    from h2t_ops.core.errors import ProviderError
    conv.client = MagicMock()
    conv.client.comments.create.side_effect = RuntimeError("boom")
    with pytest.raises(ProviderError):
        conv.create_comment("page1", "Hello")


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


def test_search_workspace_database_alias_uses_data_source_filter(conv):
    data_source = {
        "id": "db-1",
        "object": "data_source",
        "parent": {"type": "page_id", "page_id": "page-1"},
    }

    class _Client:
        def search(self, **kwargs):
            assert kwargs == {"filter": {"property": "object", "value": "data_source"}}
            return {"results": [data_source], "has_more": False, "next_cursor": None}

    conv.client = _Client()

    result = conv.search_workspace(object_type="database")

    assert result["object"] == "database"
    assert result["results"][0]["object"] == "data_source"
    assert result["results"][0]["parent"] == {"type": "page_id", "page_id": "page-1"}


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


def test_graph_page_returns_nodes_edges_and_maps(conv):
    conv.get_page = lambda page_id: {
        "id": page_id,
        "object": "page",
        "parent": {"type": "workspace"},
        "url": "https://notion.so/root",
        "created_time": "c",
        "last_edited_time": "m",
        "properties": {"title": {"type": "title", "title": [{"type": "text", "text": {"content": "Root"}}]}},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "b1",
                "type": "paragraph",
                "parent": {"type": "page_id", "page_id": "root"},
                "created_time": "c",
                "last_edited_time": "m",
            },
            "depth": 1,
            "path": ["Root"],
        },
        {
            "block": {
                "id": "db1",
                "type": "child_database",
                "parent": {"type": "page_id", "page_id": "root"},
                "child_database": {"title": "Tasks"},
                "created_time": "c",
                "last_edited_time": "m",
            },
            "depth": 1,
            "path": ["Root"],
        },
    ])

    result = conv.graph_page("root", max_depth=2)

    assert result["kind"] == "notion_workspace_graph/v1"
    assert result["parent_map"]["b1"] == "root"
    assert result["parent_map"]["db1"] == "root"
    assert result["children_map"]["root"] == ["b1", "db1"]
    assert result["edges"] == [
        {"from": "root", "to": "b1", "relation": "contains"},
        {"from": "root", "to": "db1", "relation": "contains"},
    ]
    assert result["nodes"][0]["source_ref"] == "notion:page:root"
    assert result["nodes"][1]["source_ref"] == "notion:block:b1"
    assert result["nodes"][2]["source_ref"] == "notion:database:db1"
    assert result["nodes"][1]["parent"] == {"type": "page_id", "page_id": "root"}
    assert result["nodes"][1]["parent_chain"] == ["root", "Root"]


def test_graph_page_uses_canonical_root_id_for_edges_and_maps(conv):
    conv.get_page = lambda page_id: {
        "id": "canonical",
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "child",
                "type": "paragraph",
                "parent": {"type": "page_id", "page_id": "canonical"},
            },
            "depth": 1,
            "path": [],
        },
    ])

    result = conv.graph_page("compact")

    assert result["root_page_id"] == "canonical"
    assert result["requested_root_page_id"] == "compact"
    assert result["nodes"][0]["id"] == "canonical"
    assert result["nodes"][0]["source_ref"] == "notion:page:canonical"
    assert result["children_map"]["canonical"] == ["child"]
    assert result["parent_map"]["child"] == "canonical"
    assert result["nodes"][1]["parent_chain"] == ["canonical"]


def test_graph_block_parent_owner_chain_uses_retrieve_block(conv):
    conv.get_page = lambda page_id: {
        "id": "root",
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    conv.get_block = lambda block_id: {
        "id": "owner",
        "type": "paragraph",
        "parent": {"type": "page_id", "page_id": "root"},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "nested",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
    ])

    result = conv.graph_page("root")

    assert result["parent_map"]["nested"] == "owner"
    assert result["owner_map"]["nested"]["owner_block_id"] == "owner"
    assert result["owner_map"]["nested"]["owner_page_id"] == "root"
    assert result["owner_map"]["nested"]["chain"] == ["owner"]
    assert result["owner_map"]["nested"]["source_refs"] == ["notion:block:owner"]
    assert result["owner_map"]["nested"]["owner_page_source_ref"] == "notion:page:root"


def test_graph_block_parent_owner_chain_caches_shared_parent_lookup(conv):
    conv.get_page = lambda page_id: {
        "id": "root",
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    calls = []

    def _get_block(block_id):
        calls.append(block_id)
        return {
            "id": block_id,
            "type": "paragraph",
            "parent": {"type": "page_id", "page_id": "root"},
        }

    conv.get_block = _get_block
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "nested-a",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
        {
            "block": {
                "id": "nested-b",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
    ])

    result = conv.graph_page("root")

    assert calls == ["owner"]
    assert result["owner_map"]["nested-a"]["owner_page_id"] == "root"
    assert result["owner_map"]["nested-b"]["owner_page_id"] == "root"
    assert result["owner_map"]["nested-a"]["chain"] == ["owner"]
    assert result["owner_map"]["nested-b"]["chain"] == ["owner"]


def test_graph_block_parent_owner_resolution_error_keeps_node(conv):
    conv.get_page = lambda page_id: {
        "id": "root",
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }

    def _blocked(block_id):
        raise ProviderError("restricted owner")

    conv.get_block = _blocked
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "nested",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
    ])

    result = conv.graph_page("root")

    assert [node["id"] for node in result["nodes"]] == ["root", "nested"]
    assert result["parent_map"]["nested"] == "owner"
    assert result["owner_map"]["nested"]["owner_block_id"] == "owner"
    assert result["owner_map"]["nested"]["owner_page_id"] is None
    assert result["owner_map"]["nested"]["error"] == "restricted owner"
    assert result["owner_map"]["nested"]["error_type"] == "ProviderError"
    assert result["errors"] == [
        {
            "block_id": "nested",
            "owner_block_id": "owner",
            "error": "restricted owner",
            "error_type": "ProviderError",
        }
    ]


def test_graph_block_parent_owner_resolution_error_caches_shared_parent_lookup(conv):
    conv.get_page = lambda page_id: {
        "id": "root",
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    calls = []

    def _blocked(block_id):
        calls.append(block_id)
        raise ProviderError("restricted owner")

    conv.get_block = _blocked
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "nested-a",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
        {
            "block": {
                "id": "nested-b",
                "type": "paragraph",
                "parent": {"type": "block_id", "block_id": "owner"},
            },
            "depth": 2,
            "path": [],
        },
    ])

    result = conv.graph_page("root")

    assert calls == ["owner"]
    assert result["owner_map"]["nested-a"]["error"] == "restricted owner"
    assert result["owner_map"]["nested-b"]["error"] == "restricted owner"
    assert result["owner_map"]["nested-a"]["error_type"] == "ProviderError"
    assert result["owner_map"]["nested-b"]["error_type"] == "ProviderError"
    assert result["errors"] == [
        {
            "block_id": "nested-a",
            "owner_block_id": "owner",
            "error": "restricted owner",
            "error_type": "ProviderError",
        },
        {
            "block_id": "nested-b",
            "owner_block_id": "owner",
            "error": "restricted owner",
            "error_type": "ProviderError",
        },
    ]


def test_graph_page_can_exclude_child_databases(conv):
    conv.get_page = lambda page_id: {
        "id": page_id,
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([
        {
            "block": {
                "id": "db1",
                "type": "child_database",
                "parent": {"type": "page_id", "page_id": "root"},
                "child_database": {"title": "Tasks"},
            },
            "depth": 1,
            "path": [],
        },
        {
            "block": {
                "id": "b1",
                "type": "paragraph",
                "parent": {"type": "page_id", "page_id": "root"},
            },
            "depth": 1,
            "path": [],
        },
    ])

    result = conv.graph_page("root", include_databases=False)

    assert [node["id"] for node in result["nodes"]] == ["root", "b1"]
    assert result["children_map"]["root"] == ["b1"]
    assert "db1" not in result["parent_map"]


def test_graph_page_includes_traversal_permission_errors(conv):
    conv.get_page = lambda page_id: {
        "id": page_id,
        "object": "page",
        "parent": {"type": "workspace"},
        "properties": {},
    }
    conv.iter_blocks_recursive = lambda page_id, max_depth=3, limit_blocks=None: iter([])
    conv._last_traversal_errors = [{"block_id": "restricted", "error": "blocked"}]

    result = conv.graph_page("root")

    assert result["errors"] == [{"block_id": "restricted", "error": "blocked"}]


# --- P0 lifecycle client unit tests ---

def test_create_db_item_builds_title_property(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.pages.create.return_value = {"id": "new-page", "object": "page"}
    result = conv.create_db_item("db1", title="My Task")
    call_kwargs = conv.client.pages.create.call_args.kwargs
    assert call_kwargs["parent"] == {"database_id": "db1"}
    assert "Name" in call_kwargs["properties"]
    assert call_kwargs["properties"]["Name"]["title"][0]["text"]["content"] == "My Task"
    assert result["id"] == "new-page"


def test_create_db_item_does_not_override_existing_title_property(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.pages.create.return_value = {"id": "new-page"}
    prop_json = '{"Name": {"title": [{"text": {"content": "Custom"}}]}}'
    conv.create_db_item("db1", title="Ignored", property_json=prop_json)
    call_kwargs = conv.client.pages.create.call_args.kwargs
    # Name was already in property_json, should use custom value
    assert call_kwargs["properties"]["Name"]["title"][0]["text"]["content"] == "Custom"


def test_update_db_item_passes_properties_json(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.pages.update.return_value = {"id": "page1"}
    result = conv.update_db_item("page1", property_json='{"Status":{"select":{"name":"Done"}}}')
    call_kwargs = conv.client.pages.update.call_args.kwargs
    assert call_kwargs["page_id"] == "page1"
    assert call_kwargs["properties"] == {"Status": {"select": {"name": "Done"}}}
    assert result["id"] == "page1"


def test_archive_confirms_title_before_update(conv):
    from unittest.mock import MagicMock
    conv.client = MagicMock()
    conv.client.pages.retrieve.return_value = {
        "id": "page1",
        "properties": {"Name": {"type": "title", "title": [{"type": "text", "text": {"content": "My Task"}}]}},
    }
    conv.client.pages.update.return_value = {"id": "page1", "archived": True}
    result = conv.archive_page("page1", confirm_title="My Task")
    assert conv.client.pages.update.called
    update_kwargs = conv.client.pages.update.call_args.kwargs
    assert update_kwargs["archived"] is True


def test_archive_mismatch_raises_usageerror_before_update(conv):
    from unittest.mock import MagicMock
    from h2t_ops.core.errors import UsageError
    conv.client = MagicMock()
    conv.client.pages.retrieve.return_value = {
        "id": "page1",
        "properties": {"Name": {"type": "title", "title": [{"type": "text", "text": {"content": "Real Title"}}]}},
    }
    with pytest.raises(UsageError, match="mismatch"):
        conv.archive_page("page1", confirm_title="Wrong Title")
    assert not conv.client.pages.update.called


def test_append_blocks_uses_blocks_children_append(conv, tmp_path):
    from unittest.mock import MagicMock
    md_file = tmp_path / "content.md"
    md_file.write_text("# Hello\n\nWorld.\n", encoding="utf-8")
    conv.client = MagicMock()
    conv.client.blocks.children.append.return_value = {"results": []}
    conv.append_blocks_from_file("page1", str(md_file))
    assert conv.client.blocks.children.append.called
    call_kwargs = conv.client.blocks.children.append.call_args.kwargs
    assert call_kwargs["block_id"] == "page1"
    assert any(b["type"] == "heading_1" for b in call_kwargs["children"])


def test_replace_content_deletes_existing_blocks_then_appends(conv, tmp_path):
    from unittest.mock import MagicMock, call
    md_file = tmp_path / "content.md"
    md_file.write_text("New content.\n", encoding="utf-8")
    conv.client = MagicMock()
    conv.client.pages.retrieve.return_value = {
        "id": "page1",
        "properties": {"Name": {"type": "title", "title": [{"type": "text", "text": {"content": "Page Title"}}]}},
    }
    conv.client.blocks.children.list.return_value = {
        "results": [{"id": "b1"}, {"id": "b2"}], "has_more": False
    }
    conv.client.blocks.delete.return_value = {}
    conv.client.blocks.children.append.return_value = {"results": []}
    conv.replace_page_content_safe("page1", str(md_file), confirm_title="Page Title")
    # Verify delete was called for existing blocks
    assert conv.client.blocks.delete.call_count == 2
    assert conv.client.blocks.children.append.called


def test_replace_content_mismatch_raises_before_delete(conv, tmp_path):
    from unittest.mock import MagicMock
    from h2t_ops.core.errors import UsageError
    md_file = tmp_path / "content.md"
    md_file.write_text("Replacement.\n", encoding="utf-8")
    conv.client = MagicMock()
    conv.client.pages.retrieve.return_value = {
        "id": "page1",
        "properties": {"Name": {"type": "title", "title": [{"type": "text", "text": {"content": "Actual Title"}}]}},
    }
    with pytest.raises(UsageError, match="mismatch"):
        conv.replace_page_content_safe("page1", str(md_file), confirm_title="Wrong Title")
    # CRITICAL: blocks.delete must NOT have been called
    assert not conv.client.blocks.delete.called
    assert not conv.client.blocks.children.list.called
