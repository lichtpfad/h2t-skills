from lib.eval import session as sess
from lib.eval.status import get_status


def test_status_off_when_no_sdk_or_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    st = get_status(env={}, evals_root="/nonexistent")
    assert st["mode"] == "off"
    assert st["sdk_available"] is False
    assert st["token_present"] is False
    assert "H2T_EVALS_MODE=local" in st["hint"]


def test_status_push_when_sdk_and_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    st = get_status(env={"H2T_EVALS_TOKEN": "t"}, evals_root="/nonexistent")
    assert st["mode"] == "push"
    assert st["token_present"] is True


def test_status_source_legacy(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    st = get_status(env={"H2T_EVALS_ENABLED": "1"}, evals_root="/nonexistent")
    assert st["source"] == "legacy"
    assert st["mode"] == "push"


def test_status_default_env_merges_secrets_file(tmp_path, monkeypatch):
    """get_status() default env reflects ~/.dor/secrets.env so operators see push (#321)."""
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    f = tmp_path / "secrets.env"
    f.write_text("H2T_EVALS_TOKEN=tok\n", encoding="utf-8")
    monkeypatch.setattr(sess, "_DEFAULT_SECRETS", f)
    for var in ("H2T_EVALS_MODE", "H2T_EVALS_ENABLED", "H2T_EVALS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    st = get_status(evals_root="/nonexistent")
    assert st["token_present"] is True
    assert st["mode"] == "push"


def test_status_counts_local_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    d = tmp_path / "session-start" / "sessions"
    d.mkdir(parents=True)
    (d / "se-2026-07-11-001.json").write_text("{}", encoding="utf-8")
    st = get_status(env={}, evals_root=str(tmp_path))
    assert st["session_count"] == 1
    assert st["local_dir"] == str(tmp_path)
