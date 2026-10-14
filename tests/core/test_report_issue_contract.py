"""The bug report has three writers and one reader, and they must agree on its headings.

The bug form (`bug.yml`) and the `report-issue` skill both produce a body; the
`issue-fields` workflow recognises a bug report by its headings and labels it for triage.
If any side renames a heading, a client's report falls through to the maintainer's task
contract and is stamped `status:needs-fields` — rejected, from the reporter's view.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml"
SKILL = ROOT / "plugins" / "h2t-core" / "skills" / "report-issue" / "SKILL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "issue-fields.yml"


def _workflow_sections() -> list[str]:
    block = re.search(r"BUG_SECTIONS = \[(.*?)\]", WORKFLOW.read_text(encoding="utf-8"), re.S)
    assert block, "issue-fields.yml no longer declares BUG_SECTIONS"
    return [s.removeprefix("### ") for s in re.findall(r"'([^']+)'", block.group(1))]


def _form_labels() -> list[str]:
    return re.findall(r"^\s+label:\s*(.+?)\s*$", FORM.read_text(encoding="utf-8"), re.M)


def _skill_headings() -> list[str]:
    return re.findall(r"^### (.+?)\s*$", SKILL.read_text(encoding="utf-8"), re.M)


def test_the_workflow_recognises_what_the_form_writes():
    required = _workflow_sections()
    assert len(required) >= 3, "parsed as near-empty — the regex, not the workflow"
    assert set(required) <= set(_form_labels())


def test_the_workflow_recognises_what_the_skill_writes():
    assert set(_workflow_sections()) <= set(_skill_headings())


def test_every_filing_command_in_the_skill_names_the_upstream_repo():
    commands = re.findall(r"gh issue (?:create|list)[^\n]*(?:\\\n[^\n]*)*", SKILL.read_text(encoding="utf-8"))
    assert commands, "no gh issue command found — the regex, not the skill"
    for cmd in commands:
        assert "--repo lichtpfad/h2t-skills" in cmd, cmd
        assert "--label" not in cmd, cmd
