"""The structure guard must run on a POSIX box with no `python` on PATH (#331).

`hooks-handlers/structure-guard` exec'd bare `python`. Windows has that command, macOS
and most Linux distros deliberately do not ship it after the Python 2 EOL, so on
macbook-pro-3 the hook died with `exec: python: not found` on every Edit — the naming
conventions were never enforced there, and the failure surfaced only as hook noise.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDLERS = REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers"
GUARD = HANDLERS / "structure-guard"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="bash wrapper; POSIX only")

# A bare `python` call: not part of python3, not a path or a variable expansion.
_BARE_PYTHON = re.compile(r"(?<![\w./$-])python(?![\w.3-])")


def _shell_wrappers():
    for path in sorted(HANDLERS.iterdir()):
        if path.is_dir() or path.suffix == ".py":
            continue
        head = path.read_text(encoding="utf-8").splitlines()[:1]
        if head and "bash" in head[0]:
            yield path


def test_no_hook_wrapper_calls_bare_python():
    """Ratchet: the next wrapper must not reintroduce the same assumption."""
    offenders = []
    for path in _shell_wrappers():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if _BARE_PYTHON.search(code):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "bare `python` is absent on macOS/Linux:\n" + "\n".join(offenders)


@pytest.fixture
def posix_box(tmp_path):
    """A PATH with python3 but no python, and a HOME with no ~/.h2t/venv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    for tool in ("dirname", "uname", "env"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    env = dict(os.environ)
    env.update(PATH=str(bin_dir), HOME=str(tmp_path / "home"))
    env.pop("H2T_PYTHON", None)
    return env


@pytest.fixture
def guarded_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".h2t").mkdir(parents=True)
    (repo / ".h2t" / "structure.yaml").write_text(
        "forbidden_patterns:\n  - \"tmp_*\"\n", encoding="utf-8"
    )
    (repo / "docs").mkdir()
    return repo


def _run_guard(env, repo, payload):
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True, encoding="utf-8",
        cwd=repo,
        env=env,
    )


def test_guard_blocks_a_forbidden_name_without_python_on_path(posix_box, guarded_repo):
    result = _run_guard(posix_box, guarded_repo, {
        "tool_name": "Write",
        "tool_input": {"file_path": str(guarded_repo / "docs" / "tmp_scratch.md"), "content": ""},
    })
    assert "not found" not in result.stderr, result.stderr
    assert result.returncode == 2, f"rc={result.returncode} stderr={result.stderr!r}"
    assert "BLOCKED" in result.stderr


def test_guard_allows_a_clean_name_without_python_on_path(posix_box, guarded_repo):
    result = _run_guard(posix_box, guarded_repo, {
        "tool_name": "Write",
        "tool_input": {"file_path": str(guarded_repo / "docs" / "notes.md"), "content": ""},
    })
    assert result.returncode == 0, f"stderr={result.stderr!r}"
