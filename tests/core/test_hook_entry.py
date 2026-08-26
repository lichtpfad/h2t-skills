"""A hook written into a project's settings.json must resolve when it fires.

`${CLAUDE_PLUGIN_ROOT}` exists only for the plugin's own hooks.json. scaffold-project
writes into somebody else's `.claude/settings.json`, which is normally committed and
travels to other clones and other operating systems.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_CALL = ("import sys; from h2t_ops.hook_entry import main; "
         "sys.argv=['h2t-hook', *{args!r}]; raise SystemExit(main())")


def _run(plugin_root, *args):
    return subprocess.run(
        [sys.executable, "-c", _CALL.format(args=list(args))],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        env={**os.environ, "H2T_PLUGIN_ROOT": str(plugin_root)},
    )


def _handler(plugin_root, name, body):
    handlers = Path(plugin_root) / "hooks-handlers"
    handlers.mkdir(parents=True, exist_ok=True)
    (handlers / name).write_text(body, encoding="utf-8")
    return handlers / name


def test_hook_entry_runs_the_handler_the_resolver_finds(tmp_path):
    root = tmp_path / "plugin"
    _handler(root, "probe", "#!/usr/bin/env bash\necho RAN-PROBE\n")
    result = _run(root, "probe")
    assert result.returncode == 0, result.stderr
    assert "RAN-PROBE" in result.stdout


def test_a_python_handler_is_not_run_under_bash(tmp_path):
    """hooks.json hardcodes `bash`, but the two handlers scaffold-project writes are
    `#!/usr/bin/env python3`. Under bash they are a syntax error, not a fallback."""
    root = tmp_path / "plugin"
    _handler(root, "pyprobe", "#!/usr/bin/env python3\nprint('RAN-PY')\n")
    result = _run(root, "pyprobe")
    assert result.returncode == 0, result.stderr
    assert "RAN-PY" in result.stdout


def test_the_handlers_exit_code_is_passed_through(tmp_path):
    root = tmp_path / "plugin"
    _handler(root, "fails", "#!/usr/bin/env bash\nexit 7\n")
    assert _run(root, "fails").returncode == 7


def test_arguments_reach_the_handler(tmp_path):
    root = tmp_path / "plugin"
    _handler(root, "echoes", '#!/usr/bin/env bash\necho "GOT:$1"\n')
    result = _run(root, "echoes", "--cwd")
    assert "GOT:--cwd" in result.stdout, result.stdout


def test_stdin_reaches_the_handler(tmp_path):
    """Hooks are fed their event as JSON on stdin; a launcher that swallows it is useless."""
    root = tmp_path / "plugin"
    _handler(root, "reads", "#!/usr/bin/env bash\ncat\n")
    result = subprocess.run(
        [sys.executable, "-c", _CALL.format(args=["reads"])],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", input='{"hook":"event"}', check=False,
        env={**os.environ, "H2T_PLUGIN_ROOT": str(root)},
    )
    assert '{"hook":"event"}' in result.stdout, result.stdout


def test_a_missing_handler_exits_5_and_names_what_it_tried(tmp_path):
    result = _run(tmp_path, "nope")
    assert result.returncode == 5
    assert "hooks-handlers/nope" in result.stderr


def test_no_handler_name_is_a_usage_error(monkeypatch):
    from h2t_ops.hook_entry import main
    monkeypatch.setattr(sys, "argv", ["h2t-hook"])
    assert main() == 2


@pytest.mark.parametrize("shebang", ["#!/usr/bin/env bash\n", "#!/bin/sh\n"])
def test_a_shell_shebang_selects_that_shell(tmp_path, shebang):
    from h2t_ops.hook_entry import interpreter_for
    p = tmp_path / "h"
    p.write_text(shebang + "true\n", encoding="utf-8")
    assert Path(interpreter_for(p)[0]).stem in {"bash", "sh"}


@pytest.mark.parametrize("shebang", ["#!/usr/bin/env python3\n", "#!/usr/bin/python\n"])
def test_a_python_shebang_never_resolves_to_a_missing_name(tmp_path, shebang):
    """On Windows there is usually no `python3` on PATH, only `python.exe`. Falling back
    to the literal name would break the hook on exactly the machine class this exists for."""
    from h2t_ops.hook_entry import interpreter_for
    p = tmp_path / "h"
    p.write_text(shebang + "pass\n", encoding="utf-8")
    resolved = interpreter_for(p)[0]
    assert Path(resolved).is_file(), f"{resolved} is not an executable file"
