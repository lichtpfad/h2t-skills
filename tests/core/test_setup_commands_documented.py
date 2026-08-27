"""Every `setup` command a document tells the user to run must exist (#443).

README.md:33 said `/h2t-core:setup install h2t-ops`; the parser has defined
`install-h2t-ops` since it was written (`setup_h2t.py:581`). argparse rejects the
first with `invalid choice: 'install'` and exit 2 — so the first command of the
documented onboarding failed on every machine, and nothing noticed, because the
documentation and the parser were never read against each other.

The check is deliberately blunt: it only asks whether the word after `setup` is a
command the parser knows. That is the whole class of defect it exists for.
"""

import argparse
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "plugins" / "h2t-core" / "skills" / "setup" / "scripts" / "setup_h2t.py"

# Historical documents record what was true when they were written; a command that has
# since been renamed is not a defect there.
SKIP_DIRS = {"archive", "reports"}

# Anchored at the start of the line, because `/h2t-core:setup` also appears mid-sentence
# ("run /h2t-core:setup if missing") and `setup_h2t.py latest/` is a path. A trailing
# slash rules out the second; the anchor rules out the first.
INVOCATION = re.compile(
    r"^\s*[`$]?\s*(?:/h2t-core:setup|[\w./\\-]*python[\w.]*\s+[\w/\\.-]*setup_h2t\.py"
    r"|setup_h2t\.py)\s+([a-z][a-z0-9-]*)(?![\w-]*/)",
)


def _known_commands() -> set[str]:
    spec = importlib.util.spec_from_file_location("_setup_h2t", SETUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("setup_h2t.py exposes no subparsers")


def _documents() -> list[Path]:
    out = []
    for path in ROOT.rglob("*.md"):
        parts = set(path.relative_to(ROOT).parts)
        if ".git" in parts or parts & SKIP_DIRS:
            continue
        out.append(path)
    return out


def test_every_documented_setup_command_exists():
    known = _known_commands()
    offenders = []
    for path in _documents():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for command in INVOCATION.findall(line):
                if command not in known:
                    rel = path.relative_to(ROOT)
                    offenders.append(f"{rel}:{lineno} -> {command!r} ({line.strip()})")
    assert not offenders, "documented commands the parser does not know:\n" + "\n".join(
        offenders
    ) + f"\n\nknown: {sorted(known)}"
