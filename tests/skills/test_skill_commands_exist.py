"""Every command a skill tells the agent to run exists in the CLI it ships with (spec §6.3).

Four assertions over the shipped text:

1. Each `h2t-*` command in a fenced shell block of a SKILL.md or its references names a
   command this package installs, and each subcommand and flag on that line is in the
   command's parser. The parser is asked through `--help` of the console script beside
   `sys.executable`, the installed interpreter — not reconstructed from the source.
2. Every h2t skill starts with the version check: its first shell command is
   `h2t-ops version --expect <slot> --json` (the slot pattern of scripts/release.py), and the outcomes block under it is the
   canonical one in plugins/h2t-core/references/version-check.md, byte for byte.
3. No skill runs plugin Python: no `.py` script, no `h2t-python`, no path into a plugin's
   `scripts/`. Plugins carry text only (spec §5).
4. The briefing rule — use the hook's briefing only when it is fresh and for this
   directory, otherwise gather — is in the three session skills.

A command outside the package is named in EXTERNAL with the reason; a skill that runs no
h2t command at all is named in NO_H2T_COMMAND with the reason.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"
SKILLS = sorted(PLUGINS.glob("h2t-*/skills/*/SKILL.md"))
VERSION_CHECK_DOC = PLUGINS / "h2t-core" / "references" / "version-check.md"


def _release_slots():
    """scripts/release.py: the one definition of the slots a release rewrites."""
    spec = importlib.util.spec_from_file_location("release_slots", ROOT / "scripts" / "release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The placeholder in a checkout, X.Y.Z after `release.py prepare`.
VERSION_CHECK = _release_slots().VERSION_CHECK
BLOCK_BEGIN, BLOCK_END = "<!-- version-check:begin -->", "<!-- version-check:end -->"

# Commands a skill may run that this package does not install.
EXTERNAL = {
    "h2t-snap": "a separate binary from lichtpfad/h2t-snap, declared in snap's compatibility",
}
# Plugin bins: shell scripts that print a plugin directory, for reading the plugin's
# reference text. Checked against the `case` labels of the script itself.
PLUGIN_BINS = {"h2t-dev": PLUGINS / "h2t-dev" / "bin" / "h2t-dev",
               "h2t-arch": PLUGINS / "h2t-arch" / "bin" / "h2t-arch"}

# Skills that run no h2t command, so the version check has nothing to protect.
NO_H2T_COMMAND = {
    "h2t-arch/diagram-node": "research prose for a subagent; no shell command at all",
    "h2t-core/snap": "runs only the external h2t-snap binary",
    "h2t-creative/design": "deprecated pointer to style-create; its blocks are HTML/CSS",
    "h2t-dev/github-issues": "gh only",
    "h2t-dev/pre-merge-check": "placeholders for the project's own audit/test/build commands",
}

SHELL_FENCES = {"bash", "sh", "shell", "console"}
FENCE = re.compile(r"^\s*```([A-Za-z]*)\s*$")
COMMAND = re.compile(r"h2t-[a-z][a-z0-9-]*")
# Where a word is in command position: line start, after an operator, after `$(`.
COMMAND_POSITION = re.compile(
    r"(?:^|[;&|(`]|\$\(|\b(?:then|do|else|exec|time)\s|!\s)\s*(h2t-[a-z][a-z0-9-]*)(?![\w:-])")
COMMAND_V = re.compile(r"\bcommand\s+-v\s+(h2t-[a-z][a-z0-9-]*)")


def _key(skill_md: Path) -> str:
    return f"{skill_md.parents[2].name}/{skill_md.parent.name}"


def _documents(skill_md: Path) -> list[Path]:
    """The SKILL.md, its references/, and the files beside it that it names."""
    text = skill_md.read_text(encoding="utf-8")
    docs = [skill_md]
    docs += sorted((skill_md.parent / "references").rglob("*.md"))
    docs += sorted(p for p in skill_md.parent.glob("*.md")
                   if p.name != "SKILL.md" and p.name in text)
    return docs


def _plugin_references() -> list[Path]:
    return sorted(PLUGINS.glob("h2t-*/references/**/*.md"))


def fenced_blocks(text: str, fences=SHELL_FENCES) -> list[tuple[int, str]]:
    """(first line number, body) of every fenced block whose info string is in `fences`."""
    blocks, lang, start, body = [], None, 0, []
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match and lang is None:
            lang, start, body = match.group(1), number + 1, []
        elif match:
            if lang in fences:
                blocks.append((start, "\n".join(body)))
            lang = None
        elif lang is not None:
            body.append(line)
    return blocks


def logical_lines(body: str) -> list[str]:
    """Lines with `\\` continuations joined and comments dropped; heredoc bodies skipped."""
    out, pending, heredoc = [], "", None
    for raw in body.splitlines():
        if heredoc is not None:
            if raw.strip() == heredoc:
                heredoc = None
            continue
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line, pending = pending + line, ""
        doc = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", line)
        if doc:
            heredoc = doc.group(1)
        if line.strip():
            out.append(line.strip())
    return out


def _cut_at_operator(rest: str) -> str:
    """The command's own words: up to the first unquoted `| ; & ) > <` or backtick."""
    quote, depth, i = None, 0, 0
    while i < len(rest):
        ch = rest[i]
        if quote:
            if ch == quote:
                quote = None
            elif ch == "$" and rest[i:i + 2] == "$(":
                depth += 1
        elif ch in "'\"":
            quote = ch
        elif rest[i:i + 2] == "$(":
            depth += 1
            i += 1
        elif ch == "<" and (placeholder := re.match(r"<[^<>\s]+>", rest[i:])):
            i += len(placeholder.group(0))  # `<id>` is a placeholder, not a redirect
            continue
        elif ch == ")" and depth:
            depth -= 1
        elif ch in "|;&)><`":
            break
        i += 1
    return rest[:i]


def calls(line: str) -> list[tuple[str, list[str]]]:
    """(command, words after it) for every h2t command in command position on the line."""
    found = []
    for match in COMMAND_POSITION.finditer(line):
        words = _cut_at_operator(line[match.end():])
        try:
            tokens = shlex.split(words)
        except ValueError:
            tokens = words.split()
        found.append((match.group(1), [t.strip("[]") for t in tokens if t.strip("[]")]))
    for match in COMMAND_V.finditer(line):
        found.append((match.group(1), []))
    return found


def every_call() -> list[tuple[str, int, str, list[str]]]:
    """(document, line, command, words) across all skills and the plugin references."""
    docs = {d for skill in SKILLS for d in _documents(skill)} | set(_plugin_references())
    out = []
    for doc in sorted(docs):
        for start, body in fenced_blocks(doc.read_text(encoding="utf-8")):
            for line in logical_lines(body):
                for command, words in calls(line):
                    out.append((doc.relative_to(ROOT).as_posix(), start, command, words))
    return out


# --- the installed parsers -----------------------------------------------------------

def _entry_points() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(data["project"]["scripts"])


def console_script(name: str) -> str | None:
    """The console script installed beside the running interpreter, as CI installs it."""
    here = Path(sys.executable).parent
    for folder in (here, here / "Scripts", here.parent / "Scripts", here.parent / "bin"):
        for candidate in (folder / name, folder / f"{name}.exe"):
            if candidate.is_file():
                return str(candidate)
    return shutil.which(name)


@cache
def help_text(command: str, path: tuple[str, ...]) -> tuple[int, str]:
    """(exit code, output) of `<command> <path> --help`."""
    exe = console_script(command)
    if exe is None:
        return 127, ""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"}
    done = subprocess.run([exe, *path, "--help"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=60, cwd=ROOT)
    return done.returncode, done.stdout + done.stderr


def choices(help_out: str) -> set[str]:
    """Subcommand and positional choices: every `{a,b,c}` group in the help."""
    return {word for group in re.findall(r"\{([a-z0-9,_-]+)\}", help_out)
            for word in group.split(",")}


def has_flag(help_out: str, flag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_out) is not None


def _is_word(token: str) -> bool:
    return re.fullmatch(r"[a-z][a-z0-9-]*", token) is not None


def resolve(command: str, words: list[str]) -> tuple[tuple[str, ...], list[str], list[str]]:
    """(subcommand path, flags, problems).

    A leading word is a subcommand when `--help` under it answers with a different help:
    the parser descended. The same help means a positional value (a repo name, a mode the
    parser reads itself). An error means the parser has no such subcommand.
    """
    path: list[str] = []
    problems: list[str] = []
    for word in words:
        if word.startswith("-") or not _is_word(word):
            break
        rc, child = help_text(command, (*path, word))
        _, here = help_text(command, tuple(path))
        if rc != 0 or "invalid choice" in child:
            if word not in choices(here):
                problems.append(f"`{' '.join([command, *path])}` has no subcommand {word}")
            break
        if child == here:
            break
        path.append(word)
    flags = [w.split("=", 1)[0] for w in words
             if re.fullmatch(r"--?[A-Za-z][\w-]*(=.*)?", w)]
    return tuple(path), flags, problems


def problems_of(command: str, words: list[str]) -> list[str]:
    if command in EXTERNAL:
        return []
    if command in PLUGIN_BINS:
        labels = re.findall(r"^\s*([a-z-]+)\)", PLUGIN_BINS[command].read_text(encoding="utf-8"),
                            re.M)
        return [] if not words or words[0] in labels else [f"no `{words[0]}` in {command}"]
    if command not in _entry_points():
        return [f"`{command}` is not a console script of this package"]
    if console_script(command) is None:
        return [f"`{command}` is declared but not installed beside {sys.executable}"]
    path, flags, found = resolve(command, words)
    _, help_out = help_text(command, path)
    found += [f"`{' '.join([command, *path])}` has no flag {flag}"
              for flag in flags if not has_flag(help_out, flag)]
    return found


CALLS = every_call()


def test_the_extraction_finds_the_commands():
    """Positive control: a broken extractor would make every assertion below vacuous."""
    commands = {command for _, _, command, _ in CALLS}
    assert {"h2t-ops", "h2t-gather", "h2t-handoff", "h2t-creative", "h2t-runbook"} <= commands
    assert len(CALLS) > 100


def test_every_skill_command_and_flag_exists_in_its_parser():
    unique = sorted({(command, tuple(words)) for _, _, command, words in CALLS})
    # Warm the help cache in parallel: one --help per distinct subcommand path.
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda cw: problems_of(cw[0], list(cw[1])), unique))
    offenders = []
    for doc, line, command, words in CALLS:
        for problem in problems_of(command, words):
            offenders.append(f"{doc}:{line}: {problem}  ({command} {' '.join(words)})")
    assert not offenders, "\n".join(sorted(set(offenders)))


# Spec §6.3: a skill calls the CLI "always with --json". A call whose deepest --help lists
# --json and that does not pass it needs an entry here: the command form and the reason.
NO_JSON = {
    # Commands with no JSON mode at all (fix round 1, ruling 3b).
    **{form: "produces an artifact or human text; no machine-readable result consumed by "
             "the skill"
       for form in ("h2t-drawio generate", "h2t-drawio export", "h2t-creative root",
                    "h2t-creative profiles-dir", "h2t-creative assemble",
                    "h2t-detect-project", "h2t-agent-profile")},
    # docs-lint's mode parser is shared, so --json is listed for every mode, but only
    # doctor, plan and retire read it (h2t_ops/tools/docs/lint.py main): these three print
    # human text whatever is passed, and the flag would promise JSON they do not emit.
    "h2t-docs-lint audit": "this mode ignores --json and prints the human audit",
    "h2t-docs-lint fix-safe": "this mode ignores --json and prints what it fixed",
    "h2t-docs-lint fix-index": "this mode ignores --json and prints the index diff",
    # The bare path is the result: the skill substitutes it into a shell path with $(...).
    "h2t-ops paths get": "the human output is the path itself, used inside $(...)",
}
# A deliberate human/markdown format on a call the skill does consume, with the reason the
# skill gives for it.
FORMAT_CHOSEN = {
    "h2t-ops gmail list": "daily-brief: in --json every message carries its full body, "
                          "~300 KB for 40 messages; --format human is ~13 KB with the ids",
    "h2t-ops notion search": "daily-brief: --format md resolves the Project relation and the "
                             "page link, which the brief prints",
    **{form: "the markdown is the content itself — a note or transcript the user reads or "
             "keeps — not a result the skill parses"
       for form in ("h2t-ops granola get", "h2t-ops granola transcript",
                    "h2t-ops meetgeek transcript")},
}


def has_json_option(help_out: str) -> bool:
    """`--json` as an option of this parser, not a word in some subcommand's description."""
    return re.search(r"^\s+(?:-\w, )?--json\b", help_out, re.M) is not None


def _form(command: str, words: list[str]) -> str:
    path, _, _ = resolve(command, words)
    return " ".join([command, *path])


def test_every_call_that_can_emit_json_asks_for_it():
    offenders = []
    for doc, line, command, words in CALLS:
        if not words or command in EXTERNAL or command in PLUGIN_BINS:
            continue  # `command -v` probes, and commands outside the package
        form = _form(command, words)
        _, help_out = help_text(command, resolve(command, words)[0])
        if form in NO_JSON or not has_json_option(help_out) or "--json" in words:
            continue
        if form in FORMAT_CHOSEN and "--format" in words:
            continue
        offenders.append(f"{doc}:{line}: {command} {' '.join(words)}")
    assert not offenders, "calls without --json (add it, or an entry in NO_JSON):\n" + \
        "\n".join(sorted(set(offenders)))


def test_the_json_allow_lists_name_real_forms():
    forms = {_form(c, w) for _, _, c, w in CALLS if w}
    stale = (set(NO_JSON) | set(FORMAT_CHOSEN)) - forms
    assert not stale, f"allow-list entries no skill uses: {sorted(stale)}"


@pytest.mark.parametrize(("line", "command", "words"), [
    ('PLUGIN_ROOT="$(h2t-creative root)"', "h2t-creative", ["root"]),
    ("h2t-ops drive get <id> --json | jq .", "h2t-ops", ["drive", "get", "<id>", "--json"]),
    ("command -v h2t-gather >/dev/null 2>&1 || {", "h2t-gather", []),
    ("h2t-scaffold-project create --id x [--merge]", "h2t-scaffold-project",
     ["create", "--id", "x", "--merge"]),
])
def test_calls_reads_a_command_line(line, command, words):
    assert (command, words) in calls(line)


@pytest.mark.parametrize("line", [
    'echo "ERROR: h2t-gather not found. Run /h2t-core:setup"',
    "uvx --from 'h2t-ops @ x' something",
])
def test_calls_ignores_a_name_that_is_not_run(line):
    assert calls(line) == []


def test_a_missing_flag_is_reported():
    """Control for the parser probe: an invented flag must be caught."""
    assert problems_of("h2t-gather", ["--no-such-flag"])
    assert not problems_of("h2t-gather", ["--cwd", ".", "--briefing-only"])
    assert problems_of("h2t-ops", ["drive", "nonexistent-verb"])
    assert problems_of("h2t-nonexistent", [])


# --- the version check ---------------------------------------------------------------

def _first_shell_command(text: str) -> str | None:
    for _, body in fenced_blocks(text):
        lines = logical_lines(body)
        if lines:
            return lines[0]
    return None


def _outcomes_block(text: str) -> str | None:
    if BLOCK_BEGIN not in text or BLOCK_END not in text:
        return None
    return text.split(BLOCK_BEGIN, 1)[1].split(BLOCK_END, 1)[0]


def test_the_canonical_outcomes_block_exists():
    block = _outcomes_block(VERSION_CHECK_DOC.read_text(encoding="utf-8"))
    assert block, f"{VERSION_CHECK_DOC} has no {BLOCK_BEGIN} block"
    assert VERSION_CHECK.search(block), block
    # The four outcomes of spec §6.3, in that order.
    order = [block.find(marker) for marker in
             ('"ok": true', '"ok": false', "command not found", "Anything else")]
    assert -1 not in order and order == sorted(order), order


def test_the_block_does_not_tell_the_agent_to_act_on_the_hint():
    """Outcome 2 shows the hint; it never follows or runs it (spec §6.3).

    The `path` hint names `uv tool update-shell`, which edits the user's shell profile and
    is the user's to run. An earlier text said "follow it before going on".
    """
    block = _outcomes_block(VERSION_CHECK_DOC.read_text(encoding="utf-8"))
    outcome2 = block.split("\n2. ", 1)[1].split("\n3. ", 1)[0]
    assert not re.search(r"\bfollow", outcome2, re.I), outcome2
    assert not re.search(r"(?<!not )\brun (?:it|the hint|what)", outcome2, re.I), outcome2
    assert "stop" in outcome2 and "unless the user asks" in outcome2, outcome2


@pytest.mark.parametrize("skill", SKILLS, ids=_key)
def test_every_h2t_skill_starts_with_the_version_check(skill):
    text = skill.read_text(encoding="utf-8")
    if _key(skill) in NO_H2T_COMMAND:
        return
    assert VERSION_CHECK.fullmatch(_first_shell_command(text) or ""), (
        f"{_key(skill)}: the first shell command is {_first_shell_command(text)!r}")
    canonical = _outcomes_block(VERSION_CHECK_DOC.read_text(encoding="utf-8"))
    assert _outcomes_block(text) == canonical, (
        f"{_key(skill)}: the outcomes block differs from {VERSION_CHECK_DOC.name}; "
        "copy it from there unchanged")


def test_a_skill_without_h2t_commands_really_has_none():
    """NO_H2T_COMMAND is a list of exceptions; an entry that runs h2t commands is stale."""
    stale, unknown = [], set(NO_H2T_COMMAND) - {_key(s) for s in SKILLS}
    for skill in SKILLS:
        if _key(skill) not in NO_H2T_COMMAND:
            continue
        ran = {c for d in _documents(skill) for _, body in fenced_blocks(d.read_text("utf-8"))
               for line in logical_lines(body) for c, _ in calls(line) if c not in EXTERNAL}
        if ran:
            stale.append(f"{_key(skill)} runs {sorted(ran)}")
    assert not stale and not unknown, (stale, unknown)


# --- no plugin Python ----------------------------------------------------------------

PLUGIN_PYTHON = [
    (re.compile(r"(?<![\w*])[\w./${}()-]*\.py\b(?!['\"]?\s*:)"), "runs a .py script"),
    (re.compile(r"\bh2t-python\b"), "names the retired h2t-python interpreter"),
    # An inline program is plugin Python too, only without a file: the handoff rule scan
    # was 35 lines of `uv run ... python -c` before it became `h2t-handoff rule-scan`.
    (re.compile(r"\bpython[0-9.]*(?:\.exe)?\s+-c\b"), "runs an inline python -c program"),
    (re.compile(r"\$\{?CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}?/"), "builds a path from a harness variable"),
    (re.compile(r"(?:\}|\))/(?:skills/[\w-]+/)?scripts\b|/scripts['\"/]"), "reaches into a plugin scripts/ dir"),
]


def _plugin_python(doc: Path) -> list[str]:
    hits = []
    for start, body in fenced_blocks(doc.read_text(encoding="utf-8"), SHELL_FENCES | {""}):
        for offset, line in enumerate(body.splitlines()):
            code = re.sub(r"(^|\s)#.*$", "", line)
            for pattern, why in PLUGIN_PYTHON:
                if pattern.search(code) and "*.py" not in code:
                    hits.append(f"{doc.relative_to(ROOT).as_posix()}:{start + offset}: {why}: "
                                f"{line.strip()[:100]}")
    return hits


@pytest.mark.parametrize("skill", SKILLS, ids=_key)
def test_no_skill_runs_plugin_python(skill):
    hits = [hit for doc in _documents(skill) for hit in _plugin_python(doc)]
    assert not hits, "\n".join(hits)


@pytest.mark.parametrize(("line", "flagged"), [
    ('$RUN "$LINT" doctor --json', False),
    ('uv run --no-project python scripts/setup_h2t.py doctor --json', True),
    ('LINT="$(h2t-dev root)/skills/docs-lint/scripts/lint.py"', True),
    ("sys.path.insert(0, '${SKILL_DIR}/scripts')", True),
    ("git diff main...HEAD -- '*.js' '*.py'", False),
    ("h2t-python -c 'print(1)'", True),
    ('uv run --no-project --python 3.11 python -c "', True),
    ("python3 -c 'import sys'", True),
    ("h2t-handoff rule-scan --json", False),
])
def test_the_plugin_python_matcher(tmp_path, line, flagged):
    doc = tmp_path / "SKILL.md"
    doc.write_text(f"```bash\n{line}\n```\n", encoding="utf-8")
    original = ROOT
    try:
        globals()["ROOT"] = tmp_path
        assert bool(_plugin_python(doc)) is flagged
    finally:
        globals()["ROOT"] = original


# --- the briefing rule ---------------------------------------------------------------

@pytest.mark.parametrize("skill", ["session-start", "handoff", "init-project"])
def test_session_skills_carry_the_briefing_rule(skill):
    text = (PLUGINS / "h2t-core" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "120 s" in text, f"{skill}: no freshness bound"
    assert "`cwd`" in text and "`at`" in text, f"{skill}: does not name cwd and at"
    gather = "h2t-detect-project" if skill == "init-project" else "h2t-gather"
    assert gather in text, f"{skill}: no fallback to {gather}"
    assert "Codex" in text, f"{skill}: does not say what happens without hooks"
