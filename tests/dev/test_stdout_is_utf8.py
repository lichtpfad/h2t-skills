"""A script that writes JSON to stdout must not trust the codepage (#428).

Windows encodes a piped stdout with the ANSI codepage whatever `chcp` says. Two
severities follow, and the second is the one that hides:

- cp1252 *has* a byte for `—` (0x97), so the caller receives it and its UTF-8 decode
  raises `UnicodeDecodeError`. Loud, and traceable to the byte.
- cp1252 has *no* byte for `→` (U+2192), so `print()` itself raises `UnicodeEncodeError`
  inside the child. Measured on macOS 2026-08-27 by piping `meetgeek_cli.py --help`
  through `PYTHONIOENCODING=cp1252`: exit 1, and **zero bytes on stdout**. A caller sees
  a failed command with no report, which reads as anything at all.

The probe reproduces both without a Windows machine. It needs its own control — five of
the six scripts first probed emitted pure ASCII for the invocation used, so their green
said nothing about the defect. Only `meetgeek_cli.py` actually carried non-ASCII, and it
is what the behavioural case below runs.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = 'reconfigure(encoding="utf-8"'


def _writes_json_to_stdout(path: Path) -> bool:
    """`print(json.dumps(...))` — JSON on stdout, through the codepage."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "json.dumps" not in text:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
            continue
        for arg in node.args:
            inner = getattr(getattr(arg, "func", None), "attr", "")
            if inner == "dumps":
                return True
    return False


def _emitters() -> list[Path]:
    out = []
    for root in (ROOT / "plugins", ROOT / "lib", ROOT / "h2t_ops", ROOT / "scripts"):
        if not root.is_dir():
            continue
        out += [p for p in root.rglob("*.py")
                if "__pycache__" not in p.parts and _writes_json_to_stdout(p)]
    return sorted(out)


def test_there_are_emitters_to_check():
    """Guards the walk: an empty list would make the check below vacuous."""
    assert len(_emitters()) >= 10, [str(p) for p in _emitters()]


@pytest.mark.parametrize(
    "path", _emitters(), ids=lambda p: str(p.relative_to(ROOT))
)
def test_every_json_emitter_forces_utf8(path):
    text = path.read_text(encoding="utf-8")
    assert GUARD in text, (
        f"{path.relative_to(ROOT)} prints json.dumps without forcing UTF-8 on stdout.\n"
        'Add at the top of main(): if hasattr(sys.stdout, "reconfigure"): '
        'sys.stdout.reconfigure(encoding="utf-8")'
    )


def test_a_real_run_survives_a_cp1252_pipe():
    """The behavioural half, on the one script whose --help carries `—` and `→`.

    Without the guard this exits 1 with an empty stdout; the assertion is on both, so a
    script that starts printing nothing would fail here too.
    """
    script = ROOT / "plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, encoding="utf-8", timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"}, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr[-400:]
    assert "—" in result.stdout and "→" in result.stdout, repr(result.stdout[:200])
