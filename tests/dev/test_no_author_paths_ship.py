"""No shipped file may name a directory that exists on one machine (#434).

#434 was filed for this and read as done. Nothing was watching, so twelve occurrences
survived — and three of them were behaviour, not prose: the `kb` skill defaulted its
knowledge base to `C:/dev/research-kb`, and `project-audit` defaulted `projects.yaml`
to `C:/dev/h2t-landings/`. On every machine but one those resolve to nothing, and the
failure lands far from its cause.

This is a ratchet, not a wall. `KNOWN_DEBT` lists what is still there with the reason,
and `test_known_debt_is_not_stale` fails when an entry is fixed without being removed —
otherwise the list outlives the problem and the next reader trusts it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "plugins"

# A drive-letter dev root, or a home directory with a name in it.
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, `/Users/stani/` is a person. A one-letter home does not exist on any machine
# this could leak.
AUTHOR_PATH = re.compile(
    r"[A-Za-z]:[\\/]dev\b|/(?:Users|home)/[A-Za-z_][A-Za-z0-9_-]+/", re.IGNORECASE
)

SKIP_NAMES = {"CHANGELOG.md"}

# path -> why it is still here. Each is a design question, not a rename.
KNOWN_DEBT = {
    # The domain-detection table keys on the author's Windows layout. Rewriting it is
    # #444 — what replaces "where my repos live" is not a path substitution.
    "h2t-core/skills/init-project/scripts/detect_project.py":
        "domain patterns key on C:/dev/* — #444",
    "h2t-core/skills/init-project/scripts/test_detect.py":
        "asserts the patterns above — moves with them (#444)",
    # Prose explaining a default that was removed. Harmless, but it keeps the literal
    # in the tree, so it is listed rather than silently allowed.
    "h2t-dev/lib/docs/common.py": "comment recording the removed C:/dev default",
    "h2t-core/skills/scaffold-project/scripts/scaffold_project.py":
        "comment recording the removed _DEV_ROOT default",
    "h2t-core/skills/scaffold-project/SKILL.md":
        "prose recording the removed C:/dev/{id} default",
}


def _offenders() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(SHIPPED.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        if path.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".json", ".sh", ""}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = [
            f"{lineno}: {line.strip()[:110]}"
            for lineno, line in enumerate(text.splitlines(), 1)
            if AUTHOR_PATH.search(line)
        ]
        if hits:
            found[str(path.relative_to(SHIPPED))] = hits
    return found


def test_no_new_author_paths_ship():
    offenders = {k: v for k, v in _offenders().items() if k not in KNOWN_DEBT}
    assert not offenders, "author-machine paths in shipped files:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_known_debt_is_not_stale():
    """Fixing an entry without deleting it leaves a list that lies to the next reader."""
    clean = set(KNOWN_DEBT) - set(_offenders())
    assert not clean, f"KNOWN_DEBT names files that are already clean: {sorted(clean)}"
