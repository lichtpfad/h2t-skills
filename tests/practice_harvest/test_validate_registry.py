import pytest

from lib.practice_harvest.validate_registry import (
    ValidationError,
    validate_coverage,
    validate_finding,
)


def _ok(tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("x", encoding="utf-8")
    return {
        "practice": "codex second-opinion gate",
        "track": "process",
        "lineage_sources": ["quant-kb"],
        "recurrence": 1,
        "domain_independence": "high",
        "current_location": "quant-kb/.claude/rules/codex-review.md",
        "lift_verdict": "new-standard",
        "source_paths": [str(f)],
    }

def test_valid_finding_passes(tmp_path):
    validate_finding(_ok(tmp_path))  # no raise

def test_bad_track_rejected(tmp_path):
    f = _ok(tmp_path); f["track"] = "hybrid"
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_bad_verdict_rejected(tmp_path):
    f = _ok(tmp_path); f["lift_verdict"] = "maybe"
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_missing_source_path_on_disk_rejected(tmp_path):
    f = _ok(tmp_path); f["source_paths"] = [str(tmp_path / "nope.md")]
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_recurrence_must_match_unique_lineage(tmp_path):
    # recurrence врёт: 3, но уникальный lineage один
    f = _ok(tmp_path); f["recurrence"] = 3; f["lineage_sources"] = ["quant-kb"]
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_append_verdict_with_target_ok(tmp_path):
    f = _ok(tmp_path); f["lift_verdict"] = "append:git-naming-conventions.md"
    validate_finding(f)  # no raise

def test_coverage_all_lineages_accounted_passes():
    corpus = {"lineage_counts": {"quant-kb": 3, "rejuve": 5}}
    registry = {
        "findings": [{"lineage_sources": ["quant-kb"]}],
        "examined_no_lift": ["rejuve"],
    }
    validate_coverage(registry, corpus)  # no raise

def test_coverage_missing_lineage_rejected():
    corpus = {"lineage_counts": {"quant-kb": 3, "rejuve": 5}}
    registry = {"findings": [{"lineage_sources": ["quant-kb"]}], "examined_no_lift": []}
    with pytest.raises(ValidationError):
        validate_coverage(registry, corpus)
