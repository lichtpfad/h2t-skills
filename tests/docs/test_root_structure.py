"""Unit tests for docs.root_structure module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.root_structure import (
    STANDARD_ALLOWLIST,  # noqa: F401
    check_root_readmes,
    check_root_structure,
)

# --- check_root_structure ---

def test_allowlist_items_not_flagged(tmp_path):
    """Standard items (README.md, pyproject.toml, .gitignore, docs/) are not flagged."""
    (tmp_path / "README.md").write_text("")
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / ".gitignore").write_text("")
    (tmp_path / "docs").mkdir()
    result = check_root_structure(tmp_path)
    assert result == [], f"Standard items should not produce findings: {result}"


def test_template_root_dirs_not_flagged(tmp_path):
    """Dirs from template spec (code_repo: src, tests) are not flagged."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    result = check_root_structure(tmp_path, template="code_repo")
    paths = [f["path"] for f in result]
    assert "src/" not in paths
    assert "tests/" not in paths


def test_custom_root_dirs_not_flagged(tmp_path):
    """custom_root_dirs items are not flagged."""
    (tmp_path / "nimbalyst-local").mkdir()
    result = check_root_structure(tmp_path, custom_root_dirs=["nimbalyst-local"])
    paths = [f["path"] for f in result]
    assert "nimbalyst-local/" not in paths


def test_temp_file_at_root_flagged_as_warn(tmp_path):
    """Files matching TEMP_PATTERNS get severity=warn finding."""
    (tmp_path / "session_analysis.txt").write_text("")
    result = check_root_structure(tmp_path)
    assert len(result) == 1
    assert result[0]["severity"] == "warn"
    assert "temp file" in result[0]["message"]
    assert result[0]["path"] == "session_analysis.txt"


def test_tmp_file_flagged_as_warn(tmp_path):
    """*.tmp file at root → warn finding."""
    (tmp_path / "scratch.tmp").write_text("")
    result = check_root_structure(tmp_path)
    assert any(f["severity"] == "warn" and "scratch.tmp" in f["path"] for f in result)


def test_unknown_item_flagged_as_info(tmp_path):
    """Unknown item not matching any pattern → severity=info finding."""
    (tmp_path / "my-weird-dir").mkdir()
    result = check_root_structure(tmp_path)
    assert len(result) == 1
    assert result[0]["severity"] == "info"
    assert "unknown root item" in result[0]["message"]
    assert "custom_root_dirs" in result[0]["message"]


def test_git_dir_skipped(tmp_path):
    """.git dir is silently skipped."""
    (tmp_path / ".git").mkdir()
    result = check_root_structure(tmp_path)
    assert result == []


def test_venv_dir_skipped(tmp_path):
    """.venv dir is silently skipped."""
    (tmp_path / ".venv").mkdir()
    result = check_root_structure(tmp_path)
    assert result == []


def test_empty_root_no_findings(tmp_path):
    """Completely empty root → no findings."""
    result = check_root_structure(tmp_path)
    assert result == []


def test_finding_type_is_root_structure(tmp_path):
    """Unknown item findings have type='root_structure'."""
    (tmp_path / "mystery-folder").mkdir()
    result = check_root_structure(tmp_path)
    assert all(f["type"] == "root_structure" for f in result)


# --- check_root_readmes ---

def test_root_readmes_present_no_findings(tmp_path):
    """All template root dirs have README.md → no findings."""
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
        (tmp_path / d / "README.md").write_text("")
    result = check_root_readmes(tmp_path, "code_repo")
    assert result == []


def test_root_readmes_missing_flagged(tmp_path):
    """Template root dir missing README.md → info finding."""
    (tmp_path / "src").mkdir()
    # No README.md in src/
    result = check_root_readmes(tmp_path, "code_repo")
    src_findings = [f for f in result if "src" in f["path"]]
    assert src_findings, "Missing README.md in src/ should produce a finding"
    assert src_findings[0]["severity"] == "info"


def test_root_readmes_missing_dir_not_flagged(tmp_path):
    """Dirs that don't exist are not flagged by check_root_readmes (already handled by check_project_structure_typed)."""
    # src/ doesn't exist at all — check_project_structure_typed handles this
    result = check_root_readmes(tmp_path, "code_repo")
    # Finding should not mention src because the dir itself doesn't exist
    src_findings = [f for f in result if "src/" in f["path"]]
    assert src_findings == []


def test_root_readmes_unknown_template_returns_empty(tmp_path):
    """Unknown template → no findings, no crash."""
    result = check_root_readmes(tmp_path, "nonexistent_type")
    assert result == []


def test_root_readmes_finding_type(tmp_path):
    """check_root_readmes findings have type='root_readmes'."""
    (tmp_path / "src").mkdir()
    result = check_root_readmes(tmp_path, "code_repo")
    assert all(f["type"] == "root_readmes" for f in result)
