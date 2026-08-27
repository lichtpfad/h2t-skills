"""No shipped file may name a directory that exists on one machine (#434).

#434 was filed for this and read as done. Nothing was watching, so twelve occurrences
survived — and three of them were behaviour, not prose: the `kb` skill defaulted its
knowledge base to `C:/dev/research-kb`, and `project-audit` defaulted `projects.yaml`
to `C:/dev/h2t-landings/`. On every machine but one those resolve to nothing, and the
failure lands far from its cause.

This is a ratchet, not a wall. `EXPECTED` lists what is still there with the reason,
and `test_known_debt_is_not_stale` fails when an entry is fixed without being removed —
otherwise the list outlives the problem and the next reader trusts it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Everything that ships. `plugins/` alone was the first version of this list, and
# `h2t_ops/` — the package behind the nine CLI entry points, the first thing a stranger
# installs — was outside it. The hint in `visual_ocr.py` telling them to install from
# `C:/dev/h2t-tools` was found by a grep, not by this test.
SHIPPED_ROOTS = [ROOT / "plugins", ROOT / "h2t_ops", ROOT / "lib", ROOT / "scripts"]

# A drive-letter dev root, or a home directory with a name in it.
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, `/Users/stani/` is a person. A one-letter home does not exist on any machine
# this could leak.
AUTHOR_PATH = re.compile(
    r"[A-Za-z]:[\\/]dev\b|/(?:Users|home)/[A-Za-z_][A-Za-z0-9_-]+/", re.IGNORECASE
)

SKIP_NAMES = {"CHANGELOG.md"}
SCANNED_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ""}

# path -> why an author path is expected there. Two kinds, and the distinction matters:
# prose recording a default that was removed, and fixtures that assert an old Windows
# path still resolves — the second is not debt, it is the portability proof.
EXPECTED = {
    "plugins/h2t-core/skills/init-project/scripts/detect_project.py":
        "comment recording the C:/dev anchor these patterns replaced",
    "plugins/h2t-core/skills/init-project/scripts/test_detect.py":
        "deliberate: fixtures proving a C:/dev path resolves the same as ~/Projects",
    "plugins/h2t-dev/lib/docs/common.py":
        "comment recording the removed C:/dev default",
    "plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py":
        "comment recording the removed _DEV_ROOT default",
    "plugins/h2t-core/skills/scaffold-project/SKILL.md":
        "prose recording the removed C:/dev/{id} default",
}


def _offenders() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in SHIPPED_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
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
                found[str(path.relative_to(ROOT))] = hits
    return found


def test_no_new_author_paths_ship():
    offenders = {k: v for k, v in _offenders().items() if k not in EXPECTED}
    assert not offenders, "author-machine paths in shipped files:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_expected_list_is_not_stale():
    """An entry that is now clean means the list lies to the next reader."""
    clean = set(EXPECTED) - set(_offenders())
    assert not clean, f"EXPECTED names files that are already clean: {sorted(clean)}"
