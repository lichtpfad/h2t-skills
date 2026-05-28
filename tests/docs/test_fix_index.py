# tests/docs/test_fix_index.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.index_builder import (
    compute_index_update,
    write_index,
    INDEX_START,
    INDEX_END,
)

_FAKE_GENERATE = lambda rp, name: "# generated content\n"


def test_no_readme_operation_is_append(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "append"
    assert has_markers is False
    assert INDEX_START in content
    assert INDEX_END in content


def test_readme_with_markers_operation_is_replace(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text(f"# Manual\n\n{INDEX_START}\nold content\n{INDEX_END}\n")
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "replace"
    assert has_markers is True
    assert "old content" not in content
    assert "# Manual" in content
    assert "# generated content" in content


def test_readme_without_markers_operation_is_append(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text("# Manual Section\n\nsome content\n")
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "append"
    assert "# Manual Section" in content
    assert "some content" in content
    assert INDEX_START in content


def test_dry_run_does_not_write(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=False,
                         generate=_FAKE_GENERATE)
    readme = tmp_path / "docs" / "README.md"
    assert not readme.exists()
    assert report["status"] == "dry_run"
    assert report["applied"] is False


def test_apply_creates_readme(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=True,
                         generate=_FAKE_GENERATE)
    readme = tmp_path / "docs" / "README.md"
    assert readme.exists()
    content = readme.read_text(encoding="utf-8")
    assert INDEX_START in content
    assert report["status"] == "applied"
    assert report["applied"] is True


def test_apply_is_atomic_no_tmp_leftovers(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_index(tmp_path, "test-repo", apply=True, generate=_FAKE_GENERATE)
    tmp_files = list(docs.glob("*.tmp"))
    assert tmp_files == []


def test_apply_replace_preserves_manual_content(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text(f"# Manual\n\n{INDEX_START}\nold\n{INDEX_END}\n")
    write_index(tmp_path, "test-repo", apply=True, generate=_FAKE_GENERATE)
    content = readme.read_text(encoding="utf-8")
    assert "# Manual" in content
    assert "old" not in content
    assert "# generated content" in content


def test_apply_over_existing_readme_no_markers_succeeds(tmp_path):
    """apply=True over existing README without markers appends and does not crash (Windows-safe os.replace)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text("# Existing Content\n")
    report = write_index(tmp_path, "test-repo", apply=True,
                         generate=_FAKE_GENERATE)
    assert report["status"] == "applied"
    content = readme.read_text(encoding="utf-8")
    assert "# Existing Content" in content
    assert INDEX_START in content
    assert not list(docs.glob("*.tmp"))


def test_report_has_required_fields(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=False,
                         generate=_FAKE_GENERATE)
    assert "readme_path" in report
    assert "operation" in report
    assert "has_markers" in report
    assert "status" in report
    assert "applied" in report
