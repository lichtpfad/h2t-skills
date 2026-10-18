"""`h2t-setup sync` converges a machine to the target from any state (spec §2.5, §7.3.3–8,
§9.5). Fakes stand in for `uv` (the `uv=` parameter, plus the processes it installs, through
`execute=`) and for `claude` (fake_claude.py, under the real harness wrapper). No test runs
the real `uv` or `claude`; HOME, USERPROFILE and CLAUDE_CONFIG_DIR are temporary."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from h2t_ops.core.errors import ConfigError, NetworkError
from h2t_ops.setup import cli, harness_claude, manifest, state, sync
from tests.setup.fake_claude import FakeClaude, Interrupted, Ticker

V = "4.1.0"
BOOT = ["uvx", "--isolated", "--python", "3.12.11", "--managed-python", "-c",
        "https://example.invalid/constraints.txt", "--from",
        f"h2t-ops @ https://example.invalid/h2t_ops-{V}-py3-none-any.whl", "h2t-setup"]
TARGET = {"format": 1, "version": V, "previous": "4.0.0", "python": "3.12.11",
          "wheel": f"https://example.invalid/h2t_ops-{V}-py3-none-any.whl",
          "constraints": "https://example.invalid/constraints.txt", "bootstrap": BOOT,
          "ref": f"v{V}"}
ENTRY = ("h2t-ops", "h2t-hook", "h2t-gather")


class FakeUv:
    """`uv tool dir` and `uv tool install`, writing a receipt and an environment marker the
    way uv lays them out; `run` answers for the processes that environment would run."""

    def __init__(self, root: Path, tick=None, fail_install: bool = False) -> None:
        self.tools, self.bin = root / "uv-tools", root / "uv-bin"
        self.tick = tick or (lambda label: None)
        self.fail_install = fail_install
        self.installs: list[list[str]] = []

    @property
    def root(self) -> Path:
        return self.tools / "h2t-ops"

    def env(self) -> dict | None:
        try:
            return json.loads((self.root / "fake-env.json").read_text())
        except FileNotFoundError:
            return None

    def write_env(self, version, extras=(), with_=(), healthy=True) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.bin.mkdir(parents=True, exist_ok=True)
        (self.root / "fake-env.json").write_text(json.dumps(
            {"version": version, "extras": list(extras), "healthy": healthy}))
        main = '{ name = "h2t-ops"' + (
            ", extras = [" + ", ".join(f'"{e}"' for e in extras) + "]" if extras else "") + " }"
        reqs = [main]
        for w in with_:
            name, spec = re.fullmatch(r"([A-Za-z0-9._-]+)(.*)", w).groups()
            specifier = f', specifier = "{spec}"' if spec else ""
            reqs.append(f'{{ name = "{name}"{specifier} }}')
        eps = [f'{{ name = "{n}", install-path = {json.dumps(str(self.bin / n))}, from = "h2t-ops" }}'
               for n in ENTRY]
        (self.root / "uv-receipt.toml").write_text(
            "[tool]\nrequirements = [" + ", ".join(reqs) + "]\nentrypoints = [\n    "
            + ",\n    ".join(eps) + ",\n]\n")
        for n in ENTRY:
            (self.bin / n).write_text("fake entry point")

    def __call__(self, args):
        if args == ["tool", "dir"]:
            return subprocess.CompletedProcess(args, 0, str(self.tools) + "\n", "")
        assert args[:3] == ["tool", "install", "--reinstall"], args
        self.installs.append(list(args))
        if self.fail_install:
            return subprocess.CompletedProcess(args, 1, "", "error: No solution found\n")
        opts = dict(zip(args[3::2], args[4::2]))
        assert opts["--python"] == TARGET["python"] and "--managed-python" in args
        assert args[args.index("-c") + 1] == TARGET["constraints"]
        spec = next(a for a in args[3:] if a.startswith("h2t-ops"))
        m = re.fullmatch(r"h2t-ops(?:\[([^\]]*)\])? @ (\S+)", spec)
        version = re.search(r"h2t_ops-([^-]+)-py3", m.group(2)).group(1)
        extras = m.group(1).split(",") if m.group(1) else []
        with_ = [args[i + 1] for i, a in enumerate(args) if a == "--with"]
        # uv replaces the environment in place: a kill midway leaves it broken (probe 2b).
        if self.env() is not None:
            self.write_env(self.env()["version"], healthy=False)
            self.tick("uv: environment half replaced")
        self.write_env(version, extras, with_)
        self.tick("uv: installed")
        return subprocess.CompletedProcess(args, 0, "Installed 3 executables\n", "")

    def run(self, cmd, **kwargs):
        exe = Path(cmd[0])
        env = self.env()
        if exe.parent == self.bin:
            if not exe.exists():
                raise FileNotFoundError(2, "No such file or directory", str(exe))
            if env is None or not env["healthy"]:
                return subprocess.CompletedProcess(cmd, 127, "", "No such file or directory")
            out = f"{exe.name} {env['version']}\n" if cmd[1:] == ["--version"] else ""
            return subprocess.CompletedProcess(cmd, 0, out, "")
        assert self.root in exe.parents, cmd
        if env is None or not env["healthy"]:
            return subprocess.CompletedProcess(cmd, 1, "", "ModuleNotFoundError: h2t_ops")
        wanted = json.loads(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, json.dumps({
            "version": env["version"], "unloadable": [],
            "missing": [e for e in wanted if e not in env["extras"]]}), "")


def _no_changelog(url):
    # update's question shows the CHANGELOG; these tests do not, and never reach the network.
    raise NetworkError(f"cannot read {url}: offline")


class Machine:
    def __init__(self, root: Path, monkeypatch, *, at=None, head=V, pins=None,
                 fail_install=False, fail_on=None, update_enables=False) -> None:
        self.home, self.config = root / "home", root / "claude-config"
        self.project = root / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("USERPROFILE", str(self.home))
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(self.config))
        self.tick = Ticker(at)
        self.uv = FakeUv(root, self.tick, fail_install)
        self.claude = FakeClaude(root / "claude-state.json", self.config, head=head,
                                 pins=pins or {"v2.15.0": "3.2.3"}, tick=self.tick,
                                 fail_on=fail_on, update_enables=update_enables)
        self.answers: list[str] = []
        self.prompts: list[str] = []

    def confirm(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def run(self, mode="sync", codex=False):
        def which(name):
            return "/usr/bin/codex" if (codex and name == "codex") else None
        return sync.run(mode, TARGET, [], uv=self.uv, execute=self.uv.run,
                        claude=harness_claude.Claude(exe="claude", run=self.claude),
                        confirm=self.confirm, which=which, fetch=_no_changelog)

    def env_file(self) -> dict:
        text = (state.run_dir() / "install.env").read_text()
        return dict(line.split("=", 1) for line in text.splitlines())

    def install_json(self) -> dict:
        return json.loads((state.run_dir() / "install.json").read_text())


@pytest.fixture
def interrupt_writes(monkeypatch):
    """State writes count as steps too: the interruption between install.json and
    install.env is one of them."""
    real = state._atomic_write

    def write(path, data):
        real(path, data)
        tick = getattr(write, "tick", None)
        if tick is not None:
            tick(f"wrote {path.name}" + (" ready" if b"STATE=ready" in data else ""))
    monkeypatch.setattr(state, "_atomic_write", write)
    return write


def _converged(m: Machine, plugins=("h2t-core", "h2t-ops")) -> None:
    install = state.read()
    assert install is not None, m.env_file()
    assert install.version == V
    assert m.env_file()["STATE"] == "ready"
    assert m.env_file()["GENERATION"] == m.install_json()["generation"]
    assert m.uv.env() == {"version": V, "extras": install.user_options["extras"],
                          "healthy": True}
    market = m.claude.load()["marketplaces"]["lichtpfad"]
    assert market["ref"] is None
    installed = m.claude.installed()
    for name in plugins:
        assert installed[name]["version"] == V, installed


# --- the states of §2.5 --------------------------------------------------------------------

def test_a_clean_machine_gets_the_marketplace_the_plugins_and_a_ready_cli(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    report = m.run()
    assert report.failed == []
    _converged(m)
    assert m.claude.mutations()[0] == ["marketplace", "add", "lichtpfad/h2t-skills"]
    assert {(p["scope"], p["enabled"]) for p in m.claude.installed().values()} == {("user", True)}
    assert m.install_json()["plugins"] == ["h2t-core", "h2t-ops"]
    assert report.reload_needed is True


def test_a_converged_machine_changes_nothing_but_rewrites_both_projections(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    before = m.install_json()["generation"]
    installs, mutations = len(m.uv.installs), len(m.claude.mutations())
    report = m.run()
    assert report.failed == []
    assert len(m.uv.installs) == installs and len(m.claude.mutations()) == mutations
    assert m.install_json()["generation"] != before
    assert m.env_file()["GENERATION"] == m.install_json()["generation"]
    assert report.reload_needed is False


def test_a_cli_0_2_1_with_only_a_receipt_keeps_its_options(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.uv.write_env("0.2.1", extras=["drawio"], with_=["six==1.17.0"])
    assert not (state.run_dir() / "install.json").exists()
    m.run()
    _converged(m)
    (args,) = m.uv.installs
    assert f"h2t-ops[drawio] @ {TARGET['wheel']}" in args
    assert args[args.index("--with") + 1] == "six==1.17.0"
    assert m.install_json()["user_options"] == {"extras": ["drawio"], "with": ["six==1.17.0"]}


def test_a_damaged_environment_marked_ready_is_reinstalled(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    assert m.env_file()["STATE"] == "ready"
    m.uv.write_env(V, healthy=False)  # `--version` now fails, the files still say ready
    m.run()
    assert len(m.uv.installs) == 2
    _converged(m)


def test_a_missing_extra_is_a_mismatch(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    data = m.install_json()
    data["user_options"]["extras"] = ["drawio"]
    state.commit(state.Install(**data))
    m.run()
    assert len(m.uv.installs) == 2 and "h2t-ops[drawio] @" in " ".join(m.uv.installs[-1])
    _converged(m)


def test_an_older_cli_with_newer_plugins_and_a_stale_catalog(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.uv.write_env("4.0.0")
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-ops", "4.0.0", "user", True)])
    m.run()
    assert ["marketplace", "update", "lichtpfad"] in m.claude.mutations()
    _converged(m)


def test_an_interruption_after_every_step_is_finished_by_the_next_run(tmp_path, monkeypatch,
                                                                     interrupt_writes):
    probe = Machine(tmp_path / "count", monkeypatch)
    probe.uv.write_env("4.0.0")
    probe.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True)])
    interrupt_writes.tick = probe.tick
    probe.run()
    steps = list(probe.tick.log)
    assert any(s.startswith("wrote install.json") for s in steps)
    assert any(s.startswith("uv: environment half replaced") for s in steps)
    assert any(s.startswith("claude ") for s in steps), steps
    for k in range(1, len(steps) + 1):
        m = Machine(tmp_path / f"k{k}", monkeypatch, at=k)
        m.uv.write_env("4.0.0")
        m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True)])
        interrupt_writes.tick = m.tick
        with pytest.raises(Interrupted):
            m.run()
        m.tick.at = None
        report = m.run()
        assert report.failed == [], (k, steps[k - 1], report.failed)
        _converged(m, plugins=("h2t-core",))


def test_an_interruption_between_install_json_and_install_env_rewrites_both(tmp_path,
                                                                           monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    real = state._write_env

    def die_on_ready(st, *args):
        if st == "ready":
            raise Interrupted("between install.json and install.env")
        real(st, *args)
    monkeypatch.setattr(state, "_write_env", die_on_ready)
    m.uv.write_env(V, healthy=False)
    with pytest.raises(Interrupted):
        m.run()
    assert state.read() is None  # install.json is new, install.env still says updating
    monkeypatch.setattr(state, "_write_env", real)
    m.run()
    _converged(m)


def test_a_failed_resolution_leaves_the_previous_cli_ready(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.uv.write_env("4.0.0")
    state.commit(state.Install(version="4.0.0", generation="g0", tool_root=str(m.uv.root),
                               entrypoints={n: str(m.uv.bin / n) for n in ENTRY}))
    m.uv.fail_install = True
    report = m.run()
    assert [f[0] for f in report.failed][0].startswith("CLI")
    assert BOOT[0] in report.failed[0][1] and report.failed[0][1].endswith(" sync")
    install = state.read()
    assert install is not None and install.version == "4.0.0" and install.generation != "g0"
    assert m.claude.mutations() == []  # plugins of 4.1.0 do not go next to a 4.0.0 CLI


# --- Claude Code plugins -------------------------------------------------------------------

def _pinned(m):
    return [("h2t-core", "3.2.3", "user", False),
            ("h2t-ops", "3.2.3", "project", True, m.project)]


def test_a_pinned_marketplace_stops_sync_with_the_commands_and_changes_nothing(tmp_path,
                                                                              monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=_pinned(m))
    before = m.claude.path.read_bytes()
    report = m.run()
    assert m.claude.path.read_bytes() == before
    assert m.claude.mutations() == [] and m.prompts == []  # sync never asks
    (subject, commands), = [f for f in report.failed if "pinned" in f[0]]
    assert "v2.15.0" in subject
    assert commands.splitlines() == [
        "claude plugin marketplace remove lichtpfad",
        "claude plugin marketplace add lichtpfad/h2t-skills",
        "claude plugin install h2t-core@lichtpfad --scope user",
        f'cd "{os.path.realpath(m.project)}" && claude plugin install h2t-ops@lichtpfad --scope project',
        "claude plugin disable h2t-core@lichtpfad --scope user",
    ]
    assert state.read().version == V  # the CLI step is not the harness's


def test_a_pinned_marketplace_in_update_is_repinned_after_yes(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=_pinned(m))
    m.answers = ["да", "да"]  # the update question, then the re-pin
    report = m.run("update")
    assert report.failed == [] and len(m.prompts) == 2 and "v2.15.0" in m.prompts[1]
    _converged(m)
    got = {n: (p["scope"], p["enabled"]) for n, p in m.claude.installed().items()}
    assert got == {"h2t-core": ("user", False), "h2t-ops": ("project", True)}


def test_a_pinned_marketplace_in_update_without_yes_changes_nothing(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=_pinned(m))
    before = m.claude.path.read_bytes()
    m.answers = ["да", "нет"]  # yes to the update, no to the re-pin
    report = m.run("update")
    assert m.claude.path.read_bytes() == before
    assert any("pinned" in f[0] for f in report.failed)


def test_a_failure_between_the_repin_commands_restores_the_snapshot(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch, fail_on="install h2t-ops@lichtpfad")
    m.claude.seed(ref="v2.15.0", plugins=_pinned(m))
    m.answers = ["да", "да"]  # the update question, then the re-pin
    report = m.run("update")
    assert any("restored" in f[0] for f in report.failed), report.failed
    data = m.claude.load()
    assert data["marketplaces"]["lichtpfad"]["ref"] == "v2.15.0"
    got = {n: (p["version"], p["scope"], p["enabled"]) for n, p in m.claude.installed().items()}
    assert got == {"h2t-core": ("3.2.3", "user", False), "h2t-ops": ("3.2.3", "project", True)}


def test_an_interrupted_repin_is_finished_with_the_scopes_and_disabled_it_had(tmp_path,
                                                                             monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=_pinned(m))
    m.run("sync")  # the CLI reaches the target; the pinned harness stops untouched
    m.answers = ["да", "да"]  # the update question, then the re-pin
    m.tick.at = len(m.tick.log) + 1  # dies right after `marketplace remove`
    with pytest.raises(Interrupted) as exc:
        m.run("update")
    assert "marketplace remove" in str(exc.value)
    assert m.claude.load()["plugins"] == []
    m.tick.at = None
    report = m.run("sync")
    assert report.failed == []
    got = {n: (p["version"], p["scope"], p["enabled"]) for n, p in m.claude.installed().items()}
    assert got == {"h2t-core": (V, "user", False), "h2t-ops": (V, "project", True)}


def test_a_plugin_the_user_disabled_stays_disabled_and_is_updated(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-ops", "4.0.0", "user", False)])
    report = m.run()
    assert report.failed == []
    ops = m.claude.installed()["h2t-ops"]
    assert (ops["version"], ops["enabled"]) == (V, False)
    assert ["install", "h2t-ops@lichtpfad", "--scope", "user"] not in m.claude.mutations()


def test_the_set_is_the_lichtpfad_plugins_installed_when_there_is_no_install_json(tmp_path,
                                                                                  monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-dev", "4.0.0", "user", True)])
    m.run()
    assert m.install_json()["plugins"] == ["h2t-core", "h2t-dev"]
    _converged(m, plugins=("h2t-core", "h2t-dev"))
    assert "h2t-ops" not in m.claude.installed()


def test_an_empty_set_is_a_failure(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    data = m.install_json()
    data["plugins"] = []
    state.commit(state.Install(**data))
    report = m.run()
    assert any("empty" in f[0] for f in report.failed), report.failed


def test_without_claude_the_plugins_are_reported_not_managed(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    report = sync.run("sync", TARGET, [], uv=m.uv, execute=m.uv.run,
                      claude=harness_claude.Claude(exe="", run=m.claude), confirm=m.confirm,
                      which=lambda n: None)
    assert report.failed == [] and m.claude.calls == []
    assert any("Claude Code" in n for n in report.notes)


def test_codex_is_not_touched_and_the_report_names_its_commands(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    report = m.run(codex=True)
    text = "\n".join(report.notes)
    assert "codex plugin marketplace add lichtpfad/h2t-skills" in text
    assert "codex plugin add h2t-core@lichtpfad" in text
    assert "codex plugin add h2t-ops@lichtpfad" in text


def test_the_report_asks_open_sessions_to_reload(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    report = m.run()
    text = "\n".join(report.notes)
    assert "/reload-plugins" in text and "two releases" in text


# --- cache ---------------------------------------------------------------------------------

def _cache(config: Path, plugin: str, *versions: str) -> Path:
    root = config / "plugins" / "cache" / "lichtpfad" / plugin
    for v in versions:
        (root / v).mkdir(parents=True)
    return root


def test_the_cache_keeps_the_two_latest_versions_by_semver(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    core = _cache(m.config, "h2t-core", "3.9.0", "3.10.0", "4.0.0")
    dev = _cache(m.config, "h2t-dev", "4.9.0", "4.10.0", "4.2.0")  # not installed
    other = m.config / "plugins" / "cache" / "someone" / "x"
    (other / "1.0.0").mkdir(parents=True)
    (other / "0.9.0").mkdir(parents=True)
    (other / "0.8.0").mkdir(parents=True)
    report = m.run()  # installs 4.1.0: four versions of h2t-core
    assert sorted(p.name for p in core.iterdir()) == ["4.0.0", "4.1.0"]
    assert sorted(p.name for p in dev.iterdir()) == ["4.10.0", "4.9.0"]  # numbers, not text
    assert len(list(other.iterdir())) == 3
    assert report.reload_needed is True


def test_the_cache_never_deletes_the_installed_version(tmp_path, monkeypatch):
    config = tmp_path / "cfg"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))   # deletion goes to the harness place
    core = _cache(config, "h2t-core", "3.2.3", "4.0.0", "4.1.0", "4.2.0", "notes")
    removed = sync.clean_cache(config, [{"id": "h2t-core@lichtpfad", "version": "3.2.3"}])
    assert sorted(p.name for p in core.iterdir()) == ["3.2.3", "4.1.0", "4.2.0", "notes"]
    assert [p.name for p in removed] == ["4.0.0"]



def test_the_cache_keeps_a_creative_version_that_holds_user_profiles(tmp_path, monkeypatch):
    """3.x style-create wrote user profiles into the plugin cache,
    <config>/plugins/cache/lichtpfad/h2t-creative/<ver>/profiles/<name>. Deleting that version
    would delete them: it stays, and the report says where they are and where they go."""
    m = Machine(tmp_path, monkeypatch)
    creative = _cache(m.config, "h2t-creative", "3.0.0", "3.1.0", "4.0.0", "4.0.5")
    for v in ("3.0.0", "3.1.0"):
        (creative / v / "profiles" / "h2t-default").mkdir(parents=True)  # shipped: no reason
    (creative / "3.0.0" / "profiles" / "my-brand").mkdir()
    (creative / "3.0.0" / "profiles" / "my-brand" / "DESIGN.md").write_text("mine")
    report = m.run()
    assert sorted(p.name for p in creative.iterdir()) == ["3.0.0", "4.0.0", "4.0.5"]
    assert (creative / "3.0.0" / "profiles" / "my-brand" / "DESIGN.md").read_text() == "mine"
    note = next(n for n in report.notes if "my-brand" in n)
    assert str(creative / "3.0.0") in note
    from h2t_ops.core import paths
    assert str(paths.data_dir() / "creative" / "profiles") in note
    assert any("h2t-creative 3.1.0" in d for d in report.done)


def test_clean_cache_reads_the_shipped_profile_names_from_the_package():
    from h2t_ops.resources import resource_dir
    shipped = {p.name for p in (resource_dir("creative") / "profiles").iterdir() if p.is_dir()}
    assert "h2t-default" in shipped and sync.shipped_profiles() == shipped


# --- the boundary --------------------------------------------------------------------------

def test_an_editable_install_never_reaches_the_steps(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    state.commit(state.Install(version=V, generation="g", tool_root=str(m.uv.root),
                               entrypoints={}, editable=str(tmp_path / "checkout")))
    before = {p.name: p.read_bytes() for p in state.run_dir().iterdir()}
    with pytest.raises(ConfigError) as exc:
        m.run()
    assert str(tmp_path / "checkout") in str(exc.value)
    assert m.uv.installs == [] and m.claude.calls == []
    assert {p.name: p.read_bytes() for p in state.run_dir().iterdir()} == before


def test_the_cli_renders_a_failed_report_as_an_error_with_the_retry(tmp_path, monkeypatch,
                                                                    capsys):
    Machine(tmp_path, monkeypatch)
    monkeypatch.setattr(manifest, "current", lambda: TARGET)
    monkeypatch.setattr(sync, "ensure_executor", lambda *a, **k: None)
    monkeypatch.setattr(sync, "receipt_editable", lambda *a, **k: None)
    report = sync.Report(done=["x"], failed=[("CLI h2t-ops", "uvx … sync")], reload_needed=False)
    monkeypatch.setattr(sync, "run", lambda mode, target, argv: report)
    assert cli.main(["sync", "--json"]) == 1
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["details"]["failed"] == [["CLI h2t-ops", "uvx … sync"]]
    assert err["hint"] == "uvx … sync"


# --- the probe the real environment runs ---------------------------------------------------

def test_the_probe_answers_in_a_real_environment():
    """The script `sync` sends to the tool's python, run by this interpreter: it is the one
    piece no fake can stand in for."""
    import h2t_ops
    done = subprocess.run([sys.executable, "-I", "-c", sync.PROBE, json.dumps(["drawio",
                                                                              "no-such"])],
                          capture_output=True, text=True, encoding="utf-8",
                          env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["version"] == h2t_ops.__version__
    assert out["unloadable"] == []
    missing = " ".join(out["missing"])
    assert "no-such" in missing
    if importlib.util.find_spec("drawpyo") is None:
        assert "drawio" in missing
    else:
        assert "drawio" not in missing


# --- fix round 1: enabled per its own scope, every scope on a re-pin, pending first ----------

def test_a_project_disable_is_not_replayed_as_a_global_one_by_a_sync_stop(tmp_path, monkeypatch):
    """h2t-core:agent-profile disables plugins per repo. From inside such a repo `claude
    plugin list` reads the user-scope plugin as disabled; sync must not print a user-scope
    disable for it."""
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True),
                                          ("h2t-ops", "3.2.3", "user", True)],
                  project_settings={m.project: {"h2t-ops": False}})
    monkeypatch.chdir(m.project)
    report = m.run()
    (_, commands), = [f for f in report.failed if "pinned" in f[0]]
    assert "disable" not in commands, commands


def test_a_project_disable_stays_in_its_project_through_a_sync(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-ops", "4.0.0", "user", True)],
                  project_settings={m.project: {"h2t-ops": False}})
    monkeypatch.chdir(m.project)
    report = m.run()
    assert report.failed == []
    assert m.claude.setting("h2t-ops") is True  # not disabled for every project
    assert m.claude.setting("h2t-ops", project=m.project) is False
    assert not any(c[0] == "disable" for c in m.claude.mutations())


def test_an_interrupted_repin_rerun_elsewhere_does_not_disable_globally(tmp_path, monkeypatch):
    """The reviewer's case: snapshot taken inside a repo that disables h2t-ops, re-pin dies
    after `remove`, the rerun happens in another directory."""
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True),
                                          ("h2t-ops", "3.2.3", "user", True)],
                  project_settings={m.project: {"h2t-ops": False}})
    monkeypatch.chdir(m.project)
    m.run("sync")
    m.answers = ["да", "да"]  # the update question, then the re-pin
    m.tick.at = len(m.tick.log) + 1  # dies right after `marketplace remove`
    with pytest.raises(Interrupted):
        m.run("update")
    m.tick.at = None
    monkeypatch.chdir(tmp_path)
    report = m.run("sync")
    assert report.failed == [], report.failed
    assert m.claude.setting("h2t-ops") is True
    assert not any(c[0] == "disable" for c in m.claude.mutations())


def test_a_repin_brings_back_every_scope_the_project_one_in_its_project(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True),
                                          ("h2t-core", "3.2.3", "project", False, m.project),
                                          ("h2t-ops", "3.2.3", "user", True)])
    m.answers = ["да", "да"]  # the update question, then the re-pin
    report = m.run("update")
    assert report.failed == [], report.failed
    proj = os.path.realpath(m.project)
    assert m.claude.entries() == [
        ("h2t-core", "project", proj, V, False),
        ("h2t-core", "user", None, V, True),
        ("h2t-ops", "user", None, V, True),
    ]
    installs = [(c, d) for c, d in zip(m.claude.calls, m.claude.cwds) if c[0] == "install"]
    assert (["install", "h2t-core@lichtpfad", "--scope", "project"], proj) in installs


def test_a_sync_stop_lists_every_scope_of_a_plugin(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True),
                                          ("h2t-core", "3.2.3", "project", True, m.project)])
    report = m.run()
    (_, commands), = [f for f in report.failed if "pinned" in f[0]]
    proj = os.path.realpath(m.project)
    assert "claude plugin install h2t-core@lichtpfad --scope user" in commands.splitlines()
    assert (f'cd "{proj}" && claude plugin install h2t-core@lichtpfad --scope project'
            in commands.splitlines())


def test_a_project_whose_directory_is_gone_is_left_to_a_person(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    gone = tmp_path / "deleted-project"
    gone.mkdir()
    m.claude.seed(ref="v2.15.0", plugins=[("h2t-core", "3.2.3", "user", True),
                                          ("h2t-ops", "3.2.3", "project", True, gone)])
    proj = os.path.realpath(gone)
    gone.rmdir()
    report = m.run()
    (_, commands), = [f for f in report.failed if "pinned" in f[0]]
    manual = [line for line in commands.splitlines() if line.startswith("manual")]
    assert manual and proj in manual[0] and "install h2t-ops@lichtpfad --scope project" in manual[0]
    m.answers = ["да", "да"]  # the update question, then the re-pin
    report = m.run("update")
    notes = "\n".join(report.notes)
    assert "manual" in notes and proj in notes and "--scope project" in notes
    assert [c for c in m.claude.mutations() if c[:2] == ["install", "h2t-ops@lichtpfad"]] == []


def test_a_crash_between_update_and_redisable_is_redisabled_on_the_rerun(tmp_path, monkeypatch):
    """Whether `claude plugin update` keeps a disabled plugin disabled is not probed. Model
    the bad answer, die right after the update, and the rerun must still know it was
    disabled: the pending snapshot is written before the first plugin mutation."""
    m = Machine(tmp_path, monkeypatch, update_enables=True)
    m.claude.seed(offers="4.0.0", plugins=[("h2t-core", "4.0.0", "user", True),
                                           ("h2t-ops", "4.0.0", "user", False)])
    def crash_after_ops_update(label):
        m.tick.log.append(label)
        if label.startswith("claude update h2t-ops"):
            raise Interrupted(label)
    m.claude.tick = crash_after_ops_update
    with pytest.raises(Interrupted):
        m.run()
    assert m.claude.setting("h2t-ops") is True  # the update re-enabled it, then the crash
    m.claude.tick = m.tick
    report = m.run()
    assert report.failed == [], report.failed
    assert m.claude.setting("h2t-ops") is False
    assert m.claude.installed()["h2t-ops"]["version"] == V
