"""`h2t-hook <name>` resolves every name through HANDLERS, and nothing else (spec §6.2).

A hook written into a project's settings.json, or a git hook, cannot use
`${CLAUDE_PLUGIN_ROOT}`; `h2t-hook` answers it from the installed package. Dispatch to a
registered handler is tests/hooks/test_hook_dispatch.py; the 3.x command forms are
tests/hooks/test_command_hooks.py.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_CALL = ("import sys; from h2t_ops.hook_entry import main; "
         "sys.argv=['h2t-hook', *{args!r}]; raise SystemExit(main())")


def _run(cwd, *args):
    return subprocess.run(
        [sys.executable, "-c", _CALL.format(args=list(args))],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )


def test_an_unknown_name_exits_5_and_names_the_known_ones(tmp_path):
    result = _run(tmp_path, "nope")
    assert result.returncode == 5
    assert "'nope'" in result.stderr and "structure-guard" in result.stderr


def test_a_name_is_never_looked_up_on_disk(tmp_path, monkeypatch):
    """The 3.x path ran `hooks-handlers/<name>` from the plugin tree; a file of that name
    must not be reachable any more."""
    from h2t_ops import hook_entry
    assert not hasattr(hook_entry, "plugin_script_path")
    assert not hasattr(hook_entry, "interpreter_for")
    root = tmp_path / "plugin" / "hooks-handlers"
    root.mkdir(parents=True)
    (root / "probe").write_text("#!/usr/bin/env bash\necho RAN-PROBE\n", encoding="utf-8")
    monkeypatch.setenv("H2T_PLUGIN_ROOT", str(tmp_path / "plugin"))
    result = _run(tmp_path, "probe")
    assert result.returncode == 5 and "RAN-PROBE" not in result.stdout


def test_no_handler_name_is_a_usage_error(monkeypatch):
    """64, not 2: for a hook, 2 is the harness's block signal (spec §6.1, ruling R8)."""
    from h2t_ops.hook_entry import main
    monkeypatch.setattr(sys, "argv", ["h2t-hook"])
    assert main() == 64


def test_help_is_not_a_handler_name(tmp_path):
    """`--help` is what a person types first, and it was resolved as a hook name.

    Measured on a clean HOME, 2026-08-27: `h2t-hook --help` looked for
    `hooks-handlers/--help`, did not find it, and exited 5 with a not-found message — a
    correct answer to a question nobody asked. It was the only one of the nine entry
    points that failed that probe.
    """
    for flag in ("--help", "-h", "help"):
        result = _run(tmp_path, flag)
        assert result.returncode == 0, f"{flag}: rc={result.returncode} {result.stderr}"
        assert "usage: h2t-hook" in result.stdout, flag


def test_a_real_missing_handler_still_fails(tmp_path):
    """The control. Without it, "help works" and "nothing is ever looked up" look alike."""
    result = _run(tmp_path, "no-such-handler")
    assert result.returncode == 5, result.stderr
