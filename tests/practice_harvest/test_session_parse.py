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
