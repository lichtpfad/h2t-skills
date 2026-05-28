# tests/docs/test_reporter.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.reporter import build_report, finding, status_from_findings, SCHEMA


def test_build_report_schema():
    r = build_report(
        command="docs-lint",
        repo_root="/tmp/repo",
        status="ok",
        summary="no issues",
        findings=[],
        safe_next_action="nothing",
    )
    assert r["schema"] == SCHEMA
    assert r["schema_version"] == "0.1"
    assert r["command"] == "docs-lint"


def test_build_report_evidence_has_checked_at():
    r = build_report(
        command="docs-lint",
        repo_root="/tmp/repo",
        status="ok",
        summary="",
        findings=[],
        safe_next_action="",
    )
    assert "checked_at" in r["evidence"]
    assert r["evidence"]["checked_at"].endswith("Z")


def test_finding_no_safe_fix():
    f = finding("orphan", "warn", "docs/old.md", "not reachable")
    assert "safe_fix" not in f
    assert f["type"] == "orphan"
    assert f["severity"] == "warn"
    assert f["path"] == "docs/old.md"


def test_finding_with_safe_fix():
    f = finding("frontmatter", "info", "docs/foo.md", "missing title",
                safe_fix="add frontmatter")
    assert f["safe_fix"] == "add frontmatter"


def test_status_from_findings_empty():
    assert status_from_findings([]) == "ok"


def test_status_from_findings_warn():
    assert status_from_findings([finding("orphan", "warn", "x.md", "msg")]) == "warn"


def test_status_from_findings_critical():
    assert status_from_findings(
        [finding("error", "critical", "x.md", "msg")]
    ) == "fail"


def test_status_from_findings_error():
    assert status_from_findings(
        [finding("broken", "error", "x.md", "msg")]
    ) == "fail"
