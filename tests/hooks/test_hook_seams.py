"""hooks.json entries <-> h2t_ops/hooks modules (spec §9.2).

Every handler a hooks.json names must resolve: to a HANDLERS key, which runs in the
package, or to a legacy handler that Task 12 moves. Every HANDLERS key must be named by a
hooks.json, or it is code no event reaches. And every event a handler is subscribed to
must have a recorded case, so "the expected output of each hook on each event" (§2.8) is
checked for the events that actually fire. Today's hooks.json names `hooks-handlers/<name>`;
after Task 12 it names `hooks/run <name>`. Both spellings are read.
"""
import json
import re
from pathlib import Path

from h2t_ops import hooks
from tests.hooks import hook_cases as hc

ROOT = Path(__file__).resolve().parents[2]
HANDLER_DIR = ROOT / "plugins" / "h2t-core" / "hooks-handlers"
# Not hooks.json entries: git hooks and the handlers scaffold-project writes into a
# project's settings. They keep the 3.x path through h2t-hook until Task 12.
LEGACY = {"layout-precommit", "bulk-precommit", "secrets-precommit", "on-stop",
          "post-git-commit-docs-lint"}
_NAME = re.compile(r"(?:hooks-handlers/|hooks/run\"?\s+)([A-Za-z0-9_.-]+)")


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


def test_the_reader_finds_both_spellings():
    """Control for the regex: a zero here would make every assertion below vacuous."""
    assert _NAME.search('bash "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/plan-closer"').group(1) == "plan-closer"
    assert _NAME.search('H2T_HOOK_TIMEOUT=9 bash "${CLAUDE_PLUGIN_ROOT}/hooks/run" gather-on-skill'
                        ).group(1) == "gather-on-skill"
    assert len(subscriptions()) >= 9


def test_every_hooks_json_name_resolves():
    unresolved = set(subscriptions()) - set(hooks.HANDLERS) - LEGACY
    assert not unresolved, f"hooks.json names a handler with no module: {sorted(unresolved)}"


def test_every_handlers_key_is_reached_by_a_hooks_json_entry():
    unreached = set(hooks.HANDLERS) - set(subscriptions())
    assert not unreached, f"HANDLERS keys no hooks.json entry calls: {sorted(unreached)}"


def test_legacy_names_still_have_their_3x_handler():
    assert not LEGACY & set(hooks.HANDLERS)
    for name in sorted(LEGACY):
        assert (HANDLER_DIR / name).is_file(), name


def test_every_subscribed_event_has_a_recorded_case():
    recorded: dict[str, set[str]] = {}
    for name, stem, _ in hc.all_cases():
        recorded.setdefault(name, set()).add(stem.split(".", 1)[0])
    for name, events in sorted(subscriptions().items()):
        if name in LEGACY:
            continue
        missing = events - recorded.get(name, set())
        assert not missing, f"{name}: no recorded case for {sorted(missing)}"
