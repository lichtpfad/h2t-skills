"""One machine name for session paths and the activity spool; setup pins it (#491).

macOS renames the host with the network (`MacBook-Pro-3` in the morning, `Mac` at night),
so the handoff writer, the session reader and the activity spool — each with its own copy
of the rule — split one machine's records across directories and casings.
"""
import importlib.util
import json
import os
import platform
from pathlib import Path

import pytest

from h2t_ops.lifecycle.activity import writer as activity_writer
from h2t_ops.lifecycle.gather import sessions
from h2t_ops.setup import legacy as setup_h2t

REPO = Path(__file__).resolve().parents[2]
HANDOFF_WRITER = REPO / "h2t_ops" / "lifecycle" / "handoff.py"
SETUP_SKILL = REPO / "plugins" / "h2t-core" / "skills" / "setup"


def _load_handoff_writer():
    spec = importlib.util.spec_from_file_location("_handoff_writer_under_test", HANDOFF_WRITER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def renamed_host(monkeypatch, tmp_path):
    for var in ("H2T_MACHINE_NAME", "DOR_MACHINE_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(platform, "node", lambda: "Mac.local")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "spool.jsonl"))
    return tmp_path


def test_machine_name_is_the_same_for_writer_reader_and_spool(renamed_host):
    handoff = _load_handoff_writer()

    written_under = handoff.default_markdown_dir("proj").parent.name
    activity_writer.log_session_start(session_id="s", domain="dev", project="proj")
    spooled = json.loads((renamed_host / "spool.jsonl").read_text(encoding="utf-8"))["machine"]

    assert written_under == sessions.get_machine_name() == spooled == "mac"


def _settings(tmp_path):
    return tmp_path / ".claude" / "settings.json"


def test_setup_writes_machine_name_and_keeps_the_rest(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    settings = _settings(renamed_host)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"model": "x", "env": {"OTHER": "1"}}), encoding="utf-8")

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result["status"] == "written"
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "model": "x",
        "env": {"OTHER": "1", "H2T_MACHINE_NAME": "mac"},
    }


def test_setup_keeps_an_existing_machine_name(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    settings = _settings(renamed_host)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {"H2T_MACHINE_NAME": "macbook-pro-3"}}), encoding="utf-8")
    before = settings.read_text(encoding="utf-8")

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result == {"status": "unchanged", "path": str(settings), "value": "macbook-pro-3"}
    assert settings.read_text(encoding="utf-8") == before


def test_setup_leaves_an_invalid_settings_file_alone(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    settings = _settings(renamed_host)
    settings.parent.mkdir(parents=True)
    settings.write_text("{ not json", encoding="utf-8")

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result["status"] == "error"
    assert settings.read_text(encoding="utf-8") == "{ not json"


def test_setup_does_not_overwrite_a_preference_saved_meanwhile(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    settings = _settings(renamed_host)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"model": "x"}), encoding="utf-8")
    real_mkstemp = setup_h2t.tempfile.mkstemp
    calls = []

    def claude_code_saves_meanwhile(*args, **kwargs):
        if not calls:
            settings.write_text(json.dumps({"model": "x", "theme": "dark"}), encoding="utf-8")
            os.utime(settings, ns=(1, 10**18))
        calls.append(1)
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(setup_h2t.tempfile, "mkstemp", claude_code_saves_meanwhile)

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result["status"] == "written"
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "model": "x",
        "theme": "dark",
        "env": {"H2T_MACHINE_NAME": "mac"},
    }
    assert sorted(p.name for p in settings.parent.iterdir()) == ["settings.json"]


def _history(renamed_host, *machines):
    for machine in machines:
        (renamed_host / "sessions" / machine / "proj").mkdir(parents=True)


def test_setup_does_not_pin_a_hostname_that_drifted_from_the_history(renamed_host, monkeypatch):
    # #517: the MacBook's history sits in macbook-pro-3/ while the hostname now reads Mac.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    _history(renamed_host, "macbook-pro-3")

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result["status"] == "needs_choice"
    assert result["today"] == "mac"
    assert result["candidates"] == ["macbook-pro-3"]
    assert not _settings(renamed_host).exists()


def test_setup_pins_today_s_name_when_its_folder_exists(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    _history(renamed_host, "automata", "mac")

    result = setup_h2t.ensure_machine_name(renamed_host)

    assert result["status"] == "written"
    assert result["value"] == "mac"


def test_setup_pins_the_name_it_is_given(renamed_host, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    _history(renamed_host, "macbook-pro-3")

    result = setup_h2t.ensure_machine_name(renamed_host, name="macbook-pro-3")

    assert result["status"] == "written"
    assert json.loads(_settings(renamed_host).read_text(encoding="utf-8")) == {
        "env": {"H2T_MACHINE_NAME": "macbook-pro-3"},
    }


def test_setup_command_takes_the_chosen_name(renamed_host, monkeypatch, capsys):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(setup_h2t, "_home", lambda: renamed_host)
    monkeypatch.setattr(setup_h2t, "doctor", lambda: {"status": "ok"})
    _history(renamed_host, "macbook-pro-3")

    assert setup_h2t.main(["setup", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["machine_name"]["status"] == "needs_choice"

    assert setup_h2t.main(["setup", "--machine-name", "macbook-pro-3", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["machine_name"]["value"] == "macbook-pro-3"


def test_the_setup_skill_reaches_the_pin():
    # #518: the pin lived only in the `setup` subcommand, which SKILL.md never ran.
    skill = (SETUP_SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "h2t-ops setup setup --json" in skill
    assert "needs_choice" in skill
    assert "--machine-name" in skill
