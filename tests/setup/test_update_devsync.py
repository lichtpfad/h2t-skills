"""`h2t-setup update` asks before it changes anything; `h2t-setup dev-sync` installs the CLI
from a checkout (spec §7.3 last paragraph, §7.3.2, §7.4, §6.4). The fakes are the ones of
test_sync_converges: no test runs the real uv, claude or git, and none reaches the network."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import h2t_ops
from h2t_ops.core.errors import ConfigError, NetworkError, exit_code_for
from h2t_ops.setup import cli, harness_claude, manifest, state, sync
from tests.setup.test_sync_converges import BOOT, TARGET, FakeUv, Machine, V, _converged

CHANGELOG = (
    "# Changelog\n\n"
    f"## {V}\n\n- update asks before it changes anything\n\n"
    "## 4.0.1\n\n- a fix between the two\n\n"
    "## 4.0.0\n\n- the installed one, already seen\n"
).encode()
CHANGELOG_URL = f"https://raw.githubusercontent.com/lichtpfad/h2t-skills/v{V}/CHANGELOG.md"


class Pages:
    def __init__(self, body: bytes | None = CHANGELOG) -> None:
        self.body, self.urls = body, []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url != CHANGELOG_URL or self.body is None:
            raise NetworkError(f"cannot read {url}: offline")
        return self.body


def _run(m: Machine, mode: str = "update", pages: Pages | None = None, **kw):
    return sync.run(mode, TARGET, [], uv=m.uv, execute=m.uv.run,
                    claude=harness_claude.Claude(exe="claude", run=m.claude),
                    confirm=kw.pop("confirm", m.confirm), which=lambda name: None,
                    fetch=pages or Pages(), **kw)


def _old_machine(tmp_path, monkeypatch) -> Machine:
    """A 4.0.0 install: the CLI from a receipt, both plugins at 4.0.0."""
    m = Machine(tmp_path, monkeypatch)
    m.uv.write_env("4.0.0")
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-ops", "4.0.0", "user", True)])
    return m


# --- update --------------------------------------------------------------------------------

def test_update_without_yes_changes_nothing(tmp_path, monkeypatch):
    m = _old_machine(tmp_path, monkeypatch)
    harness, env = m.claude.path.read_bytes(), m.uv.env()
    m.answers = ["нет"]
    report = _run(m)
    assert len(m.prompts) == 1
    assert m.uv.installs == [] and m.claude.mutations() == []
    assert m.claude.path.read_bytes() == harness and m.uv.env() == env
    # Not even the snapshot: the question comes before anything is written.
    assert not state.run_dir().exists()
    assert report.failed == [] and report.reload_needed is False
    assert any("nothing was changed" in n for n in report.notes), report.notes


@pytest.mark.parametrize("answer", ["", "  ", "n", "нет", "yes please"])
def test_only_an_explicit_yes_counts(tmp_path, monkeypatch, answer):
    m = _old_machine(tmp_path, monkeypatch)
    m.answers = [answer]
    _run(m)
    assert m.uv.installs == [] and not state.run_dir().exists()


@pytest.mark.parametrize("answer", ["да", "ДА", "Yes", "y", " Y \n"])
def test_update_with_yes_converges(tmp_path, monkeypatch, answer):
    m = _old_machine(tmp_path, monkeypatch)
    m.answers = [answer]
    report = _run(m)
    assert report.failed == [], report.failed
    _converged(m)
    assert len(m.uv.installs) == 1


def test_the_question_shows_was_becomes_and_the_changelog_of_the_target(tmp_path, monkeypatch):
    m = _old_machine(tmp_path, monkeypatch)
    pages = Pages()
    _run(m, pages=pages)
    (prompt,) = m.prompts
    assert pages.urls == [CHANGELOG_URL]
    assert "было → станет" in prompt
    assert f"CLI h2t-ops: 4.0.0 → {V}" in prompt
    assert f"h2t-core: 4.0.0 → {V}" in prompt and f"h2t-ops: 4.0.0 → {V}" in prompt
    # Every section after the installed version, up to the target; not the installed one.
    assert f"## {V}" in prompt and "update asks before it changes anything" in prompt
    assert "a fix between the two" in prompt
    assert "already seen" not in prompt
    assert prompt.rstrip().endswith("да?")


def test_a_first_install_shows_absent_and_the_target_section_only(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    _run(m)
    (prompt,) = m.prompts
    assert f"CLI h2t-ops: не установлен → {V}" in prompt
    assert f"h2t-core: не установлен → {V}" in prompt
    assert "update asks before" in prompt and "a fix between the two" not in prompt


@pytest.mark.parametrize("body", [None, b"# Changelog\n\n## 4.0.0\n\n- no target section\n",
                                  b"\xff\xfe not utf-8"])
def test_a_missing_or_unparseable_changelog_does_not_block(tmp_path, monkeypatch, body):
    m = _old_machine(tmp_path, monkeypatch)
    m.answers = ["да"]
    report = _run(m, pages=Pages(body))
    (prompt,) = m.prompts
    assert "CHANGELOG недоступен" in prompt and CHANGELOG_URL in prompt
    assert report.failed == []
    _converged(m)


def test_a_pinned_marketplace_is_a_second_question_after_the_first(tmp_path, monkeypatch):
    m = _old_machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True)])
    m.answers = ["да", "нет"]
    report = _run(m)
    assert len(m.prompts) == 2 and "v2.15.0" in m.prompts[1]
    assert any("not confirmed" in f[0] for f in report.failed)


def _wire_cli(monkeypatch, version):
    monkeypatch.setattr(manifest, "current", lambda: dict(TARGET))
    monkeypatch.setattr(h2t_ops, "__version__", version)
    monkeypatch.setattr(sync, "OS_NAME", "posix")
    monkeypatch.setattr(sync, "installed_tool_root", lambda **k: None)
    monkeypatch.setattr(sync, "receipt_editable", lambda *a, **k: None)
    monkeypatch.setenv(sync.RELAUNCH_ENV, "")
    monkeypatch.delenv(sync.RELAUNCH_ENV)


def test_a_confirmation_never_crosses_the_relaunch(tmp_path, monkeypatch):
    """§7.3.2: the old executor asks nothing and hands `update` over; the target asks about
    its own version. The confirm is the default one, resolved inside `run`."""
    m = _old_machine(tmp_path, monkeypatch)
    asked: list[str] = []

    def ask(prompt):
        asked.append(prompt)
        return "да"
    monkeypatch.setattr(sync, "ask", ask)
    calls = []

    def execvp(file, args):
        calls.append(args)
        raise SystemExit("execvp")
    monkeypatch.setattr(sync.os, "execvp", execvp)
    real_run = sync.run
    monkeypatch.setattr(sync, "run", lambda mode, target, argv: real_run(
        mode, target, argv, uv=m.uv, execute=m.uv.run,
        claude=harness_claude.Claude(exe="claude", run=m.claude), which=lambda n: None,
        fetch=Pages()))

    _wire_cli(monkeypatch, "4.0.0")
    with pytest.raises(SystemExit):
        cli.main(["update"])
    (command,) = calls
    assert command[:len(BOOT)] == BOOT
    words = command[len(BOOT):]
    assert words == ["update"]
    assert asked == [] and m.uv.installs == []

    # The process the bootstrap starts: the target's own executor.
    monkeypatch.setattr(h2t_ops, "__version__", V)
    assert cli.main(words) == 0
    assert len(asked) == 1 and f"→ {V}" in asked[0]
    _converged(m)


def test_no_option_carries_consent_into_the_target():
    """Consent is never a word of argv, so the re-launch has none to carry."""
    for flag in ("--yes", "-y", "--force", "--assume-yes"):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["update", flag])


def test_update_json_without_a_terminal_refuses_and_touches_nothing(tmp_path, monkeypatch,
                                                                    capsys):
    m = _old_machine(tmp_path, monkeypatch)
    _wire_cli(monkeypatch, V)

    class NoTty:
        def isatty(self):
            return False

        def readline(self):
            raise AssertionError("read an answer nobody could give")
    monkeypatch.setattr(sys, "stdin", NoTty())

    def no_target():
        raise AssertionError("the refusal must precede the target")
    monkeypatch.setattr(manifest, "current", no_target)
    assert cli.main(["update", "--json"]) == 3
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["details"]["reason"] == "confirmation_required"
    assert "h2t-setup update" in err["hint"] and "--json" in err["hint"]
    assert m.uv.installs == [] and not state.run_dir().exists()


def test_the_default_question_goes_to_stderr_and_reads_one_line(monkeypatch, capsys):
    class In:
        def readline(self):
            return "да\n"
    monkeypatch.setattr(sys, "stdin", In())
    assert sync.ask("да? ") == "да\n"
    out = capsys.readouterr()
    assert out.out == "" and out.err == "да? "


# --- dev-sync ------------------------------------------------------------------------------

class DevUv(FakeUv):
    """`uv export` from the checkout's lock and `uv tool install --editable`, the way uv
    records them; everything is in argv, and argv is recorded."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.calls: list[list[str]] = []
        self.export_fails = False

    def __call__(self, args):
        self.calls.append(list(args))
        if args == ["tool", "dir"]:
            return super().__call__(args)
        if args[0] == "export":
            if self.export_fails:
                return subprocess.CompletedProcess(args, 2, "", "error: lockfile out of date\n")
            Path(args[args.index("-o") + 1]).write_text("six==1.17.0\n")
            return subprocess.CompletedProcess(args, 0, "", "")
        assert args[:3] == ["tool", "install", "--editable"], args
        self.installs.append(list(args))
        spec = args[3]
        path, _, extras = spec.partition("[")
        version = _pyproject_version(Path(path))
        with_ = [args[i + 1] for i, a in enumerate(args) if a == "--with"]
        self.write_env(version, extras.rstrip("]").split(",") if extras else [], with_)
        return subprocess.CompletedProcess(args, 0, "Installed 3 executables\n", "")


def _pyproject_version(root: Path) -> str:
    import tomllib
    return tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]


@pytest.fixture
def dev(tmp_path, monkeypatch):
    """A machine whose cwd is inside a checkout of h2t-ops; nothing may spawn a process."""
    m = Machine(tmp_path, monkeypatch)
    m.uv = DevUv(tmp_path)
    checkout = tmp_path / "work" / "h2t-skills"
    (checkout / "h2t_ops" / "setup").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(f'[project]\nname = "h2t-ops"\nversion = "{V}"\n')
    # A parent pyproject of another project must not be taken for the checkout.
    (tmp_path / "work" / "pyproject.toml").write_text('[project]\nname = "other"\n')
    monkeypatch.chdir(checkout / "h2t_ops" / "setup")
    spawned = []

    def refuse(*args, **kwargs):
        spawned.append(args)
        raise AssertionError(f"dev-sync spawned a process: {args!r}")
    monkeypatch.setattr(subprocess, "Popen", refuse)
    m.checkout, m.spawned = checkout, spawned
    return m


def _devsync(m):
    return sync.run("dev-sync", None, [], uv=m.uv, execute=m.uv.run)


def _programs(m) -> list[str]:
    return [os.path.basename(c[0]) for c in m.uv.calls]


def test_dev_sync_installs_the_checkout_editable_and_writes_editable_root(dev):
    report = _devsync(dev)
    assert report.failed == [], report.failed
    root = os.path.realpath(dev.checkout)
    export, = [c for c in dev.uv.calls if c[0] == "export"]
    assert export[export.index("--project") + 1] == str(dev.checkout)
    assert "--frozen" in export and "--offline" in export
    constraints = export[export.index("-o") + 1]
    (install,) = dev.uv.installs
    assert install == ["tool", "install", "--editable", str(dev.checkout), "--reinstall",
                       "-c", constraints]
    env = dict(line.split("=", 1)
               for line in (state.run_dir() / "install.env").read_text().splitlines())
    assert env["STATE"] == "ready" and env["VERSION"] == V
    assert env["EDITABLE_ROOT"] == root.replace("\\", "/")
    install_state = state.read()
    assert install_state is not None and install_state.editable == root
    assert install_state.tool_root == str(dev.uv.root)
    assert set(install_state.entrypoints) == {"h2t-ops", "h2t-hook", "h2t-gather"}


def test_dev_sync_never_runs_git(dev):
    _devsync(dev)
    assert dev.spawned == []
    assert "git" not in _programs(dev)
    assert not any(c and os.path.basename(c[0]) in ("git", "git.exe") for c in dev.uv.calls)


def test_dev_sync_says_plugins_load_from_the_checkout(dev):
    report = _devsync(dev)
    text = report.text()
    assert "--plugin-dir" in text and "claude-dev.ps1" in text
    assert "marketplace" in text


def test_dev_sync_takes_user_options_from_install_json(dev):
    state.commit(state.Install(version="4.0.0", generation="g", tool_root=str(dev.uv.root),
                               entrypoints={}, user_options={"extras": ["drawio"],
                                                             "with": ["six==1.17.0"]},
                               plugins=["h2t-core"]))
    _devsync(dev)
    (install,) = dev.uv.installs
    assert install[3] == f"{dev.checkout}[drawio]"
    assert install[install.index("--with") + 1] == "six==1.17.0"
    data = json.loads((state.run_dir() / "install.json").read_text())
    assert data["user_options"] == {"extras": ["drawio"], "with": ["six==1.17.0"]}
    assert data["plugins"] == ["h2t-core"]


def test_dev_sync_on_3x_takes_user_options_from_the_receipt(dev):
    dev.uv.write_env("0.2.1", extras=["drawio"], with_=["six==1.17.0"])
    assert not (state.run_dir() / "install.json").exists()
    _devsync(dev)
    (install,) = dev.uv.installs
    assert install[3] == f"{dev.checkout}[drawio]"
    assert install[install.index("--with") + 1] == "six==1.17.0"


def test_dev_sync_through_the_cli_is_offline_and_spawns_only_uv(dev, monkeypatch, capsys):
    """End to end from the command line: the network refusal of conftest stands, and the
    target is never read; the only processes are the fake uv and the installed CLI."""
    def no_target(*a, **k):
        raise AssertionError("dev-sync read the release pointer")
    monkeypatch.setattr(manifest, "current", no_target)
    monkeypatch.setattr(manifest, "urllib_fetch", no_target)
    monkeypatch.setattr(sync, "run_uv", dev.uv)
    ran = []

    def run(cmd, **kwargs):
        ran.append(list(cmd))
        return dev.uv.run(cmd, **kwargs)
    monkeypatch.setattr(subprocess, "run", run)
    assert cli.main(["dev-sync", "--json"]) == 0, capsys.readouterr().err
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert all(Path(c[0]).parent == dev.uv.bin or dev.uv.root in Path(c[0]).parents
               for c in ran), ran
    assert state.read().editable == os.path.realpath(dev.checkout)


def test_dev_sync_outside_a_checkout_is_a_config_error(dev, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(ConfigError) as exc:
        _devsync(dev)
    assert exit_code_for(exc.value) == 3
    assert exc.value.details["reason"] == "not_a_checkout"
    assert dev.uv.installs == []


def test_a_failed_export_installs_nothing(dev):
    dev.uv.export_fails = True
    with pytest.raises(ConfigError) as exc:
        _devsync(dev)
    assert "uv lock" in exc.value.hint
    assert dev.uv.installs == [] and state.read() is None


def test_dev_sync_on_windows_inside_the_tool_hands_the_uv_command_back(dev, monkeypatch):
    dev.uv.write_env("4.0.0")
    monkeypatch.setattr(sync, "OS_NAME", "nt")
    monkeypatch.setattr(sync.sys, "prefix", str(dev.uv.root))
    with pytest.raises(ConfigError) as exc:
        _devsync(dev)
    assert exit_code_for(exc.value) == 3
    command = exc.value.details["command"]
    assert exc.value.details["reason"] == "relaunch_required"
    assert command[:4] == ["uv", "tool", "install", "--editable"]
    assert exc.value.hint == manifest.render(command)
    assert dev.uv.installs == [] and state.read() is None
