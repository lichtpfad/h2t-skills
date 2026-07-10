from pathlib import Path
from lib.practice_harvest.collect import classify_kind, track_for_kind, SourceRecord

def test_classify_kind():
    assert classify_kind(Path("x/.claude/rules/git.md")) == "rules"
    assert classify_kind(Path("x/CLAUDE.md")) == "claude_md"
    assert classify_kind(Path("x/docs/superpowers/specs/y.md")) == "spec"
    assert classify_kind(Path("x/docs/superpowers/plans/y.md")) == "plan"
    assert classify_kind(Path("mem/memory/feedback_x.md")) == "memory"
    assert classify_kind(Path("sessions/AUTOMATA/h2t-skills/s.md")) == "session"

def test_documentation_md_excluded():
    # синхронный шаблон — не находка
    assert classify_kind(Path("x/.claude/rules/documentation.md")) is None

def test_track_mapping():
    assert track_for_kind("rules") == "process"
    assert track_for_kind("spec") == "technical"
    assert track_for_kind("memory") == "both"

def test_record_carries_lineage(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_text("# hi", encoding="utf-8")
    rec = SourceRecord.from_path(f, lineage="quant-kb", kind="claude_md")
    assert rec.lineage == "quant-kb"
    assert rec.track == "process"
    assert rec.text == "# hi"
    assert rec.path.endswith("CLAUDE.md")
