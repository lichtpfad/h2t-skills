"""The handoff rule-promotion scan finds the session transcript (#475).

The scan rebuilt the transcript directory name from the cwd, stripped the leading '-' and
kept '_', so on macOS it looked in a directory that never exists and reported nothing —
indistinguishable from "no rules this session". These tests run the snippet exactly as
SKILL.md ships it, against a fake ~/.claude/projects.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "skills" / "handoff" / "SKILL.md"


def _snippet() -> str:
    text = SKILL.read_text(encoding="utf-8")
    match = re.search(r'python -c "\n(.*?)\n" \|\| true', text, re.S)
    assert match, "rule-scan snippet not found in handoff SKILL.md"
    code = match.group(1)
    # The snippet sits in bash double quotes; these would change its meaning there.
    assert not any(ch in code for ch in ('"', "$", "`")), "snippet is not bash-quote safe"
    assert "\\\\" not in code, "bash would collapse a double backslash"
    return code


def _run(cwd: Path, home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    return subprocess.run(
        [sys.executable, "-c", _snippet()],
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
    )


def _transcript_dir(home: Path, cwd: Path) -> Path:
    # Claude Code's naming: every non-alphanumeric character becomes '-'.
    return home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def test_scan_finds_the_transcript_of_a_path_with_an_underscore(tmp_path):
    home = tmp_path / "home"
    cwd = tmp_path / "some_user" / "repo"
    cwd.mkdir(parents=True)
    proj = _transcript_dir(home, cwd)
    proj.mkdir(parents=True)
    rows = [
        {"type": "user", "message": {"content": "никогда не коммить в main"}},
        {"type": "user", "message": {"content": [{"type": "text", "text": "запомни: ветка сначала"}]}},
        {"type": "user", "message": {"content": "просто вопрос"}},
        {"type": "assistant", "message": {"content": "никогда"}},
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

    result = _run(cwd, home)

    assert "никогда не коммить в main" in result.stdout
    assert "запомни: ветка сначала" in result.stdout
    assert "RULE_SCAN: scanned 3 user messages in s.jsonl, 2 hits" in result.stdout


def test_scan_reports_a_missing_transcript_instead_of_silence(tmp_path):
    home = tmp_path / "home"
    cwd = tmp_path / "repo"
    cwd.mkdir(parents=True)

    result = _run(cwd, home)

    assert "RULE_SCAN: no transcript found in" in result.stderr
