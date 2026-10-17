"""The 3.x handler and `h2t-hook <name>` decide the same on every recorded case.

The round-trip seam (.claude/rules/verification.md): both run as subprocesses on the same
case, each in its own copy of the working tree. The old one is the bash handler from
plugins/h2t-core/hooks-handlers with `H2T_PYTHON` set to this interpreter; the new one is
`python -m h2t_ops.hook_entry <name>`, the code behind the `h2t-hook` console script.
Compared: block or not, and the text, once each side's envelope is taken off.

Where the port changed what a reader gets on purpose, the change is listed in
`DECLARED` and asserted as such, not skipped. Task 12 deletes the old handlers and this
test with them.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from h2t_ops import hooks
from tests.hooks import hook_cases as hc

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(
    os.name == "nt" or BASH is None,
    reason="the 3.x handlers are bash; their own tests are POSIX-only too")

CASES = hc.all_cases()

# Port decisions a reader can see. Anything else that differs is a defect.
DECLARED = {
    # 3.x printed plain stdout on Stop, shown in transcript mode only; now the log alone.
    "grade-guard": "plain stdout -> log only",
    # 3.x printed plain stdout on Stop, shown in transcript mode only; now the log alone.
    "plain-guard": "plain stdout -> log only",
}


def _path_without(name: str) -> str:
    """PATH without a real `name`: the 3.x handler prefers a global h2t-gather, which may
    be another version than this checkout."""
    return os.pathsep.join(entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                           if entry and not (Path(entry) / name).exists())


def _fake_gh(where: Path, view: dict) -> None:
    where.mkdir(parents=True, exist_ok=True)
    answer = where / "view.json"
    answer.write_text(json.dumps(view), encoding="utf-8")
    gh = where / "gh"
    gh.write_text(f'#!/bin/sh\ncat "{answer}"\n', encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)


def _run(side: str, name: str, body: dict, tmp_path: Path):
    # One directory name on both sides: detect_project derives the project id from it.
    root = tmp_path / side / "work"
    home = tmp_path / side / "home"
    tmpdir = tmp_path / side / "tmp"
    home.mkdir(parents=True)
    tmpdir.mkdir()
    event = hc.materialize(body, root)
    env = {k: v for k, v in os.environ.items() if k not in hc.ISOLATED_ENV}
    env.update(HOME=str(home), TMPDIR=str(tmpdir), PATH=_path_without("h2t-gather"),
               H2T_PYTHON=sys.executable, CLAUDE_PLUGIN_ROOT=str(hc.PLUGIN),
               H2T_PLUGIN_ROOT=str(hc.PLUGIN), PYTHONDONTWRITEBYTECODE="1")
    if "gh_view" in body:
        _fake_gh(tmp_path / f"{side}-bin", body["gh_view"])
        env["PATH"] = str(tmp_path / f"{side}-bin") + os.pathsep + env["PATH"]
    if side == "old":
        command = [BASH, str(hc.PLUGIN / "hooks-handlers" / name)]
    else:
        command = [sys.executable, "-m", "h2t_ops.hook_entry", name]
    done = subprocess.run(command, input=json.dumps(event).encode(), capture_output=True,
                          cwd=root, env=env, timeout=120)
    return root, home, done


def _decode(done) -> tuple[bool, str, str, str]:
    """(block, model text, human text, plain stdout) — the envelope taken off."""
    out = done.stdout.decode("utf-8")
    if done.returncode == 2:
        return True, done.stderr.decode("utf-8").strip(), "", ""
    assert done.returncode == 0, (done.returncode, done.stderr.decode("utf-8", "replace"))
    if not out.strip():
        return False, "", "", ""
    try:
        env = json.loads(out)
    except json.JSONDecodeError:
        return False, "", "", out.strip()
    model = (env.get("hookSpecificOutput") or {}).get("additionalContext", "")
    return False, model, env.get("systemMessage", ""), ""


def _normal(text: str, root: Path) -> str:
    # The working tree, then the side's directory (its HOME and TMPDIR live there).
    for path, mark in ((root, "{tmp}"), (root.parent, "{side}")):
        for spelling in {str(path.resolve()), str(path)}:
            text = text.replace(spelling, mark)
    # The 3.x fallback names the script it ran; the package runs h2t-gather's code.
    return text.replace("GATHER_ERROR: gather.py failed.", "GATHER_ERROR: h2t-gather failed.")


def _gather_parts(text: str) -> tuple[str, dict | None]:
    if hc.META_SEP not in text:
        return text, None
    briefing, raw = text.rsplit(hc.META_SEP, 1)
    meta = json.loads(raw)
    meta.pop("gather_ms", None)
    return briefing, meta


@pytest.mark.parametrize("case", CASES, ids=[hc.case_id(c) for c in CASES])
def test_old_handler_and_package_module_decide_the_same(case, tmp_path):
    name, _, path = case
    # Otherwise `h2t-hook <name>` falls through to the 3.x handler and compares it with itself.
    assert name in hooks.HANDLERS, name
    body = hc.load(path)
    old_root, old_home, old = _run("old", name, body, tmp_path)
    new_root, new_home, new = _run("new", name, body, tmp_path)
    o_block, o_model, o_human, o_plain = _decode(old)
    n_block, n_model, n_human, n_plain = _decode(new)
    o_model, o_human, o_plain = (_normal(t, old_root) for t in (o_model, o_human, o_plain))
    n_model, n_human, n_plain = (_normal(t, new_root) for t in (n_model, n_human, n_plain))

    assert n_block == o_block
    assert n_plain == "", "the package never prints outside an envelope"

    if DECLARED.get(name) == "plain stdout -> log only":
        assert (n_model, n_human) == ("", "")
        hc.check_log(body, new_home, name)

        def rows(home, root):
            return [_normal(json.dumps({k: v for k, v in row.items() if k != "ts"}), root)
                    for row in hc.log_rows(home, name)]
        if name == "plain-guard":  # 3.x logged too; grade-guard's log is new in the port
            assert rows(new_home, new_root) == rows(old_home, old_root)
        assert o_plain == hc.load(path).get("plain_stdout_3x", ""), "3.x printed this"
    elif name.startswith("gather-") and hc.META_SEP in o_model + o_human:
        o_brief, o_meta = _gather_parts(o_model or o_human)
        n_brief, n_meta = _gather_parts(n_model or n_human)
        assert (bool(n_model), bool(n_human)) == (bool(o_model), bool(o_human)), "channel"
        assert n_brief == o_brief
        # The two fields the port adds (spec §6.3); everything else as 3.x had it.
        assert n_meta.pop("cwd") == "{tmp}" and n_meta.pop("at")
        assert n_meta == o_meta
    else:
        assert (n_model, n_human) == (o_model, o_human)
        assert o_plain == ""

    for rel in body.get("after") or {}:
        assert (new_root / rel).read_text(encoding="utf-8") == \
            (old_root / rel).read_text(encoding="utf-8"), rel
