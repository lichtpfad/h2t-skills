from lib.practice_harvest.session_parse import parse_session_md

SAMPLE = """# Session: dev-h2t-skills-demo-2026-07-01

## Meta
- **Date:** 2026-07-01
- **Domain:** dev
- **Project:** h2t-skills

## What Was Done
- Сделал A.
- Сделал B.

## What Remains
- [ ] Осталось C.

## Artifacts
- commit: abc1234
"""

def test_parses_meta_and_sections():
    r = parse_session_md(SAMPLE)
    assert r["date"] == "2026-07-01"
    assert r["project"] == "h2t-skills"
    assert r["what_done"] == ["Сделал A.", "Сделал B."]
    assert r["what_remains"] == ["Осталось C."]

def test_missing_section_yields_empty():
    r = parse_session_md("# Session: x\n\n## Meta\n- **Project:** quant-kb\n")
    assert r["project"] == "quant-kb"
    assert r["what_done"] == []
    assert r["date"] == ""

def test_prose_body_retained_when_no_bullets():
    # реальные сессии часто пишут секции ПРОЗОЙ, не буллетами (council Lens 1 blocker)
    md = ("# Session: x\n\n## Meta\n- **Project:** quant-kb\n\n"
          "## What Was Done\nRefactored the ingest pipeline into three passes.\n"
          "Added a faithfulness judge gate.\n\n## Artifacts\n- commit: abc\n")
    r = parse_session_md(md)
    assert r["what_done"]  # НЕ пусто — проза сохранена
    assert any("faithfulness judge" in x for x in r["what_done"])
    assert not any("commit" in x for x in r["what_done"])  # Artifacts не течёт

def test_mixed_prose_and_bullets_prefers_bullets():
    md = ("## What Was Done\n- Did A.\n- Did B.\n\n## What Remains\nStill need to wire the gate.\n")
    r = parse_session_md(md)
    assert r["what_done"] == ["Did A.", "Did B."]
    assert any("wire the gate" in x for x in r["what_remains"])
