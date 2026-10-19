"""Tests for detect_project detection logic (moved with the module, Task 12)."""
from h2t_ops.lifecycle.detect_project import (
    _check_already_registered,
    _detect_domain,
    _detect_tracker,
    _humanize_id,
)


def test_detect_domain_h2t_prefix():
    """The signal is the repository name, so the answer must not depend on the root."""
    for path in ("C:/dev/h2t-vision", "/Users/x/Projects/h2t-vision", "/home/y/src/h2t-vision"):
        assert _detect_domain(path) == (
            "hou2touch", "high", "repository named h2t-* matches hou2touch"
        ), path


def test_detect_domain_crypto_prefix():
    for path in ("C:/dev/crypto-etl", "/Users/x/Projects/crypto-etl"):
        assert _detect_domain(path) == (
            "crypto", "high", "repository named crypto-* matches crypto"
        ), path


def test_an_unrecognised_repository_gets_no_domain():
    """The catch-all this replaces answered `dev` for anything under `C:/dev/`.

    That is a guess made from one machine's directory name: it fired for every
    repository the author kept there and for nobody else's, at medium confidence, which
    reads as information and is not. `init-project` already handles `None` — it asks.
    """
    domain, confidence, reason = _detect_domain("C:/dev/some-project")
    assert domain is None
    assert confidence == "low"
    assert "no pattern match" in reason


def test_detect_domain_dropbox_h2t():
    domain, confidence, reason = _detect_domain("E:/DROPBOX/LichtPfad Dropbox/HOU2TOUCH/COURSES")
    assert domain == "hou2touch"
    assert confidence == "high"


def test_detect_domain_unknown():
    domain, confidence, reason = _detect_domain("D:/random/folder")
    assert domain is None
    assert confidence == "low"


def _user_yaml(text):
    from h2t_ops.core import paths
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def test_personal_paths_get_no_domain_without_user_yaml():
    """The author's own repositories are no longer named in the code (#548 R45): without
    domain_patterns they are new repositories like any other, and registration asks."""
    domain, confidence, _ = _detect_domain("/Users/x/Projects/DOR")
    assert (domain, confidence) == (None, "low")


def test_domain_patterns_from_user_yaml():
    _user_yaml("domain_patterns:\n  - pattern: Projects/DOR|Projects/newsengine\n"
               "    domain: personal-os\n")
    assert _detect_domain("/Users/x/Projects/DOR") == ("personal-os", "high", "user.yaml")
    assert _detect_domain("/Users/x/Projects/elsewhere")[0] is None


def test_a_broken_domain_pattern_names_the_file():
    import pytest

    from h2t_ops.core import user_config
    from h2t_ops.core.errors import ConfigError
    _user_yaml("domain_patterns:\n  - pattern: \"(unclosed\"\n    domain: x\n")
    with pytest.raises(ConfigError) as exc:
        _detect_domain("/Users/x/Projects/DOR")
    assert str(user_config.path()) in str(exc.value)


def test_humanize_id():
    assert _humanize_id("h2t-vision") == "H2T Vision"
    assert _humanize_id("crypto-etl") == "Crypto ETL"
    assert _humanize_id("my-cool-project") == "My Cool Project"


def test_detect_tracker_github_only():
    """GitHub accessible, no notion -> github."""
    # Can't test gh CLI in unit tests, test the logic with mocked inputs
    domains = {"domains": {"dev": {"label": "Dev"}}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", "dev", domains)
    # Note: this will try to run `gh` — may fail in CI. Test the no-github path instead.


def test_detect_tracker_deferred_when_no_domain():
    """Domain unknown -> tracker deferred."""
    domains = {"domains": {}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", None, domains)
    assert tracker is None
    assert confidence == "deferred"


def test_detect_tracker_none_when_no_github_no_notion():
    """No GitHub, no Notion -> none."""
    domains = {"domains": {"admin": {"label": "Admin"}}}
    # github=None means no remote
    tracker, confidence, reason = _detect_tracker(None, "admin", domains)
    assert tracker == "none"
    assert confidence == "high"


def test_check_already_registered_found():
    mapping = {"mappings": {"my-repo": "dev/my-project"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/my-repo", "my-repo", mapping)
    assert result is not None
    assert result["id"] == "my-project"
    assert result["domain"] == "dev"


def test_check_already_registered_not_found():
    mapping = {"mappings": {"other-repo": "dev/other"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/new-repo", "new-repo", mapping)
    assert result is None


def test_check_already_registered_cwd_pattern():
    mapping = {"mappings": {}, "cwd_patterns": {"/Steuer": "admin/taxes"}}
    result = _check_already_registered("E:/DROPBOX/Steuer/2026", None, mapping)
    assert result is not None
    assert result["domain"] == "admin"


_TAXES = ("mappings: {}\ncwd_patterns:\n  /Steuer: admin/taxes\n",
          "domains:\n  admin:\n    projects:\n      - id: taxes\n        label: Taxes Label\n")


def _config(root, mapping, domains):
    root.mkdir(parents=True, exist_ok=True)
    (root / "repo-mapping.yaml").write_text(mapping, encoding="utf-8")
    (root / "domains.yaml").write_text(domains, encoding="utf-8")
    return root


def test_without_config_root_the_index_answers_and_the_old_env_is_ignored(tmp_path, monkeypatch):
    """config/ under HOME through index.ontology(); H2T_CONFIG_ROOT is not read (#548 R5)."""
    from h2t_ops.core import paths
    from h2t_ops.lifecycle.detect_project import detect_project
    _config(paths.config_dir(), *_TAXES)
    monkeypatch.setenv("H2T_CONFIG_ROOT", str(_config(tmp_path / "decoy", "mappings: {}\n", "domains: {}\n")))
    cwd = tmp_path / "Steuer"
    cwd.mkdir()
    got = detect_project(str(cwd))
    assert got["already_registered"] is True
    assert got["current"]["label"] == "Taxes Label"
    assert (paths.state_dir() / "index.sqlite").is_file()


def test_a_named_config_root_is_read_directly_without_the_index(tmp_path):
    """An explicit --config-root never builds this machine's base: a caller may point at
    any directory. The control is the test above, where the base is built."""
    from h2t_ops.core import paths
    from h2t_ops.lifecycle.detect_project import detect_project
    cwd = tmp_path / "Steuer"
    cwd.mkdir()
    got = detect_project(str(cwd), config_root=str(_config(tmp_path / "named", *_TAXES)))
    assert got["current"]["label"] == "Taxes Label"
    assert not (paths.state_dir() / "index.sqlite").exists()
