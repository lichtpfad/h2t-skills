"""Tests for write_document_tab and _md_to_docs_requests — spec #206."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.connectors.drive.client import _md_to_docs_requests, _utf16_len
from h2t_ops.core.errors import UsageError


# ---------------------------------------------------------------------------
# _md_to_docs_requests unit tests
# ---------------------------------------------------------------------------

def test_empty_string_returns_empty_list():
    assert _md_to_docs_requests("", "t.abc") == []


def test_whitespace_only_returns_no_style_requests():
    reqs = _md_to_docs_requests("   \n\n  ", "t.abc")
    # insertText is still produced for the whitespace lines
    assert any("insertText" in r for r in reqs)
    assert not any("updateParagraphStyle" in r for r in reqs)
    assert not any("createParagraphBullets" in r for r in reqs)


def test_single_paragraph_produces_one_insert_no_style():
    reqs = _md_to_docs_requests("Hello world", "t.abc")
    assert len(reqs) == 1
    assert "insertText" in reqs[0]
    assert reqs[0]["insertText"]["text"] == "Hello world\n"
    assert reqs[0]["insertText"]["location"] == {"index": 1, "tabId": "t.abc"}


def test_heading1_produces_update_paragraph_style():
    reqs = _md_to_docs_requests("# My Heading", "t.xyz")
    inserts = [r for r in reqs if "insertText" in r]
    styles = [r for r in reqs if "updateParagraphStyle" in r]
    assert len(inserts) == 1
    assert inserts[0]["insertText"]["text"] == "My Heading\n"
    assert len(styles) == 1
    ps = styles[0]["updateParagraphStyle"]
    assert ps["paragraphStyle"]["namedStyleType"] == "HEADING_1"
    assert ps["range"]["tabId"] == "t.xyz"
    assert ps["range"]["startIndex"] == 1
    assert ps["range"]["endIndex"] == 1 + len("My Heading\n")


def test_heading2_named_style():
    reqs = _md_to_docs_requests("## Sub", "t.abc")
    styles = [r for r in reqs if "updateParagraphStyle" in r]
    assert styles[0]["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] == "HEADING_2"


def test_heading3_named_style():
    reqs = _md_to_docs_requests("### Deep", "t.abc")
    styles = [r for r in reqs if "updateParagraphStyle" in r]
    assert styles[0]["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] == "HEADING_3"


def test_bullet_produces_create_paragraph_bullets():
    reqs = _md_to_docs_requests("- Item one", "t.abc")
    bullets = [r for r in reqs if "createParagraphBullets" in r]
    assert len(bullets) == 1
    b = bullets[0]["createParagraphBullets"]
    assert b["bulletPreset"] == "BULLET_DISC_CIRCLE_SQUARE"
    assert b["range"]["tabId"] == "t.abc"
    assert b["range"]["startIndex"] == 1
    assert b["range"]["endIndex"] == 1 + len("Item one\n")


def test_asterisk_bullet_also_recognized():
    reqs = _md_to_docs_requests("* Item", "t.abc")
    bullets = [r for r in reqs if "createParagraphBullets" in r]
    assert len(bullets) == 1


def test_mixed_content_index_tracking():
    md = "# Title\nA paragraph\n- Bullet item"
    reqs = _md_to_docs_requests(md, "t.tab")
    inserts = [r for r in reqs if "insertText" in r]
    styles = [r for r in reqs if "updateParagraphStyle" in r]
    bullets = [r for r in reqs if "createParagraphBullets" in r]

    assert len(inserts) == 1
    assert inserts[0]["insertText"]["text"] == "Title\nA paragraph\nBullet item\n"

    # Title: indices 1 .. 1+len("Title\n")=7
    assert styles[0]["updateParagraphStyle"]["range"]["startIndex"] == 1
    assert styles[0]["updateParagraphStyle"]["range"]["endIndex"] == 7

    # "A paragraph\n" starts at 7, ends at 7+12=19
    # "Bullet item\n" starts at 19, ends at 19+12=31
    assert bullets[0]["createParagraphBullets"]["range"]["startIndex"] == 19
    assert bullets[0]["createParagraphBullets"]["range"]["endIndex"] == 31


def test_single_inserttext_for_entire_content():
    md = "# H\nPara\n- B1\n- B2"
    reqs = _md_to_docs_requests(md, "t.abc")
    inserts = [r for r in reqs if "insertText" in r]
    assert len(inserts) == 1


def test_tab_id_propagated_to_all_requests():
    md = "# H\n- B"
    tab_id = "t.unique123"
    reqs = _md_to_docs_requests(md, tab_id)
    for r in reqs:
        if "insertText" in r:
            assert r["insertText"]["location"]["tabId"] == tab_id
        if "updateParagraphStyle" in r:
            assert r["updateParagraphStyle"]["range"]["tabId"] == tab_id
        if "createParagraphBullets" in r:
            assert r["createParagraphBullets"]["range"]["tabId"] == tab_id


# ---------------------------------------------------------------------------
# write_document_tab method tests
# ---------------------------------------------------------------------------

@pytest.fixture
def dc():
    from h2t_ops.connectors.drive.client import DriveClient
    c = object.__new__(DriveClient)
    c.service = MagicMock()
    c._docs_service = MagicMock()
    c._creds = "creds"
    return c


def _empty_tab_doc(doc_id: str, tab_id: str, revision: str = "rev42") -> dict:
    return {
        "documentId": doc_id,
        "revisionId": revision,
        "tabs": [{
            "tabProperties": {"tabId": tab_id},
            "documentTab": {
                "body": {
                    "content": [{"endIndex": 1}],
                }
            },
        }],
    }


def _setup_doc(dc, doc_id="docid1", tab_id="t.tab1", revision="rev42"):
    dc.service.files.return_value.get.return_value.execute.return_value = {
        "id": doc_id,
        "name": "Test Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    dc._docs_service.documents.return_value.get.return_value.execute.return_value = (
        _empty_tab_doc(doc_id, tab_id, revision)
    )
    dc._docs_service.documents.return_value.batchUpdate.return_value.execute.return_value = {
        "writeControl": {"requiredRevisionId": revision}
    }


def test_write_tab_calls_batch_update(dc):
    _setup_doc(dc, tab_id="t.tab1")
    result = dc.write_document_tab("docid1", "t.tab1", "# Hello\nWorld")
    assert dc._docs_service.documents.return_value.batchUpdate.called
    assert result["kind"] == "google_docs_tab_write/v1"
    assert result["document_id"] == "docid1"
    assert result["tab_id"] == "t.tab1"
    assert result["requests_sent"] > 0


def test_write_tab_empty_content_skips_batch_update(dc):
    _setup_doc(dc, tab_id="t.tab1")
    result = dc.write_document_tab("docid1", "t.tab1", "")
    assert not dc._docs_service.documents.return_value.batchUpdate.called
    assert result["requests_sent"] == 0


def test_write_tab_non_doc_raises_usage_error(dc):
    dc.service.files.return_value.get.return_value.execute.return_value = {
        "id": "fid",
        "name": "sheet.xlsx",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    with pytest.raises(UsageError, match="not a Google Docs editor file"):
        dc.write_document_tab("fid", "t.tab1", "# Hello")


def test_write_tab_returns_revision_id(dc):
    _setup_doc(dc, tab_id="t.tab1")
    result = dc.write_document_tab("docid1", "t.tab1", "# Title")
    assert result["revision_id"] == "rev42"


def test_write_tab_batch_update_body_contains_insert_and_style(dc):
    _setup_doc(dc, tab_id="t.tab1")
    dc.write_document_tab("docid1", "t.tab1", "# Head\nParagraph")
    call_body = dc._docs_service.documents.return_value.batchUpdate.call_args.kwargs["body"]
    requests = call_body["requests"]
    has_insert = any("insertText" in r for r in requests)
    has_style = any("updateParagraphStyle" in r for r in requests)
    assert has_insert
    assert has_style


def test_write_tab_sends_write_control(dc):
    """batchUpdate body must include writeControl.requiredRevisionId."""
    _setup_doc(dc, tab_id="t.tab1", revision="rev99")
    dc.write_document_tab("docid1", "t.tab1", "# Hello")
    call_body = dc._docs_service.documents.return_value.batchUpdate.call_args.kwargs["body"]
    assert call_body["writeControl"] == {"requiredRevisionId": "rev99"}


def test_write_tab_non_empty_raises_usage_error(dc):
    """write_document_tab rejects tabs with endIndex > 1 (already has content)."""
    _setup_doc(dc, tab_id="t.tab1")
    dc._docs_service.documents.return_value.get.return_value.execute.return_value = {
        "documentId": "docid1",
        "revisionId": "rev1",
        "tabs": [{
            "tabProperties": {"tabId": "t.tab1"},
            "documentTab": {"body": {"content": [{"endIndex": 42}]}},
        }],
    }
    with pytest.raises(UsageError, match="not empty"):
        dc.write_document_tab("docid1", "t.tab1", "# Hello")


def test_write_tab_missing_tab_raises_usage_error(dc):
    """write_document_tab raises when the tab_id is not found in document tabs."""
    _setup_doc(dc, tab_id="t.other")
    with pytest.raises(UsageError, match="not found"):
        dc.write_document_tab("docid1", "t.tab1", "# Hello")


# ---------------------------------------------------------------------------
# UTF-16 offset correctness
# ---------------------------------------------------------------------------

def test_utf16_len_ascii():
    assert _utf16_len("Hello") == 5


def test_utf16_len_emoji():
    # 🎉 is U+1F389, a supplementary character → 2 UTF-16 units
    assert _utf16_len("🎉") == 2


def test_emoji_before_heading_correct_offset():
    """Emoji in preceding paragraph must not shift heading style range."""
    md = "🎉 Party\n# Title"
    reqs = _md_to_docs_requests(md, "t.abc")
    styles = [r for r in reqs if "updateParagraphStyle" in r]
    assert len(styles) == 1
    # "🎉 Party\n" = _utf16_len("🎉 Party") + 1 = (2+1+5) + 1 = 9 units
    # heading starts at 1 + 9 = 10
    emoji_para_len = _utf16_len("🎉 Party") + 1
    assert styles[0]["updateParagraphStyle"]["range"]["startIndex"] == 1 + emoji_para_len


def test_emoji_before_bullet_correct_offset():
    """Emoji in preceding text must not shift bullet range."""
    md = "🎉 intro\n- item"
    reqs = _md_to_docs_requests(md, "t.abc")
    bullets = [r for r in reqs if "createParagraphBullets" in r]
    assert len(bullets) == 1
    emoji_para_len = _utf16_len("🎉 intro") + 1
    assert bullets[0]["createParagraphBullets"]["range"]["startIndex"] == 1 + emoji_para_len
