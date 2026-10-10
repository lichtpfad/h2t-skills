"""One machine name for session paths and the activity spool; setup pins it (#491).

macOS renames the host with the network (`MacBook-Pro-3` in the morning, `Mac` at night),
so the handoff writer, the session reader and the activity spool — each with its own copy
of the rule — split one machine's records across directories and casings.
"""
import importlib.util
import json
import platform
import sys
from pathlib import Path

import pytest

from lib.activity import writer as activity_writer
from lib.gather import sessions

REPO = Path(__file__).resolve().parents[2]
HANDOFF_WRITER = REPO / "plugins" / "h2t-core" / "skills" / "handoff" / "scripts" / "writer.py"
SETUP_DIR = REPO / "plugins" / "h2t-core" / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SETUP_DIR))

import setup_h2t  # noqa: E402


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
