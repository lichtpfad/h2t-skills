"""No skill may build a path to an interpreter the installer never creates (#449).

Eight SKILL.md files probed for `~/.h2t/venv/bin/python` and `~/.h2t/venv/Scripts/
python.exe`, falling back to nothing when neither existed. `setup_h2t.py` contains the
word `venv` zero times, so the contract was satisfied only where the directory had been
built by hand — on the author's machine, where all four undeclared packages happened to
be installed. Everywhere else the variable stayed empty and the command ran without an
interpreter, or worse, under a system python without the dependencies.

`h2t-arch/drawio` had the same defect in a different shape: `python -c "import drawpyo"`
as a guard, where bare `python` is not on PATH on macOS at all — so the probe failed with
`command not found` and advised `pip install drawpyo`.

The replacement declares each dependency at the point of use: `uv run --no-project --with
<pkg> python <script>`. uv is already required by the documented install path, the
environment is ephemeral and cached, and there is no second environment to repair.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted((ROOT / "plugins").rglob("SKILL.md"))

# A path assembled toward an interpreter, in any of the shapes that were in the tree.
INTERPRETER_PATH = re.compile(
    r"\.h2t/venv|H2T_PYTHON|\.claude/skills/\.venv|venv/(?:bin/python|Scripts/python\.exe)"
)


def test_skills_exist():
    """Guards the walk itself: an empty list would make every check below vacuous."""
    assert len(SKILLS) > 20, f"only {len(SKILLS)} SKILL.md found — is the glob right?"


def test_no_skill_builds_an_interpreter_path():
    offenders = []
    for path in SKILLS:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # A line that only prints a path is a message to the user, not something the
            # skill runs — `voice-eval` tells the operator which variable to set, and
            # naming the shape of the value there is the point of the message.
            if line.lstrip().startswith("echo "):
                continue
            if INTERPRETER_PATH.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}  {line.strip()}")
    assert not offenders, (
        "skills building a path to an interpreter nothing installs:\n"
        + "\n".join(offenders)
        + "\n\nUse: uv run --no-project --with <pkg> python <script>"
    )


def test_every_uv_run_declares_no_project():
    """`uv run` inside a directory holding a pyproject.toml would build *that* project.

    Skills run against the user's repository (`--root $(pwd)`), which frequently is a
    Python project, so the flag is what keeps the environment the skill's own.

    Only lines that *are* an invocation are checked: prose naming `uv run --with` while
    explaining a dependency is not a command, and reading it as one made this check fire
    on two documentation sentences.
    """
    offenders = []
    for path in SKILLS:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip().lstrip("`$").lstrip()
            invocation = (
                stripped.startswith("uv run") or stripped.startswith('RUN="uv run')
            ) and "python" in line
            if invocation and "--no-project" not in line:
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}  {line.strip()}")
    assert not offenders, "uv run without --no-project:\n" + "\n".join(offenders)
