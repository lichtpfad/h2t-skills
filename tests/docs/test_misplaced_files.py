# tests/docs/test_misplaced_files.py
"""Unit tests for docs.misplaced_files module."""
import sys
from pathlib import Path
from unittest.mock import patch

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.misplaced_files import check_misplaced_deliverables


def test_no_docs_dir_returns_empty(tmp_path):
    result = check_misplaced_deliverables(tmp_path)
    assert result == []


def test_only_md_files_no_findings(tmp_path):
    docs = tmp_path / "docs" / "research"
    docs.mkdir(parents=True)
    (docs / "2026-01-01-analysis.md").write_text("# Analysis")
    result = check_misplaced_deliverables(tmp_path)
    assert result == []


def test_html_in_docs_produces_finding(tmp_path):
    docs = tmp_path / "docs" / "research"
    docs.mkdir(parents=True)
    (docs / "report.html").write_text("<html></html>")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1
    assert result[0]["type"] == "misplaced_deliverable"
    assert result[0]["severity"] == "warn"
    assert "docs/research/report.html" in result[0]["path"]
    assert result[0]["target_path"] == "deliverables/report.html"
    assert result[0]["is_tracked"] is True


def test_pdf_in_docs_produces_finding(tmp_path):
    docs = tmp_path / "docs" / "client"
    docs.mkdir(parents=True)
    (docs / "proposal.pdf").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=False):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1
    assert result[0]["is_tracked"] is False


def test_custom_deliverables_dir_in_target_path(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "deck.pptx").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path, deliverables_dir="outputs")
    assert result[0]["target_path"] == "outputs/deck.pptx"


def test_multiple_deliverable_exts_detected(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("a.html", "b.pdf", "c.pptx", "d.docx"):
        (docs / name).write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 4


def test_htm_extension_detected(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.htm").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1


def test_readme_md_not_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs")
    result = check_misplaced_deliverables(tmp_path)
    assert result == []
