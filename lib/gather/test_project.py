import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.project import _find_label, _split_domain_project, identify_project


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


def _config_root(tmp_path, domains_yaml: str = "") -> str:
    """An isolated config root. Without it these tests read the developer's own
    ~/.h2t/config and pass or fail for reasons that have nothing to do with the code."""
    root = tmp_path / "config"
    root.mkdir(parents=True, exist_ok=True)
    (root / "repo-mapping.yaml").write_text("mappings: {}\ndefault: dev/unknown\n", encoding="utf-8")
    (root / "domains.yaml").write_text(domains_yaml or "domains: {}\n", encoding="utf-8")
    return str(root)


def _git_repo(path, remote="git@github.com:someone/mapped-name.git"):
    import subprocess
    path.mkdir(parents=True, exist_ok=True)
    for cmd in (["git", "init", "-q"], ["git", "remote", "add", "origin", remote]):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)
    return path


def test_project_id_file_wins_over_the_remote(tmp_path, monkeypatch):
    """Identity travels with the checkout, so a clone needs no central mapping.

    The remote here IS mapped, and mapped to something else. Without a real remote and a
    conflicting mapping this test would pass even if the file were read last.
    """
    repo = _git_repo(tmp_path / "repo")
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("personal-os/agent-skills\n", encoding="utf-8")
    root = tmp_path / "config"
    root.mkdir(parents=True, exist_ok=True)
    (root / "repo-mapping.yaml").write_text(
        "mappings:\n  mapped-name: elsewhere/wrong-answer\ndefault: dev/unknown\n",
        encoding="utf-8",
    )
    (root / "domains.yaml").write_text("domains: {}\n", encoding="utf-8")
    monkeypatch.setenv("H2T_CONFIG_ROOT", str(root))

    # control: without the file, the remote mapping is what answers
    assert identify_project(str(repo / "..")) is not None
    (repo / ".claude" / "project-id").rename(repo / ".claude" / "project-id.off")
    assert identify_project(str(repo))["id"] == "wrong-answer"
    (repo / ".claude" / "project-id.off").rename(repo / ".claude" / "project-id")

    result = identify_project(str(repo))
    assert result["id"] == "agent-skills"
    assert result["domain"] == "personal-os"


def test_the_file_is_found_from_a_subdirectory(tmp_path, monkeypatch):
    """The hook passes $PWD, which is usually below the checkout root."""
    repo = _git_repo(tmp_path / "repo")
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("personal-os/agent-skills\n", encoding="utf-8")
    deep = repo / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    assert identify_project(str(deep))["id"] == "agent-skills"


def test_the_walk_stops_at_the_repository_root(tmp_path, monkeypatch):
    """A project-id above a repository describes a different project.

    Inheriting it would name the wrong one — worse than resolving to unknown, because a
    wrong name is written into that other project's session history.
    """
    workspace = tmp_path / "workspace"
    (workspace / ".claude").mkdir(parents=True)
    (workspace / ".claude" / "project-id").write_text("outer/not-this-one\n", encoding="utf-8")
    inner = _git_repo(workspace / "inner")
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    assert identify_project(str(inner))["id"] != "not-this-one"


def test_a_bare_id_takes_its_domain_from_domains_yaml(tmp_path, monkeypatch):
    """Every file this feature has actually written holds a bare id, no domain.

    Measured 2026-08-23: h2t-business, rejuve, lynxcap-leads and POS all carry one line
    with the id alone, because apply_registration.py writes `project_id`.
    """
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("rejuve\n", encoding="utf-8")
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(
        tmp_path,
        "domains:\n  business:\n    projects:\n      - id: rejuve\n        label: Rejuve\n",
    ))
    result = identify_project(str(repo))
    assert result["id"] == "rejuve"
    assert result["domain"] == "business"
    assert result["label"] == "Rejuve"


def test_an_unknown_bare_id_falls_back_to_dev(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("nowhere-in-yaml\n", encoding="utf-8")
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    result = identify_project(str(repo))
    assert result["id"] == "nowhere-in-yaml"
    assert result["domain"] == "dev"


def test_an_empty_project_id_file_is_ignored(tmp_path, monkeypatch):
    """A truncated write must not name the project the empty string."""
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("   \n", encoding="utf-8")
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    result = identify_project(str(repo))
    assert result["id"] == "unknown"


def test_without_the_file_nothing_changes(tmp_path, monkeypatch):
    """The control. If this returned an id too, the tests above would prove nothing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    result = identify_project(str(repo))
    assert result["id"] == "unknown"
    assert result["domain"] == "dev"


def test_the_file_does_not_cost_the_github_slug(tmp_path, monkeypatch):
    """gather.py skips gather_github entirely when project["github"] is falsy.

    Returning None here empties issues, milestones and PRs for exactly the repos this
    feature prioritizes — and an empty briefing section looks like "no open issues",
    not like a defect. Measured on four live checkouts before this test existed.
    """
    repo = _git_repo(tmp_path / "repo", remote="git@github.com:lichtpfad/rejuve.git")
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "project-id").write_text("business/rejuve\n", encoding="utf-8")
    monkeypatch.setenv("H2T_CONFIG_ROOT", _config_root(tmp_path))
    result = identify_project(str(repo))
    assert result["id"] == "rejuve"
    assert result["github"] == "lichtpfad/rejuve"
