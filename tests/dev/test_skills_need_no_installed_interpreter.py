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
import shlex
from pathlib import Path

import pytest

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


# --- calling an interpreter by name -------------------------------------------------
#
# Deciding this with one regex over the raw line was wrong twice over: skipping any line
# containing `uv run` let `$RUN good.py; python3 bad.py` through, and matching the word
# anywhere flagged prose. Both disappear if the question is asked properly — not "does
# this line mention python" but "is python the command being run".
#
# So: only inside fences that hold commands, split the line into commands, and look at
# the first word of each. `uv run ... python` begins with `uv`; `$RUN x.py` begins with a
# variable; `python-docx` is not the word. None of them need an exception.

COMMAND_FENCES = {"", "bash", "sh", "shell", "console", "zsh"}
INTERPRETERS = {"python", "python3", "py"}
WRAPPERS = {"env", "sudo", "time", "command", "exec", "nohup"}
# Wrapper options that consume the next token. `env -u FOO python3 x.py` runs
# python, and stopping at `FOO` is how that call read as a command of its own.
# The list is what these wrappers actually take; an unlisted one would leave the
# scan a token short, which the fixtures below would show.
VALUE_OPTIONS = {"-u", "-g", "-C", "-o", "--unset", "--chdir", "--user", "--group"}
BOUNDARIES = {";", "&&", "||", "|", "&", "(", ")"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
NAIVE_SPLIT = re.compile(r"\|\||&&|[;|&()]|\$\(")
HEREDOC = re.compile(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def _tokens(line: str) -> list[str] | None:
    """Shell tokens, or None when the line cannot be lexed.

    A hand-rolled split cannot tell `echo "a; python3 b.py"` from two commands, and
    cannot see that `sudo -E python3` still runs python. shlex can do both. It raises on
    an unterminated quote, which is ordinary here — `$RUN -c "` opens a multi-line
    script — and the caller falls back to a split that may over-report. Over-reporting
    is the safe direction for a guard; a miss is what ships the defect.
    """
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _command_word(tokens: list[str]) -> str | None:
    """The word that would actually be executed, or None if nothing is.

    Steps over a copied shell prompt, environment assignments, and wrappers together
    with their own options — `sudo -E python3 x.py` runs python, and reading `-E` as the
    command is how that call went unnoticed.
    """
    i = 0
    if i < len(tokens) and tokens[i] in {"$", ">"}:
        i += 1
    while i < len(tokens) and (ASSIGNMENT.match(tokens[i]) or tokens[i] in WRAPPERS):
        was_wrapper = tokens[i] in WRAPPERS
        i += 1
        while was_wrapper and i < len(tokens) and (
            tokens[i].startswith("-") or ASSIGNMENT.match(tokens[i])
        ):
            takes_value = tokens[i] in VALUE_OPTIONS
            i += 1
            if takes_value and i < len(tokens):
                i += 1
    if i >= len(tokens):
        return None
    word = tokens[i]
    return None if word.startswith("#") else word


def _interpreter_calls(line: str) -> list[str]:
    """Every command in the line whose executable is an interpreter, named directly."""
    if line.lstrip().startswith("#"):
        return []
    tokens = _tokens(line)
    if tokens is None:
        segments = [seg.split() for seg in NAIVE_SPLIT.split(line)]
    else:
        segments, current = [], []
        for token in tokens:
            if token in BOUNDARIES:
                segments.append(current)
                current = []
            else:
                current.append(token)
        segments.append(current)
    return [
        " ".join(seg) for seg in segments if _command_word(seg) in INTERPRETERS
    ]


def _command_lines(text: str):
    """Yield (lineno, line) for lines a shell would execute.

    Prose is not a command, a ```python block is a sample, and a heredoc body is data —
    each produced a false positive before being excluded here.
    """
    fence = None
    heredoc_end = None
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            ticks = len(stripped) - len(stripped.lstrip("`"))
            lang = stripped[ticks:].strip().lower()
            if fence is None:
                fence = (ticks, lang)
            elif ticks >= fence[0] and not lang:
                fence = None
            continue
        if fence is None or fence[1] not in COMMAND_FENCES:
            continue
        if heredoc_end is not None:
            if stripped == heredoc_end:
                heredoc_end = None
            continue
        yield lineno, line
        opener = HEREDOC.search(line)
        if opener:
            heredoc_end = opener.group(1)


MUST_FLAG = [
    "python3 script.py",
    "python -c \"import sys\"",
    "py -3 .\\scripts\\setup.py",
    "cat x | python3 -",
    "$RUN good.py; python3 bad.py",
    "uv run --no-project python good.py && python3 bad.py",
    "H2T_VOICE_PYTHON=/x python3 bad.py",
    "PYTHONPATH=. python3 script.py",
    "env python3 script.py",
    "sudo python3 script.py",
    "time python3 script.py",
    "$ python3 script.py",
    # Wrappers carry their own options; reading `-E` as the command missed these.
    "sudo -E python3 x.py",
    "env -u FOO python3 x.py",
    "time -p python3 x.py",
    # Grouping is a command boundary, not a command.
    "( python3 x.py )",
    "echo hi && ( python3 x.py )",
    # A real substitution runs its contents.
    "OUT=$(python3 x.py)",
]

MUST_NOT_FLAG = [
    "uv run --no-project --python 3.11 python script.py",
    'uv run --project "${PROJECT_ROOT}" python "${PROJECT_ROOT}/x.py"',
    "$RUN scripts/setup_h2t.py doctor --json",
    "$H2T_VOICE_PYTHON -m spacy download ru_core_news_lg",
    "- `python-docx` (pip install python-docx)",
    "pip install python-dotenv",
    "# python3 old.py",
    "echo 'python3 is a word here'",
    'RUN="uv run --no-project --python 3.11 python"',
    # A separator inside quotes is data, not a boundary.
    'echo "a; python3 b.py"',
    "echo '$(python3 b.py)'",
]


@pytest.mark.parametrize("line", MUST_FLAG)
def test_matcher_flags_a_bare_interpreter(line):
    assert _interpreter_calls(line), f"missed a bare interpreter: {line!r}"


@pytest.mark.parametrize("line", MUST_NOT_FLAG)
def test_matcher_leaves_everything_else_alone(line):
    assert not _interpreter_calls(line), f"false positive: {line!r}"


def test_no_skill_invokes_a_bare_interpreter():
    """`python` is absent from PATH on macOS and `python3` on Windows.

    uv supplies the interpreter instead. This is the half the first version of this file
    missed: it forbade *paths* to an interpreter and said nothing about calling one by
    name, so reverting node-researcher to `python3` left the suite green. The red run of
    step 1 exposed it; a test trusted on its green alone would have shipped the hole.
    """
    offenders = []
    for path in SKILLS:
        for lineno, line in _command_lines(path.read_text(encoding="utf-8")):
            for call in _interpreter_calls(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}  {call}")
    assert not offenders, (
        "skills calling an interpreter by name:\n"
        + "\n".join(offenders)
        + "\n\nUse: uv run --no-project --python 3.11 python <script>"
    )
