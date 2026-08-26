"""A directory under skills/ is either a skill or a known exception.

`docs-cleanup` sat under skills/ for four months with no SKILL.md — demoted to
"CLI" in 31395f5 without ever becoming a CLI: no entry point, nothing on PATH,
no command file, and zero references from anywhere. Its README section
documented usage that could not run. Its 173 lines held `find_stale_plans` and
a git-mv-to-archive, which is `docs-lint retire`, rebuilt from scratch four
months later by someone who did not know it existed.

The list below is the same shape as `allowed_root_dirs` and `allowed_doc_dirs`:
a short white list where a new entry has to be argued for in a diff. Every one
of these is live code merely filed under skills/ — the second test proves that
by requiring a reference from outside its own directory.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Directory -> why it has no SKILL.md.
_CODE_NOT_SKILLS = {
    "h2t-dev/docs-index": "index.py — the navigation generator docs-lint calls",
    "h2t-dev/docs-init": "scaffolding scripts",
    "h2t-ops/drive": "connector scripts",
    "h2t-ops/meetgeek": "connector scripts and their tests",
}


def _skill_dirs() -> list[tuple[str, Path]]:
    out = []
    for plugin in sorted((ROOT / "plugins").iterdir()):
        skills = plugin / "skills"
        if not skills.is_dir():
            continue
        for d in sorted(skills.iterdir()):
            if d.is_dir():
                out.append((f"{plugin.name}/{d.name}", d))
    return out


def test_every_skill_dir_has_a_skill_md_or_is_a_known_exception():
    missing = [
        name for name, d in _skill_dirs()
        if not (d / "SKILL.md").is_file() and name not in _CODE_NOT_SKILLS
    ]
    assert not missing, (
        f"нет SKILL.md и нет в списке исключений: {missing}. "
        "Скилл без SKILL.md не грузится, вызвать его нельзя."
    )


def test_the_exceptions_are_actually_referenced():
    """An exception nothing calls is not an exception, it is a ghost.

    This is the control that would have caught docs-cleanup: it had zero
    references from outside its own directory, and every name on the list has
    at least one.
    """
    unreferenced = []
    for name in _CODE_NOT_SKILLS:
        plugin, skill = name.split("/")
        found = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-l", f"skills/{skill}/", "--",
             "plugins", "lib", "h2t_ops", "tests", "scripts", ".github"],
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.splitlines()
        outside = [f for f in found if not f.startswith(f"plugins/{plugin}/skills/{skill}/")]
        if not outside:
            unreferenced.append(name)
    assert not unreferenced, f"числятся кодом, но никем не вызываются: {unreferenced}"


def test_the_exception_list_has_no_stale_entries():
    """A name that no longer exists on disk must leave the list with its directory."""
    present = {name for name, _ in _skill_dirs()}
    stale = [n for n in _CODE_NOT_SKILLS if n not in present]
    assert not stale, f"в списке исключений, но директории нет: {stale}"
