"""A shipped skill must not build a path out of a variable the harness never sets.

`CLAUDE_PLUGIN_ROOT` and `CLAUDE_SKILL_DIR` are empty in the bash a skill runs. Measured
2026-08-28 on Claude Code 2.1.247 (macOS) and confirmed the same day on 2.1.160 (Windows),
so this is not version dependent. The failure is silent and misdirecting:

    LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
    # LINT=/skills/docs-lint/scripts/lint.py — the filesystem root, not the plugin

The command runs, the file is absent, and the error names a path nobody wrote (#456, #459).

What the harness does provide is PATH: every installed plugin's bin/ is on it. So a skill
reaches its own files through its plugin's wrapper — `$(h2t-dev root)`, `$(h2t-creative root)`
— which derives the root from the wrapper's own location.

Mentioning the variable in prose is allowed; this checks only the shape that constructs a
path from it.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = sorted(REPO.glob("plugins/h2t-*/skills/*/SKILL.md"))
PATH_BUILD = re.compile(r"\$\{?CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}?/")


def test_skills_were_discovered():
    """Control: an empty glob would make the next test vacuously green."""
    assert len(SKILLS) >= 25, f"only {len(SKILLS)} SKILL.md found — discovery, not the tree"


def test_regex_matches_the_known_defect():
    """Control: the pattern must fire on the exact line that shipped broken."""
    assert PATH_BUILD.search('LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"')
    assert PATH_BUILD.search('"$CLAUDE_SKILL_DIR/scripts/generate.py"')
    assert not PATH_BUILD.search("`${CLAUDE_PLUGIN_ROOT}` is not exported to skill bash")


def test_no_skill_builds_a_path_from_a_harness_variable():
    offenders = []
    for path in SKILLS:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PATH_BUILD.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}")
    assert not offenders, (
        "these lines build a path from a variable the harness leaves empty, so the path "
        f"resolves against the filesystem root: {offenders}. Use the plugin's PATH wrapper "
        "instead — $(h2t-dev root), $(h2t-creative root), $(h2t-arch root)."
    )
