"""Every ${CLAUDE_PLUGIN_ROOT} path a shipped skill names must exist (#439).

#433 fixed nine hints that pointed at a plugin which was never shipped, and left a guard
for skill directories without a SKILL.md. It did not cover the paths *inside* a SKILL.md,
and one was already wrong: github-issues reached for
`${CLAUDE_PLUGIN_ROOT}/../docs-sync-labels/...`, which climbs out of the plugin. The
author had assumed the variable points at the skill directory; the hooks show it points at
the plugin root.

An agent that follows a dead reference does not fail loudly — it reads nothing and carries
on with less than it was told it had.
"""
from __future__ import annotations

import re
from pathlib import Path

PLUGINS = Path(__file__).parents[2] / "plugins"
REF = re.compile(r'\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s`"\')]+)')


def _references() -> list[tuple[Path, str, Path]]:
    found = []
    for skill_md in sorted(PLUGINS.rglob("SKILL.md")):
        if skill_md.parent.parent.name != "skills":
            continue
        plugin_root = skill_md.parents[2]
        for match in REF.finditer(skill_md.read_text(encoding="utf-8")):
            rel = match.group(1).lstrip("/")
            if "*" in rel or "<" in rel:  # a pattern, not a path
                continue
            found.append((skill_md, rel, (plugin_root / rel).resolve()))
    return found


def test_the_scan_finds_references_at_all():
    """Without this, an empty result would read as 'nothing broken'."""
    assert len(_references()) >= 5


def test_every_referenced_path_exists():
    dead = [
        f"{md.relative_to(PLUGINS)} -> {rel}"
        for md, rel, target in _references()
        if not target.exists()
    ]
    assert not dead, "dead references in shipped skills:\n" + "\n".join(dead)


def test_no_reference_climbs_out_of_its_plugin():
    """`..` in these paths means the author assumed the variable names the skill dir."""
    climbers = [
        f"{md.relative_to(PLUGINS)} -> {rel}"
        for md, rel, _ in _references()
        if ".." in Path(rel).parts
    ]
    assert not climbers, "references climbing out of the plugin:\n" + "\n".join(climbers)
