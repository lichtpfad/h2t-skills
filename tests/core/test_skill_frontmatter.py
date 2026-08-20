"""The `name:` a skill declares must be its bare directory name.

Claude Code composes the slash command as `<plugin>:<name>`. A SKILL.md that already
carries the plugin prefix gets it a second time — `/h2t-core:h2t-core:handoff`.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.M)


def _shipped_skills():
    """Every SKILL.md under a plugin the marketplace actually ships.

    Directories without a SKILL.md are script-only helpers (skills/drive, skills/docs-index),
    not skills; plugins/h2t/ is kept as a rollback archive and is not shipped.
    """
    plugins = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"]
    for plugin in plugins:
        skills_dir = ROOT / "plugins" / plugin["name"] / "skills"
        for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            manifest = skill_dir / "SKILL.md"
            if manifest.is_file():
                yield plugin["name"], skill_dir.name, manifest


SHIPPED = list(_shipped_skills())


def test_marketplace_ships_skills():
    assert SHIPPED, "no shipped SKILL.md found — discovery is broken, not the repo"


@pytest.mark.parametrize(
    "plugin,directory,manifest",
    SHIPPED,
    ids=[f"{p}:{d}" for p, d, _ in SHIPPED],
)
def test_skill_name_is_bare_directory_name(plugin, directory, manifest):
    match = NAME_RE.search(manifest.read_text(encoding="utf-8"))
    assert match, f"{manifest} declares no name:"
    declared = match.group(1).strip().strip("\"'")
    assert ":" not in declared, (
        f"{manifest} declares name: {declared!r} — the harness prepends '{plugin}:' itself, "
        f"so this renders as /{plugin}:{declared}"
    )
    assert declared == directory, f"{manifest} declares name: {declared!r}, directory is {directory!r}"
