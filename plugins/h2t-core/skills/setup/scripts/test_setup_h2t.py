from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_setup():
    path = Path(__file__).with_name("setup_h2t.py")
    spec = importlib.util.spec_from_file_location("setup_h2t_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_install_h2t_ops_dry_run_uses_canonical_source(monkeypatch):
    setup = _load_setup()
    monkeypatch.setattr(setup, "resolve_uv", lambda: {"status": "ready", "path": "uv", "source": "test"})

    result = setup.install_h2t_ops("main", dry_run=True)

    assert result["status"] == "dry_run"
    assert result["source"] == setup.CANONICAL_H2T_OPS_SOURCE
    assert result["command"] == ["uv", "tool", "install", "--reinstall", setup.CANONICAL_H2T_OPS_SOURCE]
    assert result["root_h2t_touched"] is False


def test_install_h2t_ops_refuses_root_h2t(monkeypatch):
    setup = _load_setup()
    monkeypatch.setattr(setup, "resolve_uv", lambda: {"status": "ready", "path": "uv", "source": "test"})

    try:
        setup.install_h2t_ops("h2t", dry_run=True)
    except ValueError as exc:
        assert "root h2t" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_connector_matrix_is_credential_only_by_default(tmp_path, monkeypatch):
    setup = _load_setup()
    monkeypatch.setattr(setup, "resolve_h2t_ops", lambda **_: {"status": "ready", "path": "h2t-ops"})
    cfg = tmp_path / ".config" / "telegram"
    cfg.mkdir(parents=True)
    (cfg / "config.json").write_text("{}", encoding="utf-8")

    result = setup.connector_matrix(home=tmp_path)

    assert result["mode"] == "credential-only"
    telegram = next(c for c in result["connectors"] if c["connector"] == "telegram")
    research = next(c for c in result["connectors"] if c["connector"] == "research")
    assert telegram["status"] == "ready"
    assert telegram["live"] == "skipped"
    assert research["live"] == "skipped_paid"


def test_doctor_reports_optional_pos_not_configured(tmp_path, monkeypatch):
    setup = _load_setup()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(setup, "resolve_uv", lambda: {"status": "missing", "path": ""})
    monkeypatch.setattr(setup, "resolve_h2t_ops", lambda: {"status": "missing", "path": ""})

    result = setup.doctor(runner=lambda _args, _timeout: {"exit_code": 127, "stdout": "", "stderr": ""})

    assert result["kind"] == setup.KIND_DOCTOR
    assert result["optional_pos"]["status"] == "not_configured"
    assert result["boundaries"]["root_h2t_touched"] is False
    assert result["boundaries"]["pos_required"] is False
