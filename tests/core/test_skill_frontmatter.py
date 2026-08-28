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
    not skills.
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


# --- required fields, key schema, description budget (#464) ----------------------------

REQUIRED = ("name", "description", "compatibility", "metadata")
ALLOWED = set(REQUIRED) | {"status"}
DESC_MAX = 500

# Every skill description sits in the context of every session, so length here is a
# standing cost, not a one-off. These three exceed the budget and are not being rewritten
# yet: shortening a description changes when the skill is triggered, which is a behavioural
# change and wants its own measurement. The list may only shrink — a shortened description
# must be deleted from it, or test_description_debt_has_no_stale_entries fails.
DESC_DEBT = {
    "h2t-ops:connectors": 639,
    "h2t-ops:research": 605,
    "h2t-core:scaffold-project": 555,
}


def _frontmatter(manifest: Path) -> dict:
    import yaml  # noqa: PLC0415 — test-only dependency, imported where it is used

    block = re.match(r"^---\n(.*?)\n---\n", manifest.read_text(encoding="utf-8"), re.S)
    assert block, f"{manifest} has no frontmatter fence"
    return yaml.safe_load(block.group(1)) or {}


@pytest.mark.parametrize(
    "plugin,directory,manifest", SHIPPED, ids=[f"{p}:{d}" for p, d, _ in SHIPPED]
)
def test_frontmatter_carries_the_required_fields(plugin, directory, manifest):
    """`compatibility` is where an agent reads a skill's external requirements before
    running anything. Left as the string "Claude Code" it says nothing; agent-profile and
    autonomous-run shipped without the field at all until #464."""
    fm = _frontmatter(manifest)
    missing = [k for k in REQUIRED if k not in fm]
    assert not missing, f"{manifest} is missing {missing}"


@pytest.mark.parametrize(
    "plugin,directory,manifest", SHIPPED, ids=[f"{p}:{d}" for p, d, _ in SHIPPED]
)
def test_frontmatter_declares_no_key_outside_the_schema(plugin, directory, manifest):
    """node-researcher carried a `trigger:` list of five phrases that nothing read — the
    harness takes triggers from `description`. A key outside the schema is not a feature,
    it is a misunderstanding with a long life."""
    extra = sorted(set(_frontmatter(manifest)) - ALLOWED)
    assert not extra, f"{manifest} declares {extra}, which nothing reads"


@pytest.mark.parametrize(
    "plugin,directory,manifest", SHIPPED, ids=[f"{p}:{d}" for p, d, _ in SHIPPED]
)
def test_description_stays_within_budget(plugin, directory, manifest):
    full = f"{plugin}:{directory}"
    length = len((_frontmatter(manifest).get("description") or "").strip())
    if full in DESC_DEBT:
        pytest.skip(f"known debt: {length} chars, tracked in #464")
    assert length <= DESC_MAX, (
        f"{manifest} description is {length} chars, over the {DESC_MAX} budget. "
        "Every description is loaded every session; three long ones cost what ten short "
        "ones do."
    )


def test_description_debt_has_no_stale_entries():
    """A ratchet: shortening a description without dropping it from DESC_DEBT fails here,
    so the list cannot outlive the problem it records."""
    fixed = []
    for plugin, directory, manifest in SHIPPED:
        full = f"{plugin}:{directory}"
        if full not in DESC_DEBT:
            continue
        length = len((_frontmatter(manifest).get("description") or "").strip())
        if length <= DESC_MAX:
            fixed.append(full)
    assert not fixed, f"now within budget — remove from DESC_DEBT: {fixed}"
