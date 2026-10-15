"""Nothing a user-facing install path says may lead to cloning the repository (D20).

Measured 2026-10-15: an agent installing the pack cloned the repository, and cloned it again
after it was stopped, to run `uv tool install`. The README gave plugins only as slash
commands an agent cannot type, offered "from a checkout `uv tool install --editable .`" as
the first way to install the CLI, and setup's own hint said `--source /path/to/h2t-skills
for local checkout`. A checkout belongs to developing the pack, under ## Development.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
SETUP = ROOT / "plugins" / "h2t-core" / "skills" / "setup" / "scripts" / "setup_h2t.py"

# Command-shaped: a line that runs a clone, an editable install, or names a checkout as a
# source. The sentence forbidding a clone mentions `git clone` mid-line and must not match.
CLONE = re.compile(
    r"^\s*git clone|uv tool install[^\n]*--editable|from a checkout|local checkout|/path/to/h2t-skills",
    re.M,
)


def _install_section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("## Install For A User")
    return text[start:text.index("\n## ", start + 1)]


def test_the_readme_install_section_never_leads_to_a_clone():
    section = _install_section()
    assert "claude plugin install" in section, "parsed the wrong section — the regex, not the README"
    assert not CLONE.findall(section)


def test_the_readme_gives_an_agent_a_plugin_command_it_can_run():
    section = _install_section()
    assert "claude plugin marketplace add lichtpfad/h2t-skills" in section
    assert "claude plugin install h2t-ops@lichtpfad" in section


def test_setup_hints_never_point_at_a_checkout():
    hints = re.findall(r'"hint"\]\s*=\s*"([^"]*)"', SETUP.read_text(encoding="utf-8"))
    assert hints, "found no hints — the regex, not the script"
    assert not [h for h in hints if CLONE.search(h)]
