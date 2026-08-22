import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.project import identify_project, _split_domain_project, _find_label

def test_identify_project_returns_expected_keys():
    result = identify_project(".")
    for key in ("id", "domain", "type", "github", "config_root"):
        assert key in result, f"Missing key: {key}"

def test_identify_project_git_repo():
    """In claude-agent-skills — a git repo. Domain may vary by local config."""
    result = identify_project(".")
    assert result["type"] == "git"
    # Domain defaults to 'dev' in CI (no local repo-mapping.yaml); locally maps to 'personal-os'.
    assert isinstance(result["domain"], str) and len(result["domain"]) > 0

def test_split_domain_project():
    assert _split_domain_project("personal-os/agent-skills") == ("personal-os", "agent-skills")
    assert _split_domain_project("dev/unknown") == ("dev", "unknown")
    assert _split_domain_project("standalone") == ("standalone", "unknown")

def test_identify_project_in_directory_without_git_remote(tmp_path):
    """`git remote get-url origin` exits non-zero outside a repo.

    run_parallel reports that as None, so the caller must not strip it blindly —
    identification has to fall through to the cwd patterns and the default.
    """
    result = identify_project(str(tmp_path))
    assert result["github"] in (None, "")
    assert isinstance(result["id"], str) and result["id"]

def test_find_label_missing():
    assert _find_label({}, "x", "y") == "y"

if __name__ == "__main__":
    test_identify_project_returns_expected_keys()
    test_identify_project_git_repo()
    test_split_domain_project()
    test_find_label_missing()
    print("All project tests passed")
