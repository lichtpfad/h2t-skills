# tests/connectors/evals/test_report_cli.py
from pathlib import Path

from h2t_ops.cli import dispatch


def _seed(root: Path):
    d = root / "session-start" / "sessions"
    d.mkdir(parents=True)
    (d / "a.json").write_text(
        '{"skill":"session-start","domain":"dev","project":"p","status":"success",'
        '"started_at":"2026-07-14T10:00:00+00:00","ended_at":"2026-07-14T10:00:01+00:00",'
        '"metrics":[{"key":"core.deflection_rate","value_num":1.0}]}',
        encoding="utf-8")


def test_report_json_returns_envelope(tmp_path, capsys, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--json", "--min-n", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"ok": true' in out
    assert '"provider": "evals"' in out
    assert "session-start" in out


def test_report_human_renders_table(tmp_path, capsys, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--min-n", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Instrumented-session health" in out
    assert "session-start" in out


def test_report_json_and_md_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--json", "--md"])
    assert code == 2
