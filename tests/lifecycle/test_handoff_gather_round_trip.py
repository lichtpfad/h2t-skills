"""The lifecycle commands, run as processes, against the package code.

Two contracts. A handoff written by `h2t-handoff write` must be the "Previous Session" the
next `h2t-gather --briefing-only` shows — writer and reader each have their own tests, and
the seam between them is where #377 and #491 lived. And every call form the 3.x plugins
use (tests/release/legacy_call_forms.json) must still parse: a 3.x session keeps calling
the 4.x CLI until it reloads (spec §8).

SAFETY RULE for everything in this file: no process may touch the real home. Each one runs
with HOME, USERPROFILE, CLAUDE_CONFIG_DIR and CODEX_HOME inside tmp_path — the session
records and the activity spool live under HOME's ~/.h2t/records — and with eval telemetry off. The legacy forms are not
executed at all — they are parsed and the process stops before main() can act on them,
because some of them create repositories (`h2t-scaffold-project github` calls `gh repo
create`) or edit the h2t config. Do not "simplify" that into running them.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORMS = json.loads((ROOT / "tests/release/legacy_call_forms.json").read_text(encoding="utf-8"))

ENTRY_MODULES = {
    "h2t-gather": "h2t_ops.gather_entry",
    "h2t-handoff": "h2t_ops.handoff_entry",
    "h2t-activity-log": "h2t_ops.activity_log_entry",
    "h2t-project-audit-scan": "h2t_ops.project_audit_scan_entry",
    "h2t-project-audit-report": "h2t_ops.project_audit_report_entry",
    "h2t-project-register": "h2t_ops.project_register_entry",
    "h2t-scaffold-project": "h2t_ops.scaffold_project_entry",
}


def _console_script(name: str) -> list[str]:
    """The installed console script beside this interpreter, else the same main() via -c.

    Only the interpreter's own bin directory is searched. `shutil.which` would find a
    globally installed h2t-handoff first on a developer machine — a different checkout's
    code, and a green test about the wrong program.
    """
    bindir = Path(sys.executable).parent
    for candidate in (bindir / name, bindir / f"{name}.exe",
                      bindir / "Scripts" / f"{name}.exe", bindir / "Scripts" / name):
        if candidate.is_file():
            return [str(candidate)]
    module = ENTRY_MODULES[name]
    return [sys.executable, "-c", f"import sys; from {module} import main; sys.exit(main())"]


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for var in ("H2T_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        env.pop(var, None)
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        CLAUDE_CONFIG_DIR=str(home / ".claude"),
        CODEX_HOME=str(home / ".codex"),
        H2T_MACHINE_NAME="test-machine",
        H2T_EVALS_MODE="off",
        PYTHONIOENCODING="utf-8",
    )
    return env


def _run(argv: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=cwd, check=False, timeout=120)


def _briefing(env: dict[str, str], work: Path) -> tuple[str, dict]:
    result = _run([*_console_script("h2t-gather"), "--cwd", str(work), "--briefing-only"],
                  env, work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("BRIEFING:"), result.stdout[:200]
    briefing, _, meta = result.stdout.partition("\n\nGATHER_META: ")
    return briefing, json.loads(meta)


def test_gather_shows_the_handoff_just_written(tmp_path):
    env = _isolated_env(tmp_path)
    # Outside git on purpose: no remote, no `gh` calls, nothing live in the briefing.
    work = tmp_path / "checkout"
    work.mkdir()

    before, meta = _briefing(env, work)
    project = meta["project"]["id"]
    session_id = "round-trip-2026-10-17"
    assert "### Previous Session" not in before, "control: no record before the write"

    written = _run([*_console_script("h2t-handoff"), "write", "--session-id", session_id,
                    "--project", project, "--domain", "dev",
                    "--what-done", "wrote the round-trip test",
                    "--what-remains", "read it back"], env, work)
    assert written.returncode == 0, written.stderr
    record = json.loads(written.stdout)
    assert Path(record["spool"]).is_relative_to(tmp_path), record
    records = tmp_path / "home" / ".h2t" / "records"
    assert Path(record["spool"]) == records / "activity" / "test-machine.jsonl", record
    assert Path(record["markdown"]).is_relative_to(records / "sessions" / "test-machine"), record

    md = Path(record["markdown"])
    assert Path(record["latest"]) == md and not (md.parent / "latest.json").exists()   # R10

    after, meta = _briefing(env, work)
    assert "### Previous Session  (test-machine, сегодня)" in after, after[:600]
    assert "wrote the round-trip test" in after, after[:600]
    assert "read it back" in after, after[:600]
    assert meta["latest_session"]["markdown_path"] == str(md)


def test_a_broken_record_beside_it_does_not_hide_the_session(tmp_path):
    """Review Focus 3 end to end: a hand-edited md with broken frontmatter is skipped by
    the index and session-start still shows the good record."""
    env = _isolated_env(tmp_path)
    work = tmp_path / "checkout"
    work.mkdir()
    _, meta = _briefing(env, work)
    project = meta["project"]["id"]
    written = _run([*_console_script("h2t-handoff"), "write", "--session-id", "good-one",
                    "--project", project, "--domain", "dev", "--what-done", "the good record",
                    "--what-remains", "- [ ] more"], env, work)
    assert written.returncode == 0, written.stderr
    md = Path(json.loads(written.stdout)["markdown"])
    (md.parent / "edited-by-hand.md").write_bytes(b"---\nsession_id: [unclosed\n---\nbody\n")

    after, meta = _briefing(env, work)
    assert "the good record" in after, after[:600]
    assert meta["sessions"] == [str(md)]


# Values for the placeholders in the inventory. Only `--type` and `--stack` of
# scaffold-project have `choices`; any other string parses.
_PLACEHOLDER_VALUES = {"{type}": "code-local", "{reg_type}": "code-local", "{stack}": "python"}
_PATH_PLACEHOLDERS = {"<dir>", "<config-root>", "<repo_path>", "$CONFIG_ROOT", "$PROJECTS_YAML",
                      "{project_path}", "{base_dir}"}

# Parse, then stop. argparse reports an unknown flag or an invalid choice with exit 2
# before this replacement returns; a form that parses exits 0 with a marker, before
# main() gets to act on the arguments.
_PARSE_ONLY = (
    "import argparse, sys\n"
    "_real = argparse.ArgumentParser.parse_args\n"
    "def _stop(self, *a, **k):\n"
    "    _real(self, *a, **k)\n"
    "    print('PARSED-OK'); sys.exit(0)\n"
    "argparse.ArgumentParser.parse_args = _stop\n"
    "module, prog = sys.argv[1], sys.argv[2]\n"
    "sys.argv = [prog, *sys.argv[3:]]\n"
    "main = __import__(module, fromlist=['main']).main\n"
    "sys.exit(main())\n"
)


def _concrete(argv: list[str], tmp_path: Path) -> list[str]:
    out = []
    for arg in argv:
        if arg in _PLACEHOLDER_VALUES:
            out.append(_PLACEHOLDER_VALUES[arg])
        elif arg in _PATH_PLACEHOLDERS:
            out.append(str(tmp_path / "placeholder"))
        elif arg.startswith(("{", "<", "$")):
            out.append("x")
        else:
            out.append(arg)
    return out


def _parse_only(argv: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    env = _isolated_env(tmp_path)
    return _run([sys.executable, "-c", _PARSE_ONLY, ENTRY_MODULES[argv[0]], argv[0],
                 *_concrete(argv[1:], tmp_path)], env, tmp_path)


LEGACY = [f for f in FORMS if f["argv"][0] in ENTRY_MODULES]


def test_inventory_has_forms_for_every_converted_command():
    assert {f["argv"][0] for f in LEGACY} == set(ENTRY_MODULES)


@pytest.mark.parametrize("form", LEGACY, ids=[f["source"] for f in LEGACY])
def test_legacy_call_form_still_parses(form, tmp_path):
    result = _parse_only(form["argv"], tmp_path)
    assert "unrecognized arguments" not in result.stderr, result.stderr
    assert "invalid choice" not in result.stderr, result.stderr
    assert result.returncode == 0 and "PARSED-OK" in result.stdout, (
        result.returncode, result.stdout[-300:], result.stderr[-600:])


def test_the_parse_only_probe_catches_an_unknown_flag(tmp_path):
    """Control: without it, a probe that never reaches argparse would pass every form."""
    argv = next(f["argv"] for f in LEGACY if f["argv"][0] == "h2t-handoff")
    result = _parse_only([*argv, "--no-such-flag"], tmp_path)
    assert result.returncode == 2, (result.returncode, result.stderr[-300:])
    assert "unrecognized arguments" in result.stderr
