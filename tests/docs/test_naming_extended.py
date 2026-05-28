# tests/docs/test_naming_extended.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.naming import check_naming_all_docs


def test_no_docs_dir_no_findings(tmp_path):
    assert check_naming_all_docs(tmp_path) == []


def test_clean_kebab_file_no_finding(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my-guide.md").write_text("# Guide")
    assert check_naming_all_docs(tmp_path) == []


def test_readme_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# README")
    assert check_naming_all_docs(tmp_path) == []


def test_changelog_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CHANGELOG.md").write_text("# Changes")
    assert check_naming_all_docs(tmp_path) == []


def test_uppercase_filename_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "MyDoc.md").write_text("# My Doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert results[0]["type"] == "naming"
    assert results[0]["severity"] == "warn"
    assert "MyDoc.md" in results[0]["message"]


def test_space_in_name_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my doc.md").write_text("# my doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert results[0]["safe_fix"] is not None


def test_underscore_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my_doc.md").write_text("# my doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "my-doc.md" in results[0]["safe_fix"]


def test_spec_without_date_prefix_flagged(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "my-feature-design.md").write_text("# Spec")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "date prefix" in results[0]["message"]
    assert "YYYY-MM-DD-my-feature-design.md" in results[0]["safe_fix"]


def test_spec_with_date_prefix_ok(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "2026-05-28-my-feature.md").write_text("# Spec")
    assert check_naming_all_docs(tmp_path) == []


def test_plan_without_date_flagged(tmp_path):
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "my-plan.md").write_text("# Plan")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "date prefix" in results[0]["message"]


def test_index_md_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Index")
    assert check_naming_all_docs(tmp_path) == []
