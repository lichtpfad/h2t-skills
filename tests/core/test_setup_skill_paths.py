"""Every backend call in the setup skill runs as written from the skill directory (#520).

The Secrets Wizard called `... setup_h2t.py` without `scripts/`, which does not resolve
from the skill directory. And every block after Step 1 called `$RUN ...`, a variable set
once in Step 1: an agent's shell calls share no variables, so by the second call `$RUN`
was empty and the script ran as a bare path — exit 126, Permission denied.
"""
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "skills" / "setup" / "SKILL.md"
INTERPRETER = "uv run --no-project --python 3.11 python"


def _text():
    return SKILL.read_text(encoding="utf-8")


def test_every_backend_call_names_its_directory():
    calls = re.findall(r"(\S*setup_h2t\.py) (?:doctor|setup|repair|update|connectors-check|install-h2t-ops|secrets)", _text())

    assert len(calls) > 10
    assert [c for c in calls if c not in {"scripts/setup_h2t.py", "plugins/h2t-core/skills/setup/scripts/setup_h2t.py"}] == []


def test_every_backend_call_carries_its_interpreter():
    lines = [line for line in _text().splitlines() if re.search(r"setup_h2t\.py \w", line)]

    assert len(lines) > 10
    assert [line for line in lines if INTERPRETER not in line] == []
    assert "$RUN" not in _text()
