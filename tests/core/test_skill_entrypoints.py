import re
from pathlib import Path

import pytest

from h2t_ops.lifecycle import scaffold_project

# The console scripts no longer delegate to plugin scripts through run_plugin_main; they
# call h2t_ops.lifecycle. That is checked in tests/lifecycle/test_entrypoints_use_package.py.


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
    return scaffold_project._HOOK_ENTRIES


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
    from h2t_ops.hooks import HANDLERS
    for handler in named:
        assert handler in HANDLERS, handler
