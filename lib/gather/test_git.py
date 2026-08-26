import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.git import _display_branch, _hooks_state, _parse_owner_repo, gather_git


def test_gather_git_returns_expected_keys():
    result = gather_git()
    for key in ("remote", "branch", "log", "status", "owner_repo"):
        assert key in result, f"Missing key: {key}"

def test_gather_git_branch_is_string():
    result = gather_git()
    assert isinstance(result["branch"], str)
    assert len(result["branch"]) > 0

def test_display_branch_uses_branch_when_available():
    assert _display_branch("main\n", "abc123\n") == "main"

def test_display_branch_handles_detached_head():
    assert _display_branch("\n", "abc123\n") == "detached:abc123"

def test_parse_owner_repo_ssh():
    assert _parse_owner_repo("git@github.com:lichtpfad/h2t.git") == "lichtpfad/h2t"

def test_parse_owner_repo_https():
    assert _parse_owner_repo("https://github.com/lichtpfad/h2t.git") == "lichtpfad/h2t"

def test_parse_owner_repo_https_no_git():
    assert _parse_owner_repo("https://github.com/lichtpfad/h2t") == "lichtpfad/h2t"

def test_parse_owner_repo_empty():
    assert _parse_owner_repo("") == ""

if __name__ == "__main__":
    test_gather_git_returns_expected_keys()
    test_gather_git_branch_is_string()
    test_display_branch_uses_branch_when_available()
    test_display_branch_handles_detached_head()
    test_parse_owner_repo_ssh()
    test_parse_owner_repo_https()
    test_parse_owner_repo_https_no_git()
    test_parse_owner_repo_empty()
    print("All git tests passed")


def _hook_repo(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / "scripts" / "hooks").mkdir(parents=True)
    (tmp_path / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


def test_repo_without_a_tracked_hook_reports_nothing(tmp_path):
    """No versioned hook is not a finding — most repos have none."""
    assert _hooks_state(str(tmp_path), "", "") == {
        "versioned": False, "active": True, "dir": "",
    }


def test_tracked_hook_with_hooks_path_set_is_active(tmp_path):
    root = _hook_repo(tmp_path)
    state = _hooks_state(str(root), "scripts/hooks", "scripts/hooks/pre-commit\n")
    assert state == {"versioned": True, "active": True, "dir": "scripts/hooks"}


def test_tracked_hook_never_wired_into_the_clone_is_inactive(tmp_path):
    """The failure this exists to catch: committed, and git never runs it."""
    root = _hook_repo(tmp_path)
    state = _hooks_state(str(root), "", "scripts/hooks/pre-commit\n")
    assert state["versioned"] is True
    assert state["active"] is False


def test_legacy_symlink_install_still_counts_as_active(tmp_path):
    """install.sh used to symlink into .git/hooks; those clones are not broken."""
    root = _hook_repo(tmp_path)
    (root / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n")
    assert _hooks_state(str(root), "", "scripts/hooks/pre-commit\n")["active"] is True


def test_hooks_path_pointing_where_the_hook_is_not_is_inactive(tmp_path):
    """A set-but-wrong path produces the same silence as an unset one."""
    root = _hook_repo(tmp_path)
    (root / "elsewhere").mkdir()
    assert _hooks_state(str(root), "elsewhere", "scripts/hooks/pre-commit\n")["active"] is False
