"""Tests for docs-lint `new` generator (docs/new_doc.py) — issue #264 (A')."""
import sys
from pathlib import Path

import pytest

# Make docs.* importable
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.common import FRONTMATTER_RULES, parse_frontmatter  # noqa: E402
from docs.new_doc import create_doc, next_adr_number, slugify  # noqa: E402

TODAY = "2026-07-08"


def _fm(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def test_new_plan_dated_path_and_required_fields(tmp_path):
    p = create_doc(tmp_path, "plan", "telegram search command",
                   today=TODAY, milestone="M3", author="Stan")
    assert p == tmp_path / "docs/superpowers/plans/2026-07-08-telegram-search-command.md"
    fm = _fm(p)
    # every required field present → check_frontmatter (presence-only) passes
    for field in FRONTMATTER_RULES["superpowers/plans"]:
        assert field in fm
    assert fm["status"] == "draft"
    assert fm["date"] == TODAY
    assert fm["milestone"] == "M3"
    assert "owner" not in fm  # plans have no owner field


def test_new_spec_includes_owner(tmp_path):
    p = create_doc(tmp_path, "spec", "lifecycle os", today=TODAY, author="Stan")
    assert p.parent == tmp_path / "docs/superpowers/specs"
    fm = _fm(p)
    assert set(FRONTMATTER_RULES["superpowers/specs"]).issubset(fm.keys())
    assert fm["owner"] == "Stan"


def test_new_adr_sequence_and_status(tmp_path):
    adr_dir = tmp_path / "docs/adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-first.md").write_text("x", encoding="utf-8")
    (adr_dir / "0003-third.md").write_text("x", encoding="utf-8")
    p = create_doc(tmp_path, "adr", "new decision", today=TODAY)
    assert p.name == "0004-new-decision.md"
    fm = _fm(p)
    assert set(FRONTMATTER_RULES["adr"]).issubset(fm.keys())
    assert fm["status"] == "proposed"
    assert "date" in fm  # adr keeps date field
    assert "milestone" not in fm  # adr has no milestone


def test_new_adr_first_number_when_empty(tmp_path):
    p = create_doc(tmp_path, "adr", "first", today=TODAY)
    assert p.name == "0001-first.md"


def test_refuse_overwrite(tmp_path):
    create_doc(tmp_path, "plan", "dup", today=TODAY)
    with pytest.raises(FileExistsError):
        create_doc(tmp_path, "plan", "dup", today=TODAY)


def test_slug_normalized(tmp_path):
    p = create_doc(tmp_path, "plan", "  Foo BAR!! baz ", today=TODAY)
    assert p.name == "2026-07-08-foo-bar-baz.md"


def test_empty_slug_raises(tmp_path):
    with pytest.raises(ValueError):
        create_doc(tmp_path, "plan", "!!!", today=TODAY)


def test_unknown_kind_raises(tmp_path):
    with pytest.raises(ValueError):
        create_doc(tmp_path, "essay", "foo", today=TODAY)


def test_title_derived_from_slug_and_h1_body(tmp_path):
    p = create_doc(tmp_path, "plan", "my great plan", today=TODAY)
    text = p.read_text(encoding="utf-8")
    assert "# My great plan" in text
    assert _fm(p)["title"] == "My great plan"


def test_explicit_title_overrides(tmp_path):
    p = create_doc(tmp_path, "plan", "slugged", today=TODAY, title="Custom Title")
    assert _fm(p)["title"] == "Custom Title"


def test_slugify_helper():
    assert slugify("  Hello, World! ") == "hello-world"
    assert slugify("A--b__c") == "a-b-c"


def test_next_adr_number_ignores_non_numbered(tmp_path):
    adr_dir = tmp_path / "docs/adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "README.md").write_text("x", encoding="utf-8")
    (adr_dir / "0007-seven.md").write_text("x", encoding="utf-8")
    assert next_adr_number(adr_dir) == "0008"
