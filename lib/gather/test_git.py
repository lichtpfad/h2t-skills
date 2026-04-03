import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.git import gather_git, _parse_owner_repo

def test_gather_git_returns_expected_keys():
    result = gather_git()
    for key in ("remote", "branch", "log", "status", "owner_repo"):
        assert key in result, f"Missing key: {key}"

def test_gather_git_branch_is_string():
    result = gather_git()
    assert isinstance(result["branch"], str)
    assert len(result["branch"]) > 0

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
    test_parse_owner_repo_ssh()
    test_parse_owner_repo_https()
    test_parse_owner_repo_https_no_git()
    test_parse_owner_repo_empty()
    print("All git tests passed")
