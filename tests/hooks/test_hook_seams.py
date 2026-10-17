"""hooks.json entries <-> h2t_ops/hooks modules (spec §9.2).

Every handler a hooks.json names must be a HANDLERS key. Every HANDLERS key must be named
by a hooks.json, or it is code no event reaches — except the handlers whose callers live
outside any plugin, listed in NOT_IN_HOOKS_JSON. And every event a handler is subscribed to
must have a recorded case, so "the expected output of each hook on each event" (§2.8) is
checked for the events that actually fire. hooks.json names `hooks/run <name>`; the form
itself is pinned by test_hooks_json.py.
"""
import json
import re
from pathlib import Path

from h2t_ops import hooks
from tests.hooks import hook_cases as hc

ROOT = Path(__file__).resolve().parents[2]
# Not hooks.json entries. Git pre-commit hooks (scripts/hooks/pre-commit, ~/.h2t/git-hooks):
GIT_HOOKS = {"layout-precommit", "bulk-precommit", "secrets-precommit"}
# written by scaffold-project into a project's .claude/settings.json:
SETTINGS_HOOKS = {"on-stop", "post-git-commit-docs-lint"}
NOT_IN_HOOKS_JSON = GIT_HOOKS | SETTINGS_HOOKS
_NAME = re.compile(r"hooks/run\"?\s+([A-Za-z0-9_.-]+)")


def subscriptions() -> dict[str, set[str]]:
    """handler name -> the events hooks.json subscribes it to, over every plugin."""
    found: dict[str, set[str]] = {}
    for path in sorted(ROOT.glob("plugins/*/hooks/hooks.json")):
        for event, groups in json.loads(path.read_text(encoding="utf-8"))["hooks"].items():
            for group in groups:
                for hook in group.get("hooks", []):
                    match = _NAME.search(hook.get("command", ""))
                    assert match, f"{path}: cannot read a handler name from {hook!r}"
                    found.setdefault(match.group(1), set()).add(event)
    return found


def test_the_reader_finds_the_name():
    """Control for the regex: a zero here would make every assertion below vacuous."""
    assert _NAME.search('bash "${CLAUDE_PLUGIN_ROOT}/hooks/run" gather-on-skill 29'
                        ).group(1) == "gather-on-skill"
    assert len(subscriptions()) >= 9


def test_every_hooks_json_name_resolves():
    unresolved = set(subscriptions()) - set(hooks.HANDLERS)
    assert not unresolved, f"hooks.json names a handler with no module: {sorted(unresolved)}"


def test_every_handlers_key_is_reached_by_a_hooks_json_entry():
    unreached = set(hooks.HANDLERS) - set(subscriptions()) - NOT_IN_HOOKS_JSON
    assert not unreached, f"HANDLERS keys no hooks.json entry calls: {sorted(unreached)}"


def test_the_exceptions_are_registered_and_no_hooks_json_names_them():
    """They are `Command`s, run with their own 3.x contract; a hooks.json entry for one
    would feed it an event it does not read."""
    assert NOT_IN_HOOKS_JSON <= set(hooks.HANDLERS)
    assert not NOT_IN_HOOKS_JSON & set(subscriptions())
    for name in sorted(NOT_IN_HOOKS_JSON):
        assert isinstance(hooks.HANDLERS[name], hooks.Command), name


def test_every_subscribed_event_has_a_recorded_case():
    recorded: dict[str, set[str]] = {}
    for name, stem, _ in hc.all_cases():
        recorded.setdefault(name, set()).add(stem.split(".", 1)[0])
    for name, events in sorted(subscriptions().items()):
        missing = events - recorded.get(name, set())
        assert not missing, f"{name}: no recorded case for {sorted(missing)}"
