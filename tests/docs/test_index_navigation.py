"""Tests for docs-index navigation template output."""
import sys
from pathlib import Path

_INDEX_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-index/scripts"
sys.path.insert(0, str(_INDEX_DIR))
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from index import build_navigation_index


def test_build_navigation_index_has_repo_title(tmp_path):
    """Output starts with # {repo} Documentation."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "h2t-skills")
    assert "# h2t-skills Documentation" in result


def test_build_navigation_index_has_quick_links(tmp_path):
    """Quick Links section present when superpowers/ exists with content."""
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-01-01-test.md").write_text("# Test\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Quick Links" in result


def test_build_navigation_index_adr_section_has_link(tmp_path):
    """ADR table row contains markdown link to the file."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-use-python.md").write_text(
        "---\nstatus: accepted\ndate: 2026-01-01\n---\n# Use Python\n"
    )
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Architecture Decisions" in result
    assert "[Use Python](adr/0001-use-python.md)" in result


def test_build_navigation_index_adr_number_from_num_field(tmp_path):
    """ADR row uses 'num' field (not 'number') — correct schema from _collect_adrs."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0042-some-decision.md").write_text(
        "---\nstatus: proposed\ndate: 2026-03-01\n---\n# Some Decision\n"
    )
    result = build_navigation_index(tmp_path, "my-repo")
    assert "42" in result  # num strips leading zeros: "0042" -> "42"


def test_build_navigation_index_no_adr_section_when_absent(tmp_path):
    """No ADR section when docs/adr/ does not exist."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Architecture Decisions" not in result


def test_build_navigation_index_no_quick_links_when_no_sections(tmp_path):
    """No Quick Links table when no standard subdirs exist."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Quick Links" not in result


def test_build_navigation_index_includes_research_dir_in_quick_links(tmp_path):
    """docs/research/ dir with content must appear in Quick Links."""
    research_dir = tmp_path / "docs" / "research"
    research_dir.mkdir(parents=True)
    (research_dir / "2026-06-01-analysis.md").write_text("# Analysis\n")

    result = build_navigation_index(tmp_path, "my-repo")

    assert "## Quick Links" in result
    assert "research" in result.lower()


def test_build_navigation_index_includes_unknown_dir_in_quick_links(tmp_path):
    """Any docs/ subdir with .md files appears in Quick Links, even if not in known list."""
    custom_dir = tmp_path / "docs" / "custom-section"
    custom_dir.mkdir(parents=True)
    (custom_dir / "notes.md").write_text("# Notes\n")

    result = build_navigation_index(tmp_path, "my-repo")

    assert "custom-section" in result


def test_build_navigation_index_excludes_empty_dirs_from_quick_links(tmp_path):
    """Dirs with no .md files do not appear in Quick Links."""
    empty_dir = tmp_path / "docs" / "empty-section"
    empty_dir.mkdir(parents=True)

    result = build_navigation_index(tmp_path, "my-repo")

    assert "empty-section" not in result


def test_build_navigation_index_excludes_adr_from_quick_links(tmp_path):
    """adr/ has its own table — must not also appear in Quick Links."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-test.md").write_text("# Test\n")

    result = build_navigation_index(tmp_path, "my-repo")

    # ADR appears in Architecture Decisions table, not Quick Links
    assert "## Architecture Decisions" in result
    # No Quick Links row pointing to adr/
    assert not any("[adr]" in line.lower() for line in result.splitlines())


def test_nested_section_files_are_linked(tmp_path):
    """A doc one level below a section dir gets its own link, not a dead-end dir link."""
    nested = tmp_path / "docs" / "architecture" / "h2t-creative"
    nested.mkdir(parents=True)
    (nested / "rendering.md").write_text("# Rendering\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "(architecture/h2t-creative/rendering.md)" in result


def test_loose_root_docs_are_linked(tmp_path):
    """Markdown sitting directly in docs/ is linked; only README.md is skipped."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "roadmap.md").write_text("# Roadmap\n")
    (docs / "README.md").write_text("# Index\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "(roadmap.md)" in result
    assert "(README.md)" not in result


def test_superpowers_references_are_linked(tmp_path):
    """superpowers/ has dedicated specs+plans tables; references/ must not fall through."""
    refs = tmp_path / "docs" / "superpowers" / "references"
    refs.mkdir(parents=True)
    (refs / "prior-art.md").write_text("# Prior Art\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "(superpowers/references/prior-art.md)" in result


def test_excluded_dirs_are_not_linked(tmp_path):
    """A frozen tree stays out of the index — linking it is what archiving undid."""
    arch = tmp_path / "docs" / "archive"
    arch.mkdir(parents=True)
    (arch / "old.md").write_text("# Old\n")
    result = build_navigation_index(tmp_path, "my-repo", exclude_dirs=["docs/archive"])
    assert "archive/old.md" not in result


def test_nested_readme_is_linked_but_not_the_index_itself(tmp_path):
    """A nested README is a subtree entry point; docs/README.md is the index, not an entry."""
    sub = tmp_path / "docs" / "wireframes"
    sub.mkdir(parents=True)
    (sub / "README.md").write_text("# Wireframes\n")
    (tmp_path / "docs" / "README.md").write_text("# Index\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "(wireframes/README.md)" in result
    assert "](README.md)" not in result


def test_adr_index_file_is_linked(tmp_path):
    """adr/index.md does not match the ADR glob [0-9]*.md — link it explicitly."""
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "0001-a.md").write_text("---\nstatus: accepted\n---\n# A\n")
    (adr / "index.md").write_text("# ADR Index\n")
    result = build_navigation_index(tmp_path, "my-repo")
    assert "(adr/index.md)" in result
