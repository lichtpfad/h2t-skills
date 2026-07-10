from lib.practice_harvest.render_registry import render_md

REG = {
    "window": ["2026-06-10", "2026-07-10"],
    "findings": [
        {"practice": "codex gate", "track": "process", "lineage_sources": ["quant-kb"],
         "recurrence": 1, "domain_independence": "high",
         "current_location": "quant-kb/.claude/rules/codex-review.md",
         "lift_verdict": "new-standard", "source_paths": ["x"]},
        {"practice": "two-gate verdict", "track": "technical", "lineage_sources": ["quant-kb", "crypto-regime-spike"],
         "recurrence": 2, "domain_independence": "medium",
         "current_location": "…", "lift_verdict": "deferred:code", "source_paths": ["y"]},
        {"practice": "batch telemetry", "track": "technical", "lineage_sources": ["crypto-regime-spike"],
         "recurrence": 1, "domain_independence": "low",
         "current_location": "…", "lift_verdict": "skip", "source_paths": ["z"]},
    ],
}

def test_render_groups_by_track_and_has_columns():
    md = render_md(REG)
    assert "## Process track" in md
    assert "## Technical track" in md
    assert "codex gate" in md
    assert "two-gate verdict" in md
    # single-lineage помечен как low source-diversity
    assert "⚠" in md

def test_render_sorts_by_recurrence_desc_within_track():
    md = render_md(REG)
    # technical: два finding — recurrence 2 (two-gate) должен идти ВЫШЕ recurrence 1 (batch)
    assert md.index("two-gate verdict") < md.index("batch telemetry")
