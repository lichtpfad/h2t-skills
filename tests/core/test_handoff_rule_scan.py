"""The handoff rule-promotion scan finds the session transcript (#475).

The scan rebuilt the transcript directory name from the cwd, stripped the leading '-' and
kept '_', so on macOS it looked in a directory that never exists and reported nothing —
indistinguishable from "no rules this session".

The scan was an inline `python -c` program in handoff/SKILL.md; since Task 12 it is
`h2t-handoff rule-scan`. These tests run the command through the entry point, in a child
process whose console encoding is cp1252, against a fake ~/.claude/projects.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "skills" / "handoff" / "SKILL.md"
ENTRY = "import sys; from h2t_ops.handoff_entry import main; sys.exit(main(sys.argv[1:]))"


def _run(cwd: Path, home: Path, *args: str) -> subprocess.CompletedProcess:
    # cp1252 is what a Windows pipe defaults to; the hits are Cyrillic (#428).
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
           "PYTHONIOENCODING": "cp1252"}
    return subprocess.run(
        [sys.executable, "-c", ENTRY, "rule-scan", *args],
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
    )


def _transcript_dir(home: Path, cwd: Path) -> Path:
    # Claude Code's naming: every non-alphanumeric character becomes '-'.
    return home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def _session(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    cwd = (tmp_path / "some_user" / "repo").resolve()
    cwd.mkdir(parents=True)
    proj = _transcript_dir(home, cwd)
    proj.mkdir(parents=True)
    rows = [
        {"type": "user", "message": {"content": "никогда не коммить в main"}},
        {"type": "user", "message": {"content": [{"type": "text", "text": "запомни: ветка сначала"}]}},
        {"type": "user", "message": {"content": "просто вопрос"}},
        {"type": "assistant", "message": {"content": "никогда"}},
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                                  encoding="utf-8")
    return home, cwd


def test_scan_finds_the_transcript_of_a_path_with_an_underscore(tmp_path):
    home, cwd = _session(tmp_path)

    result = _run(cwd, home)

    assert result.returncode == 0, result.stderr
    assert "никогда не коммить в main" in result.stdout
    assert "запомни: ветка сначала" in result.stdout
    assert "RULE_SCAN: scanned 3 user messages in s.jsonl, 2 hits" in result.stdout


def test_scan_json_carries_the_counts_and_the_hits(tmp_path):
    home, cwd = _session(tmp_path)

    out = json.loads(_run(cwd, home, "--json").stdout)

    assert out == {"ok": True, "transcript": "s.jsonl", "scanned": 3,
                   "hits": ["никогда не коммить в main", "запомни: ветка сначала"]}


def test_scan_reports_a_missing_transcript_instead_of_silence(tmp_path):
    home = tmp_path / "home"
    cwd = tmp_path / "repo"
    cwd.mkdir(parents=True)

    result = _run(cwd, home)
    assert result.returncode == 5
    assert "RULE_SCAN: no transcript found in" in result.stderr

    out = json.loads(_run(cwd, home, "--json").stdout)
    assert out["ok"] is False and "no transcript found in" in out["error"]["message"]
    assert out["error"]["hint"]


def test_the_skill_runs_the_command_not_a_program():
    text = SKILL.read_text(encoding="utf-8")
    assert "h2t-handoff rule-scan --json" in text
    # `--managed-python -c` in the stamped bootstrap is a uv flag, not a program
    assert not re.search(r"(?<![\w-])python -c", text)
