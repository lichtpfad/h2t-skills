import os

import pytest

from h2t_ops.lifecycle.gather.user import gather_user_context


def test_gather_user_context_returns_expected_keys():
    result = gather_user_context()
    assert "core_path" in result
    assert "language" in result
    assert "available_contexts" in result
    assert "deep_paths" in result

def test_gather_user_context_core_exists():
    result = gather_user_context()
    if result["core_path"]:
        assert os.path.exists(result["core_path"])

def test_gather_user_context_never_returns_core_content():
    """core.md is referenced by path only; its body is not carried in the payload."""
    assert "core_content" not in gather_user_context()

def test_gather_user_context_core_path_missing(tmp_path):
    result = gather_user_context(config_root=str(tmp_path))
    assert result["core_path"] == ""

def test_gather_user_context_with_personal_domain():
    result = gather_user_context(domain="personal")
    # personal domain should include psychology.md if it exists
    assert isinstance(result["deep_paths"], list)

def test_gather_user_context_with_unknown_domain():
    result = gather_user_context(domain="nonexistent")
    assert result["deep_paths"] == []

if __name__ == "__main__":
    test_gather_user_context_returns_expected_keys()
    test_gather_user_context_core_exists()
    test_gather_user_context_with_personal_domain()
    test_gather_user_context_with_unknown_domain()
    print("All user tests passed")


def _user_yaml(text):
    from h2t_ops.core import paths
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def test_context_files_from_user_yaml(tmp_path):
    about = tmp_path / "about-me"
    about.mkdir()
    (about / "notes.md").write_text("x", encoding="utf-8")
    _user_yaml("context:\n  by_domain:\n    work: [notes.md]\n  strategy: docs/plan.md\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.md").write_text("x", encoding="utf-8")
    got = gather_user_context(domain="work", config_root=str(tmp_path))
    assert got["deep_paths"] == [str(about / "notes.md")]
    assert got["strategy_path"] == str(tmp_path / "docs" / "plan.md")
    assert gather_user_context(domain="personal", config_root=str(tmp_path))["deep_paths"] == []


def test_no_context_without_user_yaml(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "strategy-summary.md").write_text("x", encoding="utf-8")
    got = gather_user_context(domain="personal", config_root=str(tmp_path))
    assert got["deep_paths"] == []
    assert "strategy_path" not in got


def test_language_default_en():
    assert gather_user_context()["language"] == "en"


def test_language_from_user_yaml():
    _user_yaml("language: de\n")
    assert gather_user_context()["language"] == "de"


@pytest.mark.parametrize("by_domain", [
    "work: about-me/notes.md",            # a string, the shape doctor used to suggest
    "work: notes.md",
    "work: [notes.md, 3]",
    "[notes.md]",
], ids=["prefixed-string", "string", "non-string-item", "not-a-mapping"])
def test_by_domain_of_the_wrong_shape_gives_no_deep_paths(tmp_path, by_domain):
    about = tmp_path / "about-me"
    about.mkdir()
    (about / "notes.md").write_text("x", encoding="utf-8")
    _user_yaml(f"context:\n  by_domain: {{{by_domain}}}\n" if not by_domain.startswith("[")
               else f"context:\n  by_domain: {by_domain}\n")
    assert gather_user_context(domain="work", config_root=str(tmp_path))["deep_paths"] == []
