"""Tests for h2t_secrets loader."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Resolve module path: plugins/h2t-core/scripts/
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
import h2t_secrets  # noqa: E402


def test_module_exposes_public_api():
    assert hasattr(h2t_secrets, "bootstrap")
    assert hasattr(h2t_secrets, "get_blob")
    assert hasattr(h2t_secrets, "DEFAULT_SECRETS_FILE")
    assert hasattr(h2t_secrets, "SECRETS_DIR")
    assert hasattr(h2t_secrets, "ENV_OVERRIDE")


def test_default_secrets_file_path():
    assert h2t_secrets.DEFAULT_SECRETS_FILE == Path.home() / ".dor" / "secrets" / "secrets.env"


def test_secrets_dir_path():
    assert h2t_secrets.SECRETS_DIR == Path.home() / ".dor" / "secrets"


def test_env_override_constant():
    assert h2t_secrets.ENV_OVERRIDE == "H2T_SECRETS_FILE"


# --- bootstrap() tests (Task 2) ---


def _write_env(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_bootstrap_loads_keys_into_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("FOO_KEY", raising=False)
    monkeypatch.delenv("BAR_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "FOO_KEY=foo-value\nBAR_KEY=bar-value\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    import os as _os
    assert _os.environ["FOO_KEY"] == "foo-value"
    assert _os.environ["BAR_KEY"] == "bar-value"
    assert new_keys == {"FOO_KEY": "foo-value", "BAR_KEY": "bar-value"}


def test_bootstrap_does_not_override_existing_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("EXISTING_KEY", "from-shell")
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "EXISTING_KEY=from-file\nNEW_KEY=from-file\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    import os as _os
    assert _os.environ["EXISTING_KEY"] == "from-shell"  # shell wins
    assert _os.environ["NEW_KEY"] == "from-file"
    assert "EXISTING_KEY" not in new_keys  # not "newly set"
    assert new_keys == {"NEW_KEY": "from-file"}


def test_bootstrap_fail_loud_on_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.env"
    with pytest.raises(FileNotFoundError) as ei:
        h2t_secrets.bootstrap(env_file=missing)
    msg = str(ei.value)
    assert str(missing) in msg
    assert "secrets.env" in msg


def test_bootstrap_skips_comments_and_blanks(tmp_path, monkeypatch):
    monkeypatch.delenv("REAL_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "# comment line\n\n  \n# another comment\nREAL_KEY=value\n\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    assert new_keys == {"REAL_KEY": "value"}


def test_bootstrap_handles_quoted_values(tmp_path, monkeypatch):
    monkeypatch.delenv("DOUBLE", raising=False)
    monkeypatch.delenv("SINGLE", raising=False)
    monkeypatch.delenv("UNQUOTED", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, 'DOUBLE="dval"\nSINGLE=\'sval\'\nUNQUOTED=uval\n')

    h2t_secrets.bootstrap(env_file=env_file)

    import os as _os
    assert _os.environ["DOUBLE"] == "dval"
    assert _os.environ["SINGLE"] == "sval"
    assert _os.environ["UNQUOTED"] == "uval"


def test_bootstrap_raises_on_malformed_line(tmp_path):
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "GOOD=val\nnot_a_kv_pair\n")

    with pytest.raises(ValueError) as ei:
        h2t_secrets.bootstrap(env_file=env_file)
    msg = str(ei.value).lower()
    assert "line 2" in msg or "line=2" in msg


def test_bootstrap_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("IDEM_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "IDEM_KEY=idem-val\n")

    first = h2t_secrets.bootstrap(env_file=env_file)
    second = h2t_secrets.bootstrap(env_file=env_file)

    assert first == {"IDEM_KEY": "idem-val"}
    assert second == {}  # nothing new on second call


def test_bootstrap_via_env_file_override(tmp_path, monkeypatch):
    monkeypatch.delenv("OVERRIDE_KEY", raising=False)
    env_file = tmp_path / "alt.env"
    _write_env(env_file, "OVERRIDE_KEY=overridden\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(env_file))

    new_keys = h2t_secrets.bootstrap()  # no env_file arg

    assert new_keys == {"OVERRIDE_KEY": "overridden"}


# --- get_blob() tests (Task 3) ---


def test_get_blob_returns_existing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(h2t_secrets, "SECRETS_DIR", tmp_path)
    blob_dir = tmp_path / "google"
    blob_dir.mkdir()
    blob = blob_dir / "oauth-client.json"
    blob.write_text('{"client_id": "fake"}', encoding="utf-8")

    result = h2t_secrets.get_blob("google/oauth-client.json")

    assert result == blob.resolve()
    assert result.is_file()


def test_get_blob_fail_loud_on_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(h2t_secrets, "SECRETS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError) as ei:
        h2t_secrets.get_blob("google/missing.json")
    msg = str(ei.value)
    assert "google/missing.json" in msg or "missing.json" in msg
