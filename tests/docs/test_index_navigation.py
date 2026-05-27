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
    """Quick Links section present when superpowers/ exists."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
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
