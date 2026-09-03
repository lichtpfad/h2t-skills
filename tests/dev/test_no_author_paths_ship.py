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
from pathlib import Path, PurePath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
# Everything that ships. `plugins/` alone was the first version of this list, and
# `h2t_ops/` — the package behind the nine CLI entry points, the first thing a stranger
# installs — was outside it. The hint in `visual_ocr.py` telling them to install from
# `C:/dev/h2t-tools` was found by a grep, not by this test.
# Two patterns, two scopes, because they are two different problems.
#
# A home directory with a person's name in it is personal data wherever it sits, and
# publication makes the whole tree readable — 185 occurrences lived under docs/, tests/
# and tools/ while the first version of this file walked four directories holding none
# of them (#417).
#
# `C:/dev` is a portability defect in code and merely noise in prose. Enforcing it over
# docs/ would mean rewriting several hundred lines of historical reports to no benefit;
# the audit that counted them said the same.
CODE_ROOTS = [ROOT / "plugins", ROOT / "h2t_ops", ROOT / "lib", ROOT / "scripts"]
PROSE_ROOTS = [ROOT / "docs", ROOT / "tests", ROOT / "tools",
                # The two files a stranger opens first, and the only shipped prose that
                # lived outside every root above (#443).
                ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "CONTRIBUTING.md"]

DEV_ROOT_PATH = re.compile(r"[A-Za-z]:[\\/]dev\b", re.IGNORECASE)
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, a real account name is a person.
PLACEHOLDER_HOMES = r"(?:user|users|testuser|someone|username|me|you|example|dev|<user>)"
HOME_PATH = re.compile(
    rf"/(?:Users|home)/(?!{PLACEHOLDER_HOMES}/)[A-Za-z_][A-Za-z0-9_-]+/", re.IGNORECASE
)

# A drive-letter dev root, or a home directory with a name in it.
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, a real account name is a person. A one-letter home does not exist on any machine
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


def _rel_key(path: PurePath, root: PurePath) -> str:
    """The key `EXPECTED` is looked up by, and it must be spelled the same on every runner.

    `str()` on a `WindowsPath` yields backslashes while `EXPECTED` is written with forward
    slashes, so on the Windows leg every allow-listed file missed the lookup at once and
    both assertions below fired from opposite directions — one naming the five as
    offenders, the other naming the same five as already clean (#471).
    """
    return path.relative_to(root).as_posix()


def _offenders(roots, pattern) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in roots:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(root.rglob("*"))
        else:
            continue
        for path in candidates:
            if not path.is_file() or path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if path.lstat().st_mode & 0o170000 == 0o120000:
                continue
            hits = [
                f"{lineno}: {line.strip()[:110]}"
                for lineno, line in enumerate(text.splitlines(), 1)
                if not line.lstrip().startswith("echo ") and pattern.search(line)
            ]
            if hits:
                found[_rel_key(path, ROOT)] = hits
    return found


def test_no_author_dev_root_in_shipped_code():
    offenders = {k: v for k, v in _offenders(CODE_ROOTS, DEV_ROOT_PATH).items()
                 if k not in EXPECTED}
    assert not offenders, "a dev root that exists on one machine:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_no_home_directory_names_anywhere():
    """A person's home directory is personal data in prose as much as in code."""
    roots = CODE_ROOTS + PROSE_ROOTS
    offenders = {k: v for k, v in _offenders(roots, HOME_PATH).items() if k not in EXPECTED}
    assert not offenders, "a home directory naming a person:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_expected_list_is_not_stale():
    """An entry that is now clean means the list lies to the next reader."""
    seen = set(_offenders(CODE_ROOTS, DEV_ROOT_PATH)) | set(
        _offenders(CODE_ROOTS + PROSE_ROOTS, HOME_PATH))
    clean = set(EXPECTED) - seen
    assert not clean, f"EXPECTED names files that are already clean: {sorted(clean)}"


def test_offender_keys_are_posix_on_any_platform():
    """A Windows runner must produce the same key a POSIX runner does.

    `PureWindowsPath` models that runner from here: `str()` on it yields backslashes,
    which is the whole of #471's first defect.
    """
    win = PureWindowsPath(r"C:\\repo\\plugins\\h2t-core\\skills\\x\\scripts\\y.py")
    assert _rel_key(win, PureWindowsPath(r"C:\\repo")) == "plugins/h2t-core/skills/x/scripts/y.py"
