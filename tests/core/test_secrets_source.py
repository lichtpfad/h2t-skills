import pytest

from h2t_ops.core import secrets


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k.startswith("SRC_TEST_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    shared = secrets.paths.secrets_shared()
    shared.mkdir(parents=True)
    legacy = secrets.paths.legacy("secrets.h2t")
    legacy.mkdir(parents=True)
    return shared, legacy


def test_source_legacy_only(sandbox):
    _, legacy = sandbox
    (legacy / "secrets.env").write_text("SRC_TEST_KEY=v\n", encoding="utf-8")
    assert secrets.source("SRC_TEST_KEY") == "legacy"


def test_source_shared_wins_over_legacy(sandbox):
    shared, legacy = sandbox
    (shared / "other.env").write_text("SRC_TEST_KEY=v\n", encoding="utf-8")
    (legacy / "secrets.env").write_text("SRC_TEST_KEY=old\n", encoding="utf-8")
    assert secrets.source("SRC_TEST_KEY") == "shared"


def test_source_none_when_absent_or_empty(sandbox):
    shared, _ = sandbox
    (shared / "other.env").write_text("SRC_TEST_KEY=\n", encoding="utf-8")
    assert secrets.source("SRC_TEST_KEY") is None
    assert secrets.source("SRC_TEST_NOPE") is None


def test_source_env_wins(sandbox, monkeypatch):
    shared, _ = sandbox
    (shared / "other.env").write_text("SRC_TEST_KEY=v\n", encoding="utf-8")
    monkeypatch.setenv("SRC_TEST_KEY", "e")
    assert secrets.source("SRC_TEST_KEY") == "env"
