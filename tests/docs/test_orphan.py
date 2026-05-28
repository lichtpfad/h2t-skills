# tests/docs/test_orphan.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.orphan import find_orphan_files


def test_no_docs_dir_no_findings(tmp_path):
    """No docs/ dir → no findings."""
    assert find_orphan_files(tmp_path) == []


def test_readme_itself_not_orphan(tmp_path):
    """docs/README.md is the BFS root — never flagged as orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n")
    results = find_orphan_files(tmp_path)
    assert not any("README.md" in r["path"] for r in results)


def test_linked_file_not_orphan(tmp_path):
    """File linked from README.md → not an orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Guide](guide.md)\n")
    (docs / "guide.md").write_text("# Guide\n")
    results = find_orphan_files(tmp_path)
    assert not any("guide.md" in r["path"] for r in results)


def test_unlinked_file_is_orphan(tmp_path):
    """File not linked from README.md → orphan finding."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n")
    (docs / "stale.md").write_text("# Stale\n")
    results = find_orphan_files(tmp_path)
    assert len(results) == 1
    assert "stale.md" in results[0]["path"]
    assert results[0]["type"] == "orphan"
    assert results[0]["severity"] == "warn"


def test_transitive_link_not_orphan(tmp_path):
    """File reachable via chain README → section/README → deep → not orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Section](section/README.md)\n")
    section = docs / "section"
    section.mkdir()
    (section / "README.md").write_text("# Section\n\n[Deep](deep.md)\n")
    (section / "deep.md").write_text("# Deep\n")
    results = find_orphan_files(tmp_path)
    assert not any("deep.md" in r["path"] for r in results)
    assert not any("section/README.md" in r["path"] for r in results)


def test_missing_readme_all_files_flagged(tmp_path):
    """No docs/README.md → all docs files are orphans (unreachable)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# Page\n")
    results = find_orphan_files(tmp_path)
    assert len(results) == 1
    assert "page.md" in results[0]["path"]


def test_http_links_not_followed(tmp_path):
    """External http links are skipped — no false positives."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Docs\n\n[External](https://example.com/page.md)\n"
    )
    (docs / "local.md").write_text("# Local\n")
    results = find_orphan_files(tmp_path)
    assert any("local.md" in r["path"] for r in results)


def test_fragment_links_resolved_correctly(tmp_path):
    """Links with #anchor are resolved to the file (anchor stripped)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Docs\n\n[Guide](guide.md#section)\n"
    )
    (docs / "guide.md").write_text("# Guide\n")
    results = find_orphan_files(tmp_path)
    assert not any("guide.md" in r["path"] for r in results)


def test_traversal_outside_docs_blocked(tmp_path):
    """Links pointing to ../outside.md (outside docs/) are not followed."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Outside](../outside.md)\n")
    (tmp_path / "outside.md").write_text("# Outside\n")
    results = find_orphan_files(tmp_path)
    assert not any("outside.md" in r["path"] for r in results)


def test_links_within_docs_subdir_followed(tmp_path):
    """Links into docs subdirs are still followed correctly."""
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    (docs / "README.md").write_text("# Docs\n\n[Page](sub/page.md)\n")
    (docs / "sub" / "page.md").write_text("# Page\n")
    results = find_orphan_files(tmp_path)
    assert not any("page.md" in r["path"] for r in results)
