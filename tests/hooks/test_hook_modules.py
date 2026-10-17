"""Each recorded event gets its recorded Reply from the module, in-process (spec §2.8).

The cases are data: tests/fixtures/hooks/<name>/<Event>.<case>.json, described in
hook_cases.py. A case for a name outside HANDLERS fails, so a fixture cannot outlive its
handler, and a handler with no case fails test_every_handler_has_a_recorded_case.
"""
from __future__ import annotations

import tempfile

import pytest

from h2t_ops import hooks
from tests.hooks import hook_cases as hc

CASES = hc.all_cases()


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A private HOME, TMPDIR and working tree; the developer's h2t settings unset."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for name in hc.ISOLATED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("H2T_PLUGIN_ROOT", str(hc.PLUGIN))  # detect_project.py, until Task 12
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))  # the gather lock
    root = tmp_path / "work"
    root.mkdir()
    monkeypatch.chdir(root)
    return home, root


def _patch_providers(monkeypatch, name: str, body: dict, home):
    """Stand-ins for the processes a hook would ask: gh, PowerShell, taskkill."""
    if name == "plan-closer":
        from h2t_ops.hooks import plan_closer
        view = body.get("gh_view") or {}
        monkeypatch.setattr(plan_closer, "_pr_view", lambda root, number: view)
    if name == "session-end-reap-codex":
        from h2t_ops.hooks import reap_codex
        # Never enumerate, let alone kill, the real processes of the machine running tests.
        monkeypatch.setattr(reap_codex, "_list_brokers", lambda: [])
        monkeypatch.setattr(reap_codex, "_kill", lambda pid: pytest.fail(f"kill {pid}"))
    if name in ("grade-guard", "plain-guard"):
        import importlib
        module = importlib.import_module(f"h2t_ops.hooks.{name.replace('-', '_')}")
        # A module constant, resolved at import from the real HOME.
        monkeypatch.setattr(module, "LOG_PATH", home / ".h2t" / "logs" / f"{name}.jsonl")


@pytest.mark.parametrize("case", CASES, ids=[hc.case_id(c) for c in CASES])
def test_recorded_event_gets_recorded_reply(case, box, monkeypatch):
    name, _, path = case
    assert name in hooks.HANDLERS, f"fixture for {name!r}, which HANDLERS does not register"
    home, root = box
    body = hc.load(path)
    event = hc.materialize(body, root)
    _patch_providers(monkeypatch, name, body, home)

    reply = hooks.HANDLERS[name](event)

    hc.check_reply(hc.expected(body, root), reply.text, reply.block, reply.notice)
    hc.check_after(body, root)
    hc.check_log(body, home, name)


def test_every_handler_has_a_recorded_case():
    """The `Command` entries take no event; their scenarios are test_command_hooks.py."""
    recorded = {name for name, _, _ in CASES}
    events = {name for name, handle in hooks.HANDLERS.items()
              if not isinstance(handle, hooks.Command)}
    assert len(events) >= 9
    assert events <= recorded, events - recorded


def test_the_gather_lock_skips_a_second_run_in_the_same_directory(box):
    _, root = box
    event = {"hook_event_name": "PreToolUse", "tool_input": {"skill": "h2t-core:handoff"},
             "cwd": str(root)}
    first = hooks.HANDLERS["gather-on-skill"](event)
    assert first.text.startswith("BRIEFING:")
    assert hooks.HANDLERS["gather-on-skill"](event).text == ""
    other = root / "other"
    other.mkdir()
    again = hooks.HANDLERS["gather-on-skill"]({**event, "cwd": str(other)})
    assert again.text.startswith("BRIEFING:"), "a run in one directory silenced another"


def test_a_failed_gather_does_not_lock_the_retry(box):
    _, root = box
    event = {"hook_event_name": "PreToolUse", "tool_input": {"skill": "h2t-core:handoff"},
             "cwd": str(root / "later")}
    assert hooks.HANDLERS["gather-on-skill"](event).text.startswith("GATHER_ERROR")
    (root / "later").mkdir()
    assert hooks.HANDLERS["gather-on-skill"](event).text.startswith("BRIEFING:")


def test_gather_output_never_reaches_the_hook_stdout(box, capfdbinary):
    """The hook's stdout carries the envelope only; gather prints through sys.stdout.buffer.

    capfd, not capsys: a write to file descriptor 1 (a subprocess that inherits it, a
    print before the swap) would bypass sys.stdout and still corrupt the envelope.
    """
    _, root = box
    reply = hooks.HANDLERS["gather-on-skill"](
        {"hook_event_name": "PreToolUse", "tool_input": {"skill": "handoff"}, "cwd": str(root)})
    assert reply.text.startswith("BRIEFING:")
    captured = capfdbinary.readouterr()
    assert captured.out == b"" and captured.err == b""


def test_stamp_meta_keeps_a_meta_that_is_not_json():
    from h2t_ops.hooks.gather import stamp_meta
    assert stamp_meta("BRIEFING:\nx\n\nGATHER_META: not json", "/w", "t") == \
        "BRIEFING:\nx\n\nGATHER_META: not json"
    assert stamp_meta("no meta at all", "/w", "t") == "no meta at all"
    stamped = stamp_meta('BRIEFING:\nx\n\nGATHER_META: {"machine": "m"}', "/w", "t")
    assert stamped == 'BRIEFING:\nx\n\nGATHER_META: {"machine": "m", "cwd": "/w", "at": "t"}'


def test_reap_off_windows_never_lists_processes(monkeypatch):
    from h2t_ops.hooks import reap_codex
    monkeypatch.setattr(reap_codex.sys, "platform", "darwin")
    monkeypatch.setattr(reap_codex, "_list_brokers", lambda: pytest.fail("listed processes"))
    assert reap_codex.handle({"hook_event_name": "SessionEnd", "cwd": "C:/w"}).text == ""


def test_reap_on_windows_kills_own_and_orphan_and_spares_a_live_sibling(monkeypatch, tmp_path):
    """The process-killing path, with PowerShell and taskkill stood in for."""
    from h2t_ops.hooks import reap_codex
    live = tmp_path / "sibling"
    live.mkdir()
    brokers = [{"pid": 11, "cwd": "C:/Work/Own/"},          # this session, other spelling
               {"pid": 12, "cwd": str(tmp_path / "gone")},  # orphan: cwd no longer exists
               {"pid": 13, "cwd": str(live)},               # live sibling: must survive
               {"pid": 14, "cwd": ""}]                      # no cwd: cannot be attributed
    killed = []
    monkeypatch.setattr(reap_codex.sys, "platform", "win32")
    monkeypatch.setattr(reap_codex, "_list_brokers", lambda: brokers)
    monkeypatch.setattr(reap_codex, "_kill", lambda pid: killed.append(pid) or True)
    reply = reap_codex.handle({"hook_event_name": "SessionEnd", "cwd": "c:\\work\\own"})
    assert sorted(killed) == [11, 12]
    assert reply.text == ("codex-reaper: убито брокеров — 1 этой сессии, "
                          "1 осиротевш(их) (мёртвая cwd)")
    assert not reply.block


def test_reap_says_nothing_when_no_kill_succeeded(monkeypatch, tmp_path):
    from h2t_ops.hooks import reap_codex
    monkeypatch.setattr(reap_codex.sys, "platform", "win32")
    monkeypatch.setattr(reap_codex, "_list_brokers",
                        lambda: [{"pid": 12, "cwd": str(tmp_path / "gone")}])
    monkeypatch.setattr(reap_codex, "_kill", lambda pid: False)
    assert reap_codex.handle({"hook_event_name": "SessionEnd"}).text == ""
