"""Every backend call in the setup skill runs as written, from any directory (#520, Task 12).

The Secrets Wizard called `... setup_h2t.py` without `scripts/`, which does not resolve
from the skill directory. And every block after Step 1 called `$RUN ...`, a variable set
once in Step 1: an agent's shell calls share no variables, so by the second call `$RUN`
was empty and the script ran as a bare path — exit 126, Permission denied.

Since Task 12 the backend is a command, `h2t-ops setup <verb>`: no path, no interpreter,
no variable — so neither defect has anything left to attach to. These tests hold that.
"""
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "skills" / "setup" / "SKILL.md"
VERBS = r"(?:doctor|setup|repair|update|connectors-check|install-h2t-ops|secrets)"


def _text():
    return SKILL.read_text(encoding="utf-8")


def test_every_backend_call_is_the_command():
    calls = re.findall(rf"h2t-ops setup {VERBS}\b", _text())

    assert len(calls) > 10
    assert "setup_h2t.py" not in _text()


def test_no_backend_call_carries_an_interpreter_or_a_variable():
    assert "uv run" not in _text()
    assert "$RUN" not in _text()


def test_secrets_wizard_names_every_registry_key_or_none():
    """A key list copied into the wizard fell behind the registry: GRANOLA_API_KEY (#525)."""
    registry = SKILL.parent / "known_secrets.yaml"
    keys = {line.rstrip(":") for line in registry.read_text(encoding="utf-8").splitlines() if re.match(r"[A-Z_]+:$", line)}
    wizard = _text().split("## Secrets Wizard", 1)[1]

    assert len(keys) >= 4
    assert {k for k in keys if k in wizard} in (set(), keys)


def test_secrets_wizard_has_no_powershell_only_command():
    """The skill runs its snippets from Git Bash, where `$env:` does not parse (#525)."""
    assert "$env:" not in _text().split("## Secrets Wizard", 1)[1]
