from pathlib import Path

from h2t_ops import activity_log_entry, gather_entry, plugin_entrypoints


def test_plugin_script_paths_exist():
    gather_path = plugin_entrypoints.plugin_script_path("skills/session-start/scripts/gather.py")
    activity_path = plugin_entrypoints.plugin_script_path("lib/activity/writer.py")
    assert gather_path.is_file()
    assert activity_path.is_file()


def test_load_plugin_module_exposes_main():
    module = plugin_entrypoints.load_plugin_module("skills/session-start/scripts/gather.py")
    assert callable(module.main)


def test_gather_entry_delegates_to_session_start_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(gather_entry, "run_plugin_main", fake_run)
    assert gather_entry.main() == 0
    assert calls == ["skills/session-start/scripts/gather.py"]


def test_activity_log_entry_delegates_to_writer_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(activity_log_entry, "run_plugin_main", fake_run)
    assert activity_log_entry.main() == 0
    assert calls == ["lib/activity/writer.py"]


def test_session_start_skill_uses_installable_entrypoints():
    skill_path = Path("plugins/h2t-core/skills/session-start/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-gather" in text
    assert "command -v h2t-activity-log" in text
    assert 'h2t-gather --cwd "$(pwd)" --format-briefing' in text
    assert "h2t-activity-log start \\" in text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py" not in text
    assert "${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py" not in text
