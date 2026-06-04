"""Unit tests for docs.agent_instructions module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.agent_instructions import check_agent_instructions


def test_no_claude_dir_returns_empty(tmp_path):
    """.claude/ dir absent → no findings, no crash."""
    result = check_agent_instructions(tmp_path)
    assert result == []


def test_required_rules_files_missing_flagged(tmp_path):
    """documentation.md and linting.md missing from .claude/rules/ → findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    result = check_agent_instructions(tmp_path)
    types = [f["message"] for f in result]
    assert any("documentation.md" in m for m in types)
    assert any("linting.md" in m for m in types)


def test_required_rules_files_present_not_flagged(tmp_path):
    """documentation.md and linting.md present → no 'missing required' finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text("# Docs rules")
    (rules / "linting.md").write_text("# Lint rules")
    result = check_agent_instructions(tmp_path)
    missing = [f for f in result if "missing required" in f["message"]]
    assert missing == []


def test_non_kebab_rules_file_flagged(tmp_path):
    """Rules file with uppercase → naming finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "MyRules.md").write_text("# bad name")
    result = check_agent_instructions(tmp_path)
    naming = [f for f in result if "not kebab-case" in f["message"]]
    assert naming, f"Expected kebab-case finding, got: {result}"
    assert naming[0]["severity"] == "warn"


def test_kebab_rules_file_not_flagged(tmp_path):
    """my-rules.md is valid kebab-case → no naming finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text("")
    (rules / "linting.md").write_text("")
    (rules / "my-custom-rules.md").write_text("")
    result = check_agent_instructions(tmp_path)
    naming = [f for f in result if "not kebab-case" in f["message"]]
    assert naming == []


def test_stale_absolute_path_in_rules_flagged(tmp_path):
    """Absolute path in backtick code span that doesn't exist → stale path finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    # Use a subpath of tmp_path that we guarantee does not exist
    nonexistent = str(tmp_path / "does_not_exist_subdir" / "check.py").replace("\\", "/")
    (rules / "documentation.md").write_text(
        f"# Docs\n\nRun `{nonexistent}` to verify.\n"
    )
    (rules / "linting.md").write_text("")
    result = check_agent_instructions(tmp_path)
    stale = [f for f in result if "stale path" in f["message"]]
    assert stale, f"Expected stale path finding, got: {result}"


def test_rules_dir_absent_required_files_still_flagged(tmp_path):
    """.claude/ exists but .claude/rules/ doesn't → required files still flagged."""
    (tmp_path / ".claude").mkdir()
    # No rules/ subdir created
    result = check_agent_instructions(tmp_path)
    msgs = [f["message"] for f in result]
    assert any("documentation.md" in m for m in msgs), f"Expected documentation.md finding: {msgs}"
    assert any("linting.md" in m for m in msgs), f"Expected linting.md finding: {msgs}"


def test_existing_absolute_path_not_flagged(tmp_path):
    """Absolute path in backtick that DOES exist → no stale path finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text(
        f"# Docs\n\nConfig at `{str(tmp_path).replace(chr(92), '/')}`.\n"
    )
    (rules / "linting.md").write_text("")
    result = check_agent_instructions(tmp_path)
    stale = [f for f in result if "stale path" in f["message"]]
    assert stale == []


def test_claude_md_missing_commands_section_flagged(tmp_path):
    """CLAUDE.md without 'Key Commands' or 'Commands' heading → info finding."""
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Overview\n\nSome content.\n")
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "missing" in f["message"] and "Commands" in f["message"]]
    assert section_findings, f"Expected commands section finding, got: {result}"
    assert section_findings[0]["severity"] == "info"


def test_claude_md_with_key_commands_not_flagged(tmp_path):
    """CLAUDE.md with '## Key Commands' heading → no section finding."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Key Commands\n\n```bash\npython run.py\n```\n"
    )
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "Commands" in f.get("message", "")]
    assert section_findings == []


def test_claude_md_with_commands_heading_not_flagged(tmp_path):
    """CLAUDE.md with '## Commands' heading → no section finding."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Commands\n\n```bash\nnpm start\n```\n"
    )
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "Commands" in f.get("message", "")]
    assert section_findings == []


def test_finding_type_is_agent_instructions(tmp_path):
    """All findings have type='agent_instructions'."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    result = check_agent_instructions(tmp_path)
    for f in result:
        assert f["type"] == "agent_instructions", f"Wrong type: {f}"
