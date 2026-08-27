"""A skill's bash must run on any host, so it may not name a plugin path.

`CLAUDE_PLUGIN_ROOT` is exported to plugin *hook* commands, not to the bash a skill
runs (Codex documents this; Claude Code is inconsistent about it). Empty, it turns
`source "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"` into `source "/scripts/x.sh"` — an error
naming the filesystem root instead of the real cause. The portable surface is an
installed command on PATH (#349, #350, #352, #357).

Prose may still discuss the variable; only executable blocks are checked.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

BASH_BLOCK = re.compile(r"^```(?:bash|sh|shell)\r?\n(.*?)^```", re.M | re.S)
FORBIDDEN = (
    ("CLAUDE_PLUGIN_ROOT", "the harness does not export it to skill bash"),
    ("CLAUDE_SKILL_DIR", "the harness does not export it to skill bash either (#456)"),
    (".claude/plugins/cache", "the plugin cache path is host- and version-specific"),
)


def _shipped_skills():
    plugins = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"]
    for plugin in plugins:
        for skill_dir in sorted((ROOT / "plugins" / plugin["name"] / "skills").iterdir()):
            manifest = skill_dir / "SKILL.md"
            if manifest.is_file():
                yield plugin["name"], skill_dir.name, manifest


SHIPPED = list(_shipped_skills())


# Not yet migrated (#360). h2t-dev needs commands *and* a way to reach reference docs,
# which needs a design decision rather than the mechanical swap #357 applied to the
# lifecycle skills. h2t-creative left this list by shipping bin/h2t-creative — an asset
# base is reachable from a script that knows its own location. This list may only shrink:
# a skill that gets fixed must be deleted from it, or the test below fails as a stale entry.
KNOWN_DEBT = frozenset({
    "h2t-dev:docs-lint",
    "h2t-dev:docs-sync-labels",
    "h2t-dev:milestone-closure",
    # CLAUDE_SKILL_DIR joined FORBIDDEN once it was measured empty too (#456). These four
    # resolve scripts through it and need a bin/ entry each, the way h2t-creative got one.
    "h2t-edu:process-transcripts",
    "h2t-edu:convert-meeting-transcript",
    "h2t-edu:youtube-transcript",
    "h2t-arch:drawio",
})


def _plugin_paths_in(manifest: Path) -> list[str]:
    offenders = []
    for block in BASH_BLOCK.findall(manifest.read_text(encoding="utf-8")):
        for needle, why in FORBIDDEN:
            if needle in block:
                line = next(ln.strip() for ln in block.splitlines() if needle in ln)
                offenders.append(f"{needle} ({why}): {line}")
    return offenders


@pytest.mark.parametrize(
    "plugin,directory,manifest",
    SHIPPED,
    ids=[f"{p}:{d}" for p, d, _ in SHIPPED],
)
def test_skill_bash_names_no_plugin_path(plugin, directory, manifest):
    if f"{plugin}:{directory}" in KNOWN_DEBT:
        pytest.skip("known debt, tracked in #360")
    offenders = _plugin_paths_in(manifest)
    assert not offenders, f"{manifest} runs a plugin path:\n  " + "\n  ".join(offenders)


def test_known_debt_has_no_stale_entries():
    """A ratchet: fixing a skill without dropping it from KNOWN_DEBT fails here.

    Otherwise the list silently outlives the problem and the next reader trusts it.
    """
    ids = {f"{p}:{d}" for p, d, _ in SHIPPED}
    unknown = KNOWN_DEBT - ids
    assert not unknown, f"KNOWN_DEBT names skills that do not ship: {sorted(unknown)}"

    clean = [
        f"{p}:{d}" for p, d, m in SHIPPED
        if f"{p}:{d}" in KNOWN_DEBT and not _plugin_paths_in(m)
    ]
    assert not clean, f"already portable — remove from KNOWN_DEBT: {sorted(clean)}"
