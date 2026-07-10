from lib.practice_harvest.collect import SourceRecord, dedup_records


def _rec(path, lineage, text):
    return SourceRecord(path=path, lineage=lineage, kind="rules",
                        track="process", text=text)


def test_identical_content_same_lineage_collapses():
    recs = [
        _rec("crypto-regime-spike/.claude/rules/git.md", "crypto-regime-spike", "RULE"),
        _rec("crypto-regime-spike-dmde/.claude/rules/git.md", "crypto-regime-spike", "RULE"),
    ]
    out = dedup_records(recs)
    assert len(out) == 1


def test_different_content_kept():
    recs = [
        _rec("a/.claude/rules/git.md", "a", "RULE-A"),
        _rec("b/.claude/rules/git.md", "b", "RULE-B"),
    ]
    assert len(dedup_records(recs)) == 2


def test_same_content_different_lineage_kept():
    # одинаковый текст в РАЗНЫХ lineage = реальный кросс-repo сигнал, не дубль
    recs = [
        _rec("a/.claude/rules/git.md", "a", "RULE"),
        _rec("b/.claude/rules/git.md", "b", "RULE"),
    ]
    assert len(dedup_records(recs)) == 2
