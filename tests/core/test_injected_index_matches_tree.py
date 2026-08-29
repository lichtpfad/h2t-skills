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


# The same file carries paths, and the name guard above never looks at them. `~/.h2t/venv`
# was the interpreter contract until #449 deleted it; `resolve-h2t-python.sh` replaced it
# with a probe whose first candidate is `$H2T_PYTHON`. Nothing in the pack ever created the
# venv — `plugins/h2t-dev/CHANGELOG.md` says so outright — so on a machine that is not the
# author's, this line injects a path that does not exist into every session (#443).
DEAD_PATHS = ("~/.h2t/venv", "$HOME/.h2t/venv", ".h2t/venv")
PLUGINS = REPO / "plugins"
# A probe tests for the directory and falls through when it is absent; that is what a
# resolver does and it is correct. An instruction tells a human to use the path, and on
# every machine but one it sends them nowhere. Only probes are listed.
PROBES = {
    "plugins/h2t-core/scripts/resolve-h2t-python.sh": "the resolver — probing is its job",
    "plugins/h2t-core/scripts/update-plugin.sh": "probe with a python3 fallback",
    "plugins/h2t-dev/scripts/update-plugin.sh": "probe with a python3 fallback",
    "plugins/h2t-ops/scripts/update-plugin.sh": "probe with a python3 fallback",
}


def test_no_shipped_file_instructs_a_path_the_installer_never_creates():
    """Every shipped file, not just the index.

    Scoping this to one file was the first version, and it was wrong within the hour: the
    grep that verified the deploy hit `gather-on-skill`, whose failure message told the
    reader to "recreate ~/.h2t/venv" — the same dead contract, offered as the remedy. Only
    `scripts/resolve-h2t-python.sh` may name the path, because probing for a directory that
    may not exist is what a resolver does.
    """
    offenders = {}
    for path in sorted(PLUGINS.rglob("*")):
        if not path.is_file() or path.name == "CHANGELOG.md":
            continue
        rel = path.relative_to(REPO).as_posix()
        if rel in PROBES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = [p for p in DEAD_PATHS if p in text]
        if found:
            offenders[rel] = found
    assert not offenders, (
        f"files instructing a path the installer never creates: {offenders}. It survives only "
        "on machines that predate #449. Name the resolver, or /h2t-core:setup, instead."
    )


# README prints the same index verbatim, for a harness that runs no hooks (#443). Two copies
# of one artifact drift silently; this is the seam, so it is tested as a round trip rather
# than each side asserting about itself.
README = REPO / "README.md"


def _readme_index() -> str:
    text = README.read_text(encoding="utf-8")
    marker = "H2T SKILLS — invoke with the Skill tool when relevant:"
    start = text.index(marker)
    return text[start : text.index("```", start)].rstrip()


def _hook_index() -> str:
    text = INDEX.read_text(encoding="utf-8")
    start = text.index('INDEX="') + len('INDEX="')
    return text[start : text.index('"\n', start)].rstrip()


def test_readme_prints_the_index_the_hook_injects():
    assert _readme_index() == _hook_index(), (
        "README.md and inject-h2t-context disagree about the skill index. The README copy is "
        "what a reader gets when the hook does not fire; a stale copy is worse than none."
    )
