import sys
from contextlib import contextmanager
from pathlib import Path

from h2t_ops import activity_log_entry, gather_entry, handoff_entry, plugin_entrypoints


@contextmanager
def _isolated_gather_modules():
    """Load the plugin gather.py against its OWN lib copy, deterministically.

    The repo-root packaged `lib/gather` and the plugin `plugins/h2t-core/lib/gather`
    have drifted (#283): the plugin gather.py imports `find_latest_session_index`, which
    exists only in the plugin copy. In a whole-suite `pytest tests/` run an earlier test
    can leave the (stale) root `gather` in sys.modules first, so the plugin script would
    resolve that copy and raise ImportError. This snapshot / evict / restore forces a
    fresh import (the plugin script puts its own lib on sys.path[0]). Runtime is
    unaffected — the real `h2t-gather` process starts clean; this only removes a
    test-ordering false failure. The staleness itself is inert (no runtime code that runs
    against root `lib/gather` needs the missing symbol).
    """
    def _gather_keys():
        return [n for n in sys.modules if n == "gather" or n.startswith("gather.")]

    saved = {name: sys.modules[name] for name in _gather_keys()}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in _gather_keys():
            del sys.modules[name]
        sys.modules.update(saved)


def test_plugin_script_paths_exist():
    gather_path = plugin_entrypoints.plugin_script_path("skills/session-start/scripts/gather.py")
    activity_path = plugin_entrypoints.plugin_script_path("lib/activity/writer.py")
    assert gather_path.is_file()
    assert activity_path.is_file()


def test_load_plugin_module_exposes_main():
    with _isolated_gather_modules():
        module = plugin_entrypoints.load_plugin_module("skills/session-start/scripts/gather.py")
    assert callable(module.main)


def test_handoff_plugin_script_path_exists():
    handoff_path = plugin_entrypoints.plugin_script_path("skills/handoff/scripts/writer.py")
    assert handoff_path.is_file()


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


def test_handoff_entry_delegates_to_writer_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(handoff_entry, "run_plugin_main", fake_run)
    assert handoff_entry.main() == 0
    assert calls == ["skills/handoff/scripts/writer.py"]


def test_session_start_skill_uses_installable_entrypoints():
    skill_path = Path("plugins/h2t-core/skills/session-start/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-gather" in text
    assert "command -v h2t-activity-log" in text
    assert 'source "${CLAUDE_PLUGIN_ROOT}/scripts/resolve-h2t-python.sh"' in text
    assert "resolve_h2t_python ||" in text
    assert 'h2t-gather --cwd "$(pwd)" --briefing-only' in text
    assert "h2t-activity-log start \\" in text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py" not in text
    assert "${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py" not in text


def test_handoff_skill_uses_installable_entrypoint():
    skill_path = Path("plugins/h2t-core/skills/handoff/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-handoff" in text
    assert 'source "${CLAUDE_PLUGIN_ROOT}/scripts/resolve-h2t-python.sh"' in text
    assert "resolve_h2t_python ||" in text
    assert "h2t-handoff write \\" in text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py" not in text
