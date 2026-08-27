import re
from pathlib import Path

import pytest

from h2t_ops import activity_log_entry, gather_entry, handoff_entry, plugin_entrypoints


@pytest.fixture(autouse=True)
def _no_host_env_leak(monkeypatch):
    """Every host location is env-overridable now; a real one would leak into the tmp trees."""
    for var in ("H2T_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(var, raising=False)


def test_plugin_script_paths_exist():
    gather_path = plugin_entrypoints.plugin_script_path("skills/session-start/scripts/gather.py")
    activity_path = plugin_entrypoints.plugin_script_path("lib/activity/writer.py")
    assert gather_path.is_file()
    assert activity_path.is_file()


def test_load_plugin_module_exposes_main():
    module = plugin_entrypoints.load_plugin_module("skills/session-start/scripts/gather.py")
    assert callable(module.main)


def test_handoff_plugin_script_path_exists():
    handoff_path = plugin_entrypoints.plugin_script_path("skills/handoff/scripts/writer.py")
    assert handoff_path.is_file()


def test_gather_entry_delegates_to_session_start_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(gather_entry, "run_plugin_main", fake_run)
    assert gather_entry.main() == 0
    assert calls == ["skills/session-start/scripts/gather.py"]


def test_activity_log_entry_delegates_to_writer_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(activity_log_entry, "run_plugin_main", fake_run)
    assert activity_log_entry.main() == 0
    assert calls == ["lib/activity/writer.py"]


def test_handoff_entry_delegates_to_writer_script(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(handoff_entry, "run_plugin_main", fake_run)
    assert handoff_entry.main() == 0
    assert calls == ["skills/handoff/scripts/writer.py"]


def test_session_start_skill_uses_installable_entrypoints():
    skill_path = Path("plugins/h2t-core/skills/session-start/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-gather" in text
    assert "command -v h2t-activity-log" in text
    # #357: the resolver was sourced by plugin path, for a graph block that never ran (#361)
    assert "resolve-h2t-python.sh" not in text
    assert "resolve_h2t_python" not in text
    assert 'h2t-gather --cwd "$(pwd)" --briefing-only' in text
    assert "h2t-activity-log start \\" in text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py" not in text
    assert "${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py" not in text


def test_handoff_skill_uses_installable_entrypoint():
    skill_path = Path("plugins/h2t-core/skills/handoff/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-handoff" in text
    assert "resolve-h2t-python.sh" not in text
    assert "resolve_h2t_python" not in text
    assert "h2t-handoff write \\" in text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py" not in text


HANDOFF_SCRIPT = "skills/handoff/scripts/writer.py"


def _make_plugin_tree(root: Path) -> Path:
    script = root / HANDOFF_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("def main():\n    return 0\n", encoding="utf-8")
    return script


def _cache_dir(home: Path, version: str, marketplace: str = "lichtpfad") -> Path:
    root = home / ".claude" / "plugins" / "cache" / marketplace / "h2t-core" / version
    _make_plugin_tree(root)
    return root


def _codex_cache_dir(home: Path, version: str, marketplace: str = "lichtpfad") -> Path:
    root = home / ".codex" / "plugins" / "cache" / marketplace / "h2t-core" / version
    _make_plugin_tree(root)
    return root


def test_plugin_script_path_honours_claude_plugin_root(tmp_path, monkeypatch):
    """The harness already exports CLAUDE_PLUGIN_ROOT when a skill runs."""
    expected = _make_plugin_tree(tmp_path / "plugin")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "plugin"))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_plugin_script_path_falls_back_to_plugin_cache_for_a_shipped_install(tmp_path, monkeypatch):
    """A non-editable install has no plugins/ next to the package — the real bug."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root",
                        lambda: tmp_path / "site-packages" / "plugins" / "h2t-core")
    expected = _cache_dir(tmp_path / "home", "3.2.14") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_plugin_cache_fallback_prefers_highest_version_over_the_latest_dir(tmp_path, monkeypatch):
    """The observed `latest` dir lags behind the versioned ones."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    home = tmp_path / "home"
    _cache_dir(home, "3.2.13")
    _cache_dir(home, "latest")
    expected = _cache_dir(home, "3.2.14") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_env_root_without_the_script_falls_through_instead_of_failing(tmp_path, monkeypatch):
    """CLAUDE_PLUGIN_ROOT may point at a different plugin than h2t-core."""
    (tmp_path / "other-plugin").mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "other-plugin"))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT).is_file()


def test_plugin_script_path_error_names_every_candidate_tried(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "empty-home"))

    with pytest.raises(FileNotFoundError) as excinfo:
        plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT)

    message = str(excinfo.value)
    assert str(tmp_path / "absent") in message
    assert "H2T_PLUGIN_ROOT" in message  # tells the operator how to override


def test_bundled_payload_is_the_last_resort_when_no_plugin_is_installed(tmp_path, monkeypatch):
    """`uv tool install` on a machine with no plugin host at all: the wheel carries its own copy."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "empty-home"))
    expected = _make_plugin_tree(tmp_path / "payload")
    monkeypatch.setattr(plugin_entrypoints, "_bundled_payload_root", lambda: tmp_path / "payload")

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_installed_plugin_beats_the_bundled_payload(tmp_path, monkeypatch):
    """The wheel copy is frozen at build time; an installed plugin can be newer."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    home = tmp_path / "home"
    expected = _cache_dir(home, "3.2.14") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    _make_plugin_tree(tmp_path / "payload")
    monkeypatch.setattr(plugin_entrypoints, "_bundled_payload_root", lambda: tmp_path / "payload")

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_codex_plugin_cache_is_searched(tmp_path, monkeypatch):
    """Codex installs into ~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    home = tmp_path / "home"
    expected = _codex_cache_dir(home, "3.2.14") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_cache_lookup_accepts_non_semver_version_dirs(tmp_path, monkeypatch):
    """Codex names that dir `local` for local plugins and a content hash for curated ones."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    home = tmp_path / "home"
    expected = _codex_cache_dir(home, "local") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_cache_lookup_does_not_depend_on_the_marketplace_name(tmp_path, monkeypatch):
    """`codex plugin marketplace add` and forks register the catalog under their own name."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    home = tmp_path / "home"
    expected = _cache_dir(home, "3.2.14", marketplace="some-fork") / HANDOFF_SCRIPT
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_cache_lookup_honours_a_relocated_host_state_dir(tmp_path, monkeypatch):
    """CODEX_HOME / CLAUDE_CONFIG_DIR move the whole state directory off ~."""
    monkeypatch.setattr(plugin_entrypoints, "_package_plugin_root", lambda: tmp_path / "absent")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "empty-home"))
    relocated = tmp_path / "elsewhere" / "codex"
    expected = _make_plugin_tree(
        relocated / "plugins" / "cache" / "lichtpfad" / "h2t-core" / "local"
    )
    monkeypatch.setenv("CODEX_HOME", str(relocated))

    assert plugin_entrypoints.plugin_script_path(HANDOFF_SCRIPT) == expected


def test_gather_hook_uses_strict_python_probe():
    """gather-on-skill must reject an interpreter its scripts cannot run under.

    Regression guard: the resolver probe used to be `import sys` (any Python passes), so
    an unprovisioned ~/.h2t/venv was selected and the run crashed silently ("returned no
    output"). The probe must name something the scripts actually need, so resolution
    fails loud instead.

    It must NOT be `lib.cli.main`: that package lives only at the repo root, and the hook
    used to cd into the plugin root, whose vendored `lib/` shadows it — the probe then
    failed on every interpreter, in every layout (#378).
    """
    text = Path("plugins/h2t-core/hooks-handlers/gather-on-skill").read_text(encoding="utf-8")
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    # The requirement is part of the contract: uv has no environment to inherit, so a
    # probe without it resolves an interpreter that cannot import yaml. A substring
    # assertion on the probe alone would not notice the argument going missing.
    assert 'resolve_h2t_python "import yaml" pyyaml' in code
    assert "lib.cli" not in code
    assert 'resolve_h2t_python "import sys"' not in code


def _console_scripts() -> dict[str, str]:
    """`name -> module` for every console script pyproject declares."""
    import tomllib

    root = Path(__file__).resolve().parents[2]
    with (root / "pyproject.toml").open("rb") as f:
        scripts = tomllib.load(f)["project"]["scripts"]
    return {name: target.split(":")[0] for name, target in scripts.items()}


# h2t-hook takes the handler name as an argument and launches it as a process, so it has
# no single script to name and never calls run_plugin_main. It is covered instead by
# test_hook_entry_resolves_the_handlers_scaffold_writes below and by tests/core/test_hook_entry.py.
_NOT_A_SINGLE_SCRIPT = {"h2t_ops.hook_entry"}

PLUGIN_SCRIPT_ENTRIES = sorted(
    (name, module)
    for name, module in _console_scripts().items()
    if module.endswith("_entry") and module not in _NOT_A_SINGLE_SCRIPT
)


@pytest.mark.parametrize("name,module_path", PLUGIN_SCRIPT_ENTRIES, ids=[n for n, _ in PLUGIN_SCRIPT_ENTRIES])
def test_entrypoint_names_a_script_that_ships(name, module_path, monkeypatch):
    """Every installed command must name a plugin script that actually exists.

    The path lives inside `main()`, so it is captured by standing in for
    `run_plugin_main` — that also proves the module wires the two together at all.
    """
    import importlib

    module = importlib.import_module(module_path)
    captured = {}
    monkeypatch.setattr(module, "run_plugin_main", lambda rel: captured.setdefault("path", rel) or 0)
    module.main()

    relative = captured.get("path")
    assert relative, f"{module_path}.main() never called run_plugin_main"
    assert plugin_entrypoints.plugin_script_path(relative).is_file(), (
        f"{name} points at {relative}, which is not in the plugin"
    )


def test_payload_script_dependencies_are_installed():
    """Moving a script behind a command changes which interpreter runs it.

    `apply_registration.py` used to run under `~/.h2t/venv`, where ruamel.yaml happened to
    be installed by hand; as `h2t-project-register` it runs under the h2t-ops environment,
    so the dependency has to be declared. It fails politely (`{"status": "error"}`), which
    reads as a failed registration rather than a broken build — hence this test.
    """
    import importlib

    importlib.import_module("ruamel.yaml")  # skills/init-project/scripts/apply_registration.py
    importlib.import_module("yaml")  # skills/project-audit/scripts/scan.py


CLI_BACKED = {
    "h2t-core/skills/handoff": "h2t-handoff",
    "h2t-core/skills/session-start": "h2t-gather",
    "h2t-core/skills/init-project": "h2t-project-register",
    "h2t-core/skills/project-audit": "h2t-project-audit-scan",
    "h2t-core/skills/scaffold-project": "h2t-scaffold-project",
}


def _gated_commands(text: str) -> set[str]:
    """Commands the skill genuinely refuses to run without.

    Two shapes are in use: `command -v h2t-x || { ...; exit 1; }` per line, and a
    `for _cmd in a b; do command -v "$_cmd" || { ...; exit 1; }; done` loop. Both are
    gates; only the loop hides the name from a substring search, so a test that greps
    for the literal fails a correct skill.

    Naming a command is not gating on it. Each shape must carry both the probe and a
    failing exit, or the name does not count — otherwise `for _cmd in h2t-x; do echo
    "$_cmd"; done` beside an unrelated `command -v` line would read as a gate.
    """
    gated = set()
    for names, body in re.findall(r"for _cmd in ([^;\n]+); do(.*?)done", text, re.S):
        if 'command -v "$_cmd"' in body and "exit 1" in body:
            gated |= {n for n in names.split() if n.startswith("h2t-")}
    for name, tail in re.findall(r"command -v ([\w.-]+)[^\n]*\|\|(.{0,200})", text, re.S):
        if "exit 1" in tail:
            gated.add(name)
    return gated


@pytest.mark.parametrize(("skill", "cli"), sorted(CLI_BACKED.items()))
def test_skill_gates_on_its_cli(skill, cli):
    text = (Path("plugins") / skill / "SKILL.md").read_text(encoding="utf-8")
    gated = _gated_commands(text)
    assert gated, f"{skill}: no gate found at all — the parser is broken, not the skill"
    assert cli in gated, f"{skill} does not gate on {cli}; it gates on {sorted(gated)}"


def test_no_h2t_core_skill_hand_rolls_a_python_probe():
    """`$H2T_PYTHON` predates the entry points. A skill that still resolves an interpreter
    by hand has a second way to run its code, and the two can disagree."""
    skills = sorted(Path("plugins/h2t-core/skills").glob("*/SKILL.md"))
    assert skills, "no SKILL.md files found — the glob is broken, not the skills"
    offenders = [p.as_posix() for p in skills if "H2T_PYTHON" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"still hand-rolling an interpreter: {offenders}"


def _scaffold_hook_entries() -> dict:
    """Load scaffold_project through the resolver rather than sys.path.

    `tests/scaffold/` puts that directory on sys.path, so a bare `import scaffold_project`
    here passes only when both directories run in the same session — green for the wrong
    reason, and red the moment someone runs `pytest tests/core/` alone.
    """
    return plugin_entrypoints.load_plugin_module(
        "skills/scaffold-project/scripts/scaffold_project.py"
    )._HOOK_ENTRIES


def test_scaffold_gates_on_every_command_it_writes_into_settings():
    """scaffold-project emits `h2t-hook <name>` into a project's settings.json.

    The gate must cover it. Between pulling the plugin and re-running
    `uv tool install`, the skill would otherwise happily create a project whose hooks
    name a command that is not on PATH — and a hook that cannot start is silent.
    Deriving the requirement from _HOOK_ENTRIES keeps the two from drifting apart.
    """
    _HOOK_ENTRIES = _scaffold_hook_entries()

    emitted = {
        command["command"].split()[0]
        for entries in _HOOK_ENTRIES.values()
        for entry in entries
        for command in entry["hooks"]
        if command["command"].startswith("h2t-")
    }
    assert emitted, "no h2t-* command emitted — the probe is broken, not the code"
    text = Path("plugins/h2t-core/skills/scaffold-project/SKILL.md").read_text(encoding="utf-8")
    gated = _gated_commands(text)
    missing = emitted - gated
    assert not missing, f"scaffold writes {sorted(missing)} but does not gate on it"


def test_hook_entry_resolves_the_handlers_scaffold_writes():
    """scaffold-project writes `h2t-hook on-stop` and `h2t-hook post-git-commit-docs-lint`
    into other people's settings.json. A name that does not resolve makes those hooks dead
    on arrival, and a dead hook is silent."""
    _HOOK_ENTRIES = _scaffold_hook_entries()

    named = [
        command["command"].split()[1]
        for entries in _HOOK_ENTRIES.values()
        for entry in entries
        for command in entry["hooks"]
    ]
    assert named, "no hook commands read — the probe is broken, not the code"
    for handler in named:
        assert plugin_entrypoints.plugin_script_path(f"hooks-handlers/{handler}").is_file()
