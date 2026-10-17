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


def _skill(root: Path, name: str) -> None:
    (root / "skills" / name).mkdir(parents=True)
    (root / "skills" / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")


def test_catalog_comes_from_the_installed_plugin_cache_outside_a_checkout(tmp_path, monkeypatch):
    """In an installed wheel there is no `plugins/` beside the package: the catalog is the
    newest cached version of each lichtpfad plugin under the Claude config dir."""
    from h2t_ops.connectors.evals import commands
    config = tmp_path / "claude"
    cache = config / "plugins" / "cache" / "lichtpfad"
    _skill(cache / "h2t-core" / "4.0.0", "handoff")
    _skill(cache / "h2t-core" / "3.9.0", "dropped-long-ago")
    _skill(cache / "h2t-ops" / "4.0.0", "research")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    wheel = tmp_path / "site-packages" / "h2t_ops" / "connectors" / "evals" / "commands.py"
    assert commands.known_skills(here=wheel) == {"handoff", "research"}


def test_catalog_prefers_the_checkout_beside_the_package(tmp_path, monkeypatch):
    from h2t_ops.connectors.evals import commands
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "none"))
    repo = tmp_path / "repo"
    _skill(repo / "plugins" / "h2t-core", "session-start")
    here = repo / "h2t_ops" / "connectors" / "evals" / "commands.py"
    assert commands.known_skills(here=here) == {"session-start"}


def test_no_catalog_anywhere_is_an_empty_set(tmp_path, monkeypatch):
    from h2t_ops.connectors.evals import commands
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "none"))
    assert commands.known_skills(here=tmp_path / "a" / "b" / "c" / "commands.py") == set()
