import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.project import identify_project, _split_domain_project, _find_label

def test_identify_project_returns_expected_keys():
    result = identify_project(".")
    for key in ("id", "domain", "type", "github", "config_root"):
        assert key in result, f"Missing key: {key}"

def test_identify_project_git_repo():
    """In claude-agent-skills — a git repo mapped in repo-mapping.yaml."""
    result = identify_project(".")
    assert result["type"] == "git"
    assert result["domain"] == "personal-os"
    assert result["id"] == "agent-skills"

def test_split_domain_project():
    assert _split_domain_project("personal-os/agent-skills") == ("personal-os", "agent-skills")
    assert _split_domain_project("dev/unknown") == ("dev", "unknown")
    assert _split_domain_project("standalone") == ("standalone", "unknown")

def test_find_label_missing():
    assert _find_label({}, "x", "y") == "y"

if __name__ == "__main__":
    test_identify_project_returns_expected_keys()
    test_identify_project_git_repo()
    test_split_domain_project()
    test_find_label_missing()
    print("All project tests passed")
