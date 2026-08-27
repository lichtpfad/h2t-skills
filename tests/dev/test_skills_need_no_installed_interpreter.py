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


def test_every_uv_run_names_its_project():
    """`uv run` must say which project it runs in — never inherit it from the directory.

    Left implicit, uv builds whatever project the working directory happens to hold, and
    skills run against the user's repository (`--root $(pwd)`), which frequently is one.

    Two answers are correct and they are not interchangeable. `--no-project` is for a
    script that ships with this pack: its dependencies come from `--with`, and the user's
    repository must not be built at all. `--project <path>` is for a script that belongs
    to the target project — `node-researcher` runs `${PROJECT_ROOT}/scripts/research.py`,
    which this pack does not ship and whose dependencies are that project's.

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
            names_project = "--no-project" in line or "--project" in line
            if invocation and not names_project:
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}  {line.strip()}")
    assert not offenders, (
        "uv run that does not name its project (--no-project or --project <path>):\n"
        + "\n".join(offenders)
    )

# An interpreter in command position: at the start of a line, or after a pipe, `&&`,
# `;`, or the opening of a command substitution. `python-docx` and `python-dotenv` are
# package names and must not match, so the word has to end there.
BARE_INTERPRETER = re.compile(
    r"(?:^|[;&|(]|\$\()\s*(?:python3?|py)(?=\s|$)"
)


def test_no_skill_invokes_a_bare_interpreter():
    """`python` is not on PATH on macOS at all, and `python3` is not on Windows.

    Every invocation goes through `uv run`, which supplies the interpreter. This is the
    half the first version of this file missed: it forbade *paths* to an interpreter and
    said nothing about calling one by name, so reverting `node-researcher` to `python3`
    left the suite green. The red run is what showed the gap — a test believed on its
    green alone would have shipped the hole.

    A fenced ```python block is a syntax-highlighting hint, not a command, and prose
    naming the defect this test guards against is not a command either. Both are skipped
    by requiring the word to sit in command position on a line that is not fenced.
    """
    offenders = []
    for path in SKILLS:
        in_python_fence = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_python_fence = stripped[3:].strip().lower().startswith("python")
                continue
            if in_python_fence:
                continue
            if "uv run" in line or "$RUN" in line or "_PYTHON" in line:
                continue
            if BARE_INTERPRETER.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}  {stripped}")
    assert not offenders, (
        "skills calling an interpreter by name:\n"
        + "\n".join(offenders)
        + "\n\nUse: uv run --no-project --python 3.11 python <script>"
    )
