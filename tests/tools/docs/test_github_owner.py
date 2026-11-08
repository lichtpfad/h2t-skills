"""The docs tools name no GitHub owner of their own (#581): it comes from the setting, from the
argument, or from the checkout's own remote — and its absence is exit 3, not the author's org."""
import subprocess
import sys

import pytest

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError
from h2t_ops.tools.docs import common, lint, migrate_legacy_labels, sync_labels


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("H2T_GITHUB_OWNER", raising=False)
    # a git with no user and no inherited config, so "no git user" is the state under test
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "EMAIL"):
        monkeypatch.delenv(var, raising=False)


def _git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def _checkout(path, remote=None):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


def test_target_owner_repo_as_given(tmp_path):
    assert common.target("acme/widget", tmp_path) == "acme/widget"


def test_bare_name_uses_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_GITHUB_OWNER", "acme")
    assert common.target("widget", tmp_path) == "acme/widget"


def test_bare_name_without_owner_is_exit_3_even_inside_a_checkout_with_a_remote(tmp_path):
    repo = _checkout(tmp_path / "r", "https://github.com/other/thing.git")
    with pytest.raises(ConfigError) as e:
        common.target("widget", repo)
    assert "H2T_GITHUB_OWNER" in (e.value.hint or "")
    assert "other" not in str(e.value) + (e.value.hint or "")


def test_bare_name_with_an_empty_owner_in_user_yaml_is_exit_3(tmp_path):
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('github:\n  owner: ""\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        common.target("widget", tmp_path)


@pytest.mark.parametrize("remote", [
    "https://github.com/acme/widget.git", "https://github.com/acme/widget",
    "git@github.com:acme/widget.git", "git@github.com:acme/widget",
])
def test_current_repo_from_origin(tmp_path, remote):
    repo = _checkout(tmp_path / "r", remote)
    assert common.target(None, repo) == "acme/widget"


def test_current_repo_without_remote_is_config_error(tmp_path):
    repo = _checkout(tmp_path / "r")
    with pytest.raises(ConfigError):
        common.target(None, repo)


def test_sync_labels_dry_run_never_prints_lichtpfad(monkeypatch, capsys):
    monkeypatch.setenv("H2T_GITHUB_OWNER", "acme")
    monkeypatch.setattr(sys, "argv", ["h2t-docs-sync-labels", "widget"])
    sync_labels.main()
    out = capsys.readouterr()
    assert "acme/widget" in out.out
    assert "lichtpfad" not in out.out + out.err


def test_sync_labels_bare_name_without_owner_is_exit_3(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["h2t-docs-sync-labels", "widget"])
    with pytest.raises(SystemExit) as e:
        sync_labels.main()
    assert e.value.code == 3


def test_manifest_without_mapping_is_config_error():
    with pytest.raises(ConfigError) as e:
        common._manifest()
    assert "owner/repo" in (e.value.hint or "")


def test_a_name_walk_does_not_need_a_mapping():
    assert "anything" not in common.REPO_MANIFEST


def test_migrate_requires_repo(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(migrate_legacy_labels, "run", lambda *a, **k: calls.append(a) or "")
    monkeypatch.setattr(sys, "argv", ["migrate_legacy_labels", "--apply"])
    with pytest.raises(SystemExit) as e:
        migrate_legacy_labels.main()
    assert e.value.code == 2
    assert calls == []


def test_migrate_uses_the_repo_it_is_given(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(migrate_legacy_labels, "run", lambda cmd: seen.append(cmd) or "")
    monkeypatch.setattr(sys, "argv", ["migrate_legacy_labels", "--repo", "acme/widget"])
    migrate_legacy_labels.main()
    assert seen and all("acme/widget" in c for c in seen)
    assert "lichtpfad" not in " ".join(" ".join(c) for c in seen)


def test_doc_owner_without_git_user_is_exit_3(monkeypatch, tmp_path, capsys):
    repo = _checkout(tmp_path / "r")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["h2t-docs-lint", "new", "spec", "thing", "--no-issue", "x",
                                      "--root", str(repo)])
    with pytest.raises(SystemExit) as e:
        lint.main()
    assert e.value.code == 3
    assert "git config --global user.name" in capsys.readouterr().err


def test_frontmatter_author_without_git_user_is_config_error(tmp_path):
    repo = _checkout(tmp_path / "r")
    f = repo / "docs" / "a.md"
    f.parent.mkdir()
    f.write_text("# A\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        lint._git_author(repo, f)


def test_the_bundled_list_and_extra_dirs_table_are_gone():
    assert not hasattr(common, "_BUNDLED_MANIFEST")
    assert not hasattr(common, "REPO_EXTRA_DIRS")
    assert not hasattr(sync_labels, "ORG")
    assert paths.config_dir()  # HOME isolation is in force
