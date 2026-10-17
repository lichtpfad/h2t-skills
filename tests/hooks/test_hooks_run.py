"""`plugins/h2t-core/hooks/run`, the bash wrapper in front of every h2t hook (spec §6.1).

The CLI is a fake: a bash script that prints known text and exits with a known code. The
fixture writes `~/.h2t/run/install.env` under a temporary HOME and a `release.env` in a
temporary plugin root, so nothing here touches the real installation.
"""
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "plugins" / "h2t-core" / "hooks" / "run"


def _release_slots():
    """scripts/release.py: the one definition of the slots a release rewrites."""
    spec = importlib.util.spec_from_file_location("release_slots", ROOT / "scripts" / "release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SLOTS = _release_slots()
BASH = shutil.which("bash")
WINDOWS = sys.platform == "win32"

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not on PATH")

FAKE = """#!/usr/bin/env bash
printf '%s' "$$" > "{pidfile}"
cat > "{stdin_copy}"
{sleep}
printf 'FAKE-OUT:%s' "$1"
printf 'FAKE-ERR:%s' "$1" >&2
exit {rc}
"""


def _p(path: Path) -> str:
    """Forward slashes: Git Bash on Windows takes C:/x, not C:\\x."""
    return path.as_posix()


class Rig:
    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.run_dir = self.home / ".h2t" / "run"
        self.plugin = tmp_path / "plugin"
        self.plugin.mkdir()
        self.script = RUN
        self.release("4.0.0")

    def release(self, version, newline="\n"):
        (self.plugin / "release.env").write_bytes(f"VERSION={version}{newline}".encode())

    def fake(self, rc=0, sleep="", where=None) -> Path:
        where = where or self.tmp / "bin"
        where.mkdir(parents=True, exist_ok=True)
        fake = where / "h2t-hook"
        fake.write_text(FAKE.format(pidfile=_p(self.tmp / "fake.pid"), stdin_copy=_p(self.tmp / "fake.stdin"),
                                    sleep=sleep, rc=rc), encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def install(self, lines, newline="\n"):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        text = newline.join(line.replace("<tmp>", _p(self.tmp)) for line in lines) + newline
        (self.run_dir / "install.env").write_bytes(text.encode("utf-8"))

    def bootstrap(self, literal):
        """What Task 13 does to the committed file: substitute the one BOOTSTRAP='...' line."""
        text = RUN.read_text(encoding="utf-8")
        assert len(re.findall(r"^BOOTSTRAP='[^']*'", text, re.M)) == 1
        text = re.sub(r"^BOOTSTRAP='[^']*'", lambda m: f"BOOTSTRAP='{literal}'", text, flags=re.M)
        self.script = self.tmp / "run"
        self.script.write_text(text, encoding="utf-8")

    def __call__(self, event, name="probe", payload=None, plugin_root=None, timeout=30, limit=None,
                 **env):
        payload = {"hook_event_name": event, "session_id": "sess-1"} if payload is None else payload
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": _p(self.home),
            "CLAUDE_PLUGIN_ROOT": _p(plugin_root or self.plugin),
            **{k: str(v) for k, v in env.items()},
        }
        for key in ("SYSTEMROOT", "TEMP", "TMP", "TMPDIR"):
            if key in os.environ:
                environment.setdefault(key, os.environ[key])
        started = time.perf_counter()
        args = [BASH, _p(self.script), name] + ([] if limit is None else [str(limit)])
        result = subprocess.run(args, input=json.dumps(payload).encode(),
                                capture_output=True, env=environment, timeout=timeout, check=False)
        result.elapsed = time.perf_counter() - started
        result.text = result.stdout.decode("utf-8")
        return result


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def _message(result):
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert list(envelope) == ["systemMessage"]
    return envelope["systemMessage"]


def _log_rows(rig):
    path = rig.home / ".h2t" / "logs" / "hooks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


CASES = [
    # (install.env lines or None, plugin_inside_editable, fake_hook_exit, event, expect)
    (None, False, 0, "SessionStart", "notice:not_installed"),
    (None, False, 0, "Stop", "silent"),
    (["STATE=updating", "VERSION=4.0.0"], False, 0, "SessionStart", "notice:not_installed"),
    (["STATE=ready", "VERSION=4.0.0", "EDITABLE_ROOT=<tmp>/checkout"], True, 0, "Stop", "ran"),
    (["STATE=ready", "VERSION=4.0.0", "EDITABLE_ROOT=<tmp>/checkout"], False, 0, "SessionStart", "notice:editable"),
    (["STATE=ready", "VERSION=4.0.0"], False, 0, "Stop", "ran"),
    (["STATE=ready", "VERSION=3.9.0"], False, 0, "SessionStart", "notice:mismatch"),
    (["STATE=ready", "VERSION=4.0.0"], False, 2, "PreToolUse", "blocked"),
    (["STATE=ready", "VERSION=4.0.0"], False, 1, "Stop", "silent+logged"),
    (["STATE=ready", "VERSION=4.0.0"], False, 1, "SessionStart", "notice:broken"),
]

NOTICE_TEXT = {
    "notice:not_installed": "CLI не установлен",
    "notice:editable": "CLI в режиме разработки",
    "notice:mismatch": "плагины 4.0.0, CLI 3.9.0",
    "notice:broken": "CLI неисправен (хук probe, код 1)",
}


@pytest.mark.parametrize("lines,inside,rc,event,expect", CASES)
def test_decision_table(rig, lines, inside, rc, event, expect):
    fake = rig.fake(rc=rc)
    plugin_root = None
    if lines is not None:
        rig.install([*lines, f"H2T_HOOK={_p(fake)}"])
    if inside:
        plugin_root = rig.tmp / "checkout" / "plugins" / "h2t-core"
        plugin_root.mkdir(parents=True)
        (plugin_root / "release.env").write_text("VERSION=0.0.0-dev\n", encoding="utf-8")
    result = rig(event, plugin_root=plugin_root)

    if expect.startswith("notice:"):
        message = _message(result)
        assert NOTICE_TEXT[expect] in message
        assert re.search(f"(?:{SLOTS.BOOTSTRAP_SLOT.pattern}) sync$", message), message
    elif expect == "silent":
        assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
    elif expect == "ran":
        assert result.returncode == 0, result.stderr
        assert result.text == "FAKE-OUT:probe"
        assert json.loads((rig.tmp / "fake.stdin").read_text(encoding="utf-8"))["hook_event_name"] == event
    elif expect == "blocked":
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr.decode() == "FAKE-ERR:probe"
    elif expect == "silent+logged":
        assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
        assert _log_rows(rig)[-1] == {"hook": "probe", "rc": 1}
    else:
        raise AssertionError(expect)


# ---- JSON safety ---------------------------------------------------------------------

BOOT = r'uvx --isolated --from "git+https://github.com/lichtpfad/h2t-skills.git@v4" h2t-setup C:\Users\x'


def test_not_installed_notice_is_valid_json_with_quotes_and_backslashes(rig):
    rig.bootstrap(BOOT)
    assert _message(rig("SessionStart")).endswith(BOOT + " sync")


def test_editable_notice_is_valid_json_when_the_root_holds_a_quote(rig):
    rig.bootstrap(BOOT)
    fake = rig.fake()
    rig.install(["STATE=ready", "VERSION=4.0.0", 'EDITABLE_ROOT=<tmp>/che"ck\\out', f"H2T_HOOK={_p(fake)}"])
    message = _message(rig("SessionStart"))
    assert 'che"ck\\out' in message
    assert BOOT in message


def test_mismatch_notice_is_valid_json_when_a_version_holds_a_quote(rig):
    rig.bootstrap(BOOT)
    rig.release('4.0"0')
    fake = rig.fake()
    rig.install(["STATE=ready", 'VERSION=3\\9"x', f"H2T_HOOK={_p(fake)}"])
    message = _message(rig("SessionStart"))
    assert 'плагины 4.0"0, CLI 3\\9"x' in message


def test_broken_notice_and_log_row_are_valid_json_when_the_name_holds_a_quote(rig):
    rig.bootstrap(BOOT)
    fake = rig.fake(rc=1)
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    assert 'хук we"ird\\name' in _message(rig("SessionStart", name='we"ird\\name'))
    assert _log_rows(rig)[-1] == {"hook": 'we"ird\\name', "rc": 1}


def test_exactly_one_bootstrap_line_and_it_is_a_bootstrap_slot():
    """release.py substitutes the one BOOTSTRAP='...' line; two lines would split it."""
    lines = SLOTS.RUN_BOOTSTRAP.findall(RUN.read_text(encoding="utf-8"))
    assert len(lines) == 1
    assert SLOTS.BOOTSTRAP_SLOT.fullmatch(lines[0][len("BOOTSTRAP='"):-1]), lines[0]


# ---- reading the two files ---------------------------------------------------------------

def test_crlf_in_install_env_and_release_env_still_matches(rig):
    fake = rig.fake()
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"], newline="\r\n")
    rig.release("4.0.0", newline="\r\n")
    result = rig("Stop")
    assert result.text == "FAKE-OUT:probe", result.stderr


def test_a_hook_path_with_a_space_and_cyrillic_runs(rig):
    fake = rig.fake(where=rig.tmp / "Users" / "Лидия Иванова" / ".local" / "bin")
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    result = rig("Stop")
    assert result.text == "FAKE-OUT:probe", result.stderr


# ---- one notice per session ------------------------------------------------------------------

def test_a_second_session_start_of_the_same_session_is_silent(rig):
    assert "не установлен" in _message(rig("SessionStart"))
    second = rig("SessionStart")
    assert (second.returncode, second.stdout) == (0, b"")
    other = rig("SessionStart", payload={"hook_event_name": "SessionStart", "session_id": "sess-2"})
    assert "не установлен" in _message(other)


def test_session_start_without_session_id_notifies_every_time(rig):
    payload = {"hook_event_name": "SessionStart"}
    for _ in range(2):
        assert "не установлен" in _message(rig("SessionStart", payload=payload))
    notified = rig.run_dir / "notified"
    assert not notified.exists() or list(notified.iterdir()) == []


def test_a_session_id_with_a_path_in_it_is_not_used_as_a_path(rig):
    payload = {"hook_event_name": "SessionStart", "session_id": "../../escape"}
    for _ in range(2):
        assert "не установлен" in _message(rig("SessionStart", payload=payload))
    assert not (rig.home / "escape").exists()


@pytest.mark.skipif(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="needs POSIX permissions and a non-root user")
@pytest.mark.parametrize("locked", ["run", "notified"])
def test_a_read_only_run_dir_notifies_on_every_session_start(rig, locked):
    rig.run_dir.mkdir(parents=True)
    if locked == "notified":
        (rig.run_dir / "notified").mkdir()
    target = rig.run_dir if locked == "run" else rig.run_dir / "notified"
    target.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        for _ in range(2):
            assert "не установлен" in _message(rig("SessionStart"))
    finally:
        target.chmod(0o755)


# ---- the watchdog --------------------------------------------------------------------------

def test_a_handler_that_overruns_is_treated_as_broken_before_the_harness_timeout(rig):
    fake = rig.fake(sleep="exec sleep 30")
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    result = rig("SessionStart", limit=1)
    assert result.elapsed < 3, result.elapsed
    assert "CLI неисправен (хук probe" in _message(result)
    assert "FAKE-OUT" not in result.text
    if not WINDOWS:  # MSYS pids are not Windows pids
        pid = int((rig.tmp / "fake.pid").read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_an_overrun_on_stop_is_silent(rig):
    fake = rig.fake(sleep="exec sleep 30")
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    result = rig("Stop", limit=1)
    assert result.elapsed < 3, result.elapsed
    assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")  # no "Terminated" line
    assert _log_rows(rig)[-1]["rc"] != 0


def test_a_fast_handler_does_not_wait_for_the_watchdog(rig):
    """capture_output reads the pipe to EOF, as the harness does. A watchdog `sleep` that
    inherited the wrapper's stdout would hold it open for the whole timeout."""
    fake = rig.fake()
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    result = rig("Stop", limit=5)
    assert result.text == "FAKE-OUT:probe"
    assert result.elapsed < 1, f"took {result.elapsed:.2f}s"


# ---- UserPromptSubmit prefilter ------------------------------------------------------------

def _ready(rig):
    fake = rig.fake()
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])


def _prompt(text):
    return {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": text}


@pytest.mark.parametrize("text", ["/h2t-core:session-start", "/handoff", "  /init-project now",
                                  "\n/h2t-core:handoff\nnotes"])
def test_a_session_slash_command_passes_the_prefilter(rig, text):
    _ready(rig)
    result = rig("UserPromptSubmit", payload=_prompt(text))
    assert result.text == "FAKE-OUT:probe", result.stderr


@pytest.mark.parametrize("text", ["привет", "сделай /handoff", "/dev-overview",
                                  "<task-notification> plugins/h2t-core/skills/handoff"])
def test_a_plain_prompt_never_reaches_the_handler(rig, text):
    _ready(rig)
    result = rig("UserPromptSubmit", payload=_prompt(text))
    assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
    assert not (rig.tmp / "fake.pid").exists()


@pytest.mark.skipif(WINDOWS or shutil.which("mkfifo") is None, reason="needs mkfifo")
def test_a_plain_prompt_reads_no_file(rig):
    """Both files are FIFOs with no writer: opening either blocks until the timeout."""
    rig.run_dir.mkdir(parents=True)
    (rig.plugin / "release.env").unlink()
    for path in (rig.run_dir / "install.env", rig.plugin / "release.env"):
        subprocess.run(["mkfifo", str(path)], check=True)
    result = rig("UserPromptSubmit", payload=_prompt("привет"), timeout=5)
    assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
    with pytest.raises(subprocess.TimeoutExpired):  # control: past the prefilter it does read
        rig("UserPromptSubmit", payload=_prompt("/handoff"), timeout=2)


def test_a_plain_prompt_is_within_budget(rig):
    """Spec §2.7: 50 ms p95 over 20 warm runs. CI runners are noisier, so CI gets 200 ms;
    Windows has no threshold yet (Task 2) and is measured, not asserted."""
    payload = _prompt("привет")
    rig("UserPromptSubmit", payload=payload)  # warm
    times = sorted(rig("UserPromptSubmit", payload=payload).elapsed for _ in range(20))
    p95 = times[18]
    print(f"UserPromptSubmit plain p95={p95 * 1000:.1f} ms")
    if WINDOWS:
        return
    budget = 0.200 if os.environ.get("CI") else 0.050
    assert p95 < budget, f"p95 {p95 * 1000:.1f} ms"


# ---- fix round 1 ---------------------------------------------------------------------------

def test_a_1mb_payload_is_read_in_bulk(rig):
    """PreToolUse Write/Edit carries the whole file on stdin. `read -d ''` reads one byte per
    syscall: 1 MB took 0.48 s on macOS against 0.01 s for `$(cat)`, and Git Bash emulates
    every syscall."""
    _ready(rig)
    payload = {"hook_event_name": "PreToolUse", "session_id": "s", "tool_input": {"content": "x" * 2**20}}
    rig("PreToolUse", payload=payload)  # warm
    result = rig("PreToolUse", payload=payload)
    assert result.text == "FAKE-OUT:probe", result.stderr
    assert len((rig.tmp / "fake.stdin").read_bytes()) > 2**20
    print(f"PreToolUse 1 MB: {result.elapsed * 1000:.0f} ms")
    budget = 3.0 if os.environ.get("CI") else 0.25
    assert result.elapsed < budget, f"{result.elapsed:.2f}s"


def test_an_unwritable_log_leaks_nothing_to_stderr(rig):
    """`>> file 2>/dev/null` fails at the `>>` before the `2>` applies (hooks.md: every
    exit path honours the channel)."""
    fake = rig.fake(rc=1)
    rig.install(["STATE=ready", "VERSION=4.0.0", f"H2T_HOOK={_p(fake)}"])
    (rig.home / ".h2t" / "logs").write_text("a file where the directory should be", encoding="utf-8")
    result = rig("Stop")
    assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")


def _editable(rig, editable, plugin_root):
    fake = rig.fake()
    rig.install(["STATE=ready", "VERSION=4.0.0", f"EDITABLE_ROOT={editable}", f"H2T_HOOK={_p(fake)}"])
    plugin_root.mkdir(parents=True, exist_ok=True)
    return rig("Stop", plugin_root=plugin_root)


def test_editable_root_equal_to_the_plugin_root_is_inside(rig):
    checkout = rig.tmp / "checkout"
    assert _editable(rig, _p(checkout), checkout).text == "FAKE-OUT:probe"


def test_editable_root_with_a_trailing_slash_is_inside(rig):
    checkout = rig.tmp / "checkout"
    assert _editable(rig, _p(checkout) + "/", checkout / "plugins" / "h2t-core").text == "FAKE-OUT:probe"


def test_a_sibling_with_the_same_prefix_is_outside(rig):
    result = _editable(rig, _p(rig.tmp / "checkout"), rig.tmp / "checkout-2" / "plugins" / "h2t-core")
    assert (result.returncode, result.stdout) == (0, b""), result.text  # Stop: silent, not run
    assert not (rig.tmp / "fake.pid").exists()


@pytest.mark.skipif(WINDOWS, reason="symlinks need privileges on Windows")
def test_a_plugin_reached_through_a_symlink_is_inside(rig):
    checkout = rig.tmp / "checkout"
    (checkout / "plugins" / "h2t-core").mkdir(parents=True)
    link = rig.tmp / "link"
    link.symlink_to(checkout, target_is_directory=True)
    assert _editable(rig, _p(checkout), link / "plugins" / "h2t-core").text == "FAKE-OUT:probe"


@pytest.mark.skipif(WINDOWS, reason="symlinks need privileges on Windows")
def test_editable_root_spelled_through_a_symlink_is_inside(rig):
    """/var vs /private/var on macOS: the same directory, two spellings."""
    checkout = rig.tmp / "checkout"
    (checkout / "plugins" / "h2t-core").mkdir(parents=True)
    link = rig.tmp / "link"
    link.symlink_to(checkout, target_is_directory=True)
    assert _editable(rig, _p(link), checkout / "plugins" / "h2t-core").text == "FAKE-OUT:probe"
