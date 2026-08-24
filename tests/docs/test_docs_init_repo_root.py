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


def test_init_repo_adds_lint_temp_files_to_gitignore(tmp_path):
    """docs-init appends .h2t/lint-before.json and lint-after.json to .gitignore."""
    repo = tmp_path / "my-repo"
    repo.mkdir()

    init_repo("my-repo", repo_root=repo, dry_run=False, commit=False)

    gi = (repo / ".gitignore").read_text(encoding="utf-8")
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi


def test_init_repo_creates_h2t_lint_state(tmp_path):
    """docs-init creates .h2t/lint-state.jsonl so it's tracked from day 0."""
    repo = tmp_path / "my-repo"
    repo.mkdir()

    init_repo("my-repo", repo_root=repo, dry_run=False, commit=False)

    lint_state = repo / ".h2t" / "lint-state.jsonl"
    assert lint_state.exists(), ".h2t/lint-state.jsonl must be created by docs-init"
