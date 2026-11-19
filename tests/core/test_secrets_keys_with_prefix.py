import pytest

from h2t_ops.core import secrets


@pytest.fixture
def sandboxed_secrets(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k.startswith("THREADS_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    return tmp_path


def test_keys_with_prefix_lists_names_from_new_and_legacy(sandboxed_secrets):
    tmp_path = sandboxed_secrets
    shared = secrets.paths.secrets_shared()
    assert tmp_path / "root" in shared.parents      # the new root, not HOME
    shared.mkdir(parents=True)
    assert secrets.paths.legacy("secrets.h2t") != shared
    (shared / "threads.env").write_text("THREADS_TOKEN_A=x\nTHREADS_TOKEN_EMPTY=\nOTHER_KEY=z\n", encoding="utf-8")
    legacy = secrets.paths.legacy("secrets.h2t")
    legacy.mkdir(parents=True)
    assert tmp_path / "home" in legacy.parents
    (legacy / "other.env").write_text("THREADS_TOKEN_B=y\n", encoding="utf-8")
    assert secrets.keys_with_prefix("THREADS_TOKEN_") == ["THREADS_TOKEN_A", "THREADS_TOKEN_B"]


def test_keys_with_prefix_includes_environment_and_never_values(sandboxed_secrets, monkeypatch):
    monkeypatch.setenv("THREADS_TOKEN_ENV", "secret-value")
    names = secrets.keys_with_prefix("THREADS_TOKEN_")
    assert names == ["THREADS_TOKEN_ENV"]
    assert "secret-value" not in repr(names)
