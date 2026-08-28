"""The skill index injected at session start must name only skills that exist.

`inject-h2t-context` writes a hand-maintained list of `plugin:skill` names into the context
of every session. Nothing kept it in step with the tree: `bc335d8` deliberately removed
`SKILL.md` from four skills ("demote to CLI"), the index kept advertising `h2t-dev:docs-init`,
and four months later it was still there — a name that looks reachable, costs a turn, and
resolves to nothing (#458).

An audit answers "how many are wrong now". This answers "did it get worse".
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "plugins" / "h2t-core" / "hooks-handlers" / "inject-h2t-context"
NAME = re.compile(r"\bh2t-[a-z]+:[a-z][a-z-]*\b")


def _advertised() -> list[str]:
    return sorted(set(NAME.findall(INDEX.read_text(encoding="utf-8"))))


def test_index_is_not_empty():
    """Control: an empty match set would make the next test vacuously green."""
    assert len(_advertised()) >= 8, "index parsed as near-empty — the regex, not the tree"


def test_every_advertised_skill_exists():
    missing = []
    for full in _advertised():
        plugin, skill = full.split(":", 1)
        if not (REPO / "plugins" / plugin / "skills" / skill / "SKILL.md").is_file():
            missing.append(full)
    assert not missing, (
        f"{INDEX.relative_to(REPO)} advertises skills with no SKILL.md: {missing}. "
        "Either the skill was removed and the index was not updated, or the name is a typo. "
        "A directory holding only scripts/ is not a skill — the harness cannot reach it."
    )
