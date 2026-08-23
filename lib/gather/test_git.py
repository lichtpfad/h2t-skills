import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.git import _display_branch, _parse_owner_repo, gather_git


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
