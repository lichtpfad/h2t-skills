import argparse

from h2t_ops.core.registry import discover


def test_evals_connector_registered():
    names = {spec.name for spec in discover()}
    assert "evals" in names


def test_evals_status_handler_returns_status(monkeypatch):
    from h2t_ops.connectors.evals.commands import _cmd_status
    from lib.eval import session as sess

    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    result = _cmd_status(argparse.Namespace())
    expected_keys = {
        "mode", "source", "sdk_available", "token_present",
        "service_url", "local_dir", "session_count", "hint",
    }
    assert expected_keys <= set(result)
