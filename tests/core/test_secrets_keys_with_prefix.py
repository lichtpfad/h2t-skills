import pytest

from h2t_ops.core import secrets


@pytest.fixture
def sandboxed_secrets(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k.startswith("THREADS_"):
            monkeypatch.delenv(k)
    return tmp_path


def test_keys_with_prefix_lists_names_from_new_and_legacy(sandboxed_secrets):
    shared = secrets.paths.secrets_shared()
    shared.mkdir(parents=True)
    (shared / "threads.env").write_text("THREADS_TOKEN_A=x\nTHREADS_TOKEN_EMPTY=\nOTHER_KEY=z\n", encoding="utf-8")
    legacy = secrets.paths.legacy("secrets.h2t")
    legacy.mkdir(parents=True)
    (legacy / "other.env").write_text("THREADS_TOKEN_B=y\n", encoding="utf-8")
    assert secrets.keys_with_prefix("THREADS_TOKEN_") == ["THREADS_TOKEN_A", "THREADS_TOKEN_B"]


def test_keys_with_prefix_includes_environment_and_never_values(sandboxed_secrets, monkeypatch):
    monkeypatch.setenv("THREADS_TOKEN_ENV", "secret-value")
    names = secrets.keys_with_prefix("THREADS_TOKEN_")
    assert names == ["THREADS_TOKEN_ENV"]
    assert "secret-value" not in repr(names)
