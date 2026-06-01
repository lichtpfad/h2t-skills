import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-init/scripts"
sys.path.insert(0, str(_SCRIPT_DIR))

from init import init_repo


def test_init_repo_accepts_explicit_repo_root_outside_dev(tmp_path):
    repo = tmp_path / "client-project"
    repo.mkdir()

    changes = init_repo(
        "client-project",
        repo_root=repo,
        dry_run=False,
        commit=False,
        template="client_project",
    )

    assert changes is not None
    assert (repo / "docs" / "README.md").exists()
    assert (repo / ".claude" / "rules" / "documentation.md").exists()
    assert (repo / ".claude" / "rules" / "docs-lint.yaml").exists()


def test_init_repo_writes_docs_lint_template_config(tmp_path):
    repo = tmp_path / "research-project"
    repo.mkdir()

    init_repo(
        "research-project",
        repo_root=repo,
        dry_run=False,
        commit=False,
        template="research_project",
    )

    cfg = (repo / ".claude" / "rules" / "docs-lint.yaml").read_text(encoding="utf-8")
    assert "template: research_project" in cfg
    assert "docs_root: docs" in cfg


def test_init_repo_preserves_old_name_mode(monkeypatch, tmp_path):
    import init as init_mod

    repo = tmp_path / "h2t-example"
    repo.mkdir()
    monkeypatch.setattr(init_mod, "repo_path", lambda name: repo)

    changes = init_repo("h2t-example", dry_run=False, commit=False)

    assert changes is not None
    assert (repo / "docs" / "README.md").exists()


def test_init_repo_returns_none_when_explicit_root_missing(tmp_path):
    missing = tmp_path / "missing"
    assert init_repo("missing", repo_root=missing, dry_run=True) is None


def test_init_repo_rejects_home_directory(monkeypatch, tmp_path):
    from pathlib import Path
    import init as init_mod
    # Temporarily treat tmp_path as "home" for testing purposes
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    result = init_repo("home", repo_root=tmp_path, dry_run=True)
    assert result is None
