"""Repo-wide pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _neutralize_eval_secrets(monkeypatch, tmp_path_factory):
    """Stop the real ~/.dor/secrets.env from leaking H2T_EVALS_* creds into tests.

    Once #321 creds are configured, SkillEval construction resolves mode=push
    and (in a venv with the h2t_evals SDK) would fire real network pushes to
    prod during unit tests. Point the default secrets file at a nonexistent
    path; tests that need a file pass secrets_path=... or monkeypatch
    session._DEFAULT_SECRETS explicitly.
    """
    try:
        from lib.eval import session as sess
    except Exception:
        return
    missing = tmp_path_factory.mktemp("no-secrets") / "secrets.env"
    monkeypatch.setattr(sess, "_DEFAULT_SECRETS", missing, raising=False)
