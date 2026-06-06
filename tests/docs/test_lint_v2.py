"""Tests for docs-lint v2 extensions: severity, vendor filter, cap, exceptions."""
from pathlib import Path
import datetime
import pytest


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "documentation.md").write_text("# rules\n")
    return tmp_path


def test_all_findings_have_id_field(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    for f in _collect_all_findings(repo):
        assert "id" in f and f["id"], f"missing id: {f}"


def test_all_findings_have_normalized_severity(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    valid = {"critical", "important", "low"}
    for f in _collect_all_findings(repo):
        assert f["severity"] in valid, f"bad severity '{f['severity']}': {f}"


def test_vendor_paths_excluded(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "README.md").write_text("vendor\n")
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "README.md").write_text("vendor\n")
    paths = [f["path"] for f in _collect_all_findings(repo)]
    assert not any(".venv" in p for p in paths)
    assert not any("node_modules" in p for p in paths)


def test_per_dimension_cap(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings, _DIM_LIMIT
    from collections import Counter
    repo = _make_repo(tmp_path)
    # Create 60 files without date prefix to trigger naming findings
    for i in range(60):
        (repo / "docs" / "superpowers" / "plans" / f"plan-no-date-{i}.md").write_text("---\ntitle: x\n---\n")
    counts = Counter(f["type"] for f in _collect_all_findings(repo))
    for t, n in counts.items():
        assert n <= _DIM_LIMIT, f"dimension '{t}' has {n} > {_DIM_LIMIT}"


def test_exception_dict_paths_filtered(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    (repo / "benchmark_results").mkdir()
    (repo / "benchmark_results" / "run.json").write_text("{}")
    today = datetime.date.today().isoformat()
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    (h2t / "docs-lint.yaml").write_text(
        f"exceptions:\n  - path: benchmark_results/\n    reason: live\n    type: operational_data\n    reviewed: {today}\n"
    )
    paths = [f["path"] for f in _collect_all_findings(repo)]
    assert not any("benchmark_results" in p for p in paths)


def test_exception_string_format_no_crash(tmp_path):
    """Legacy string exceptions must not crash _collect_all_findings."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    (h2t / "docs-lint.yaml").write_text("exceptions:\n  - eval\n  - ops\n")
    findings = _collect_all_findings(repo)
    assert isinstance(findings, list)


def test_exception_warnings_not_capped(tmp_path):
    """Stale exception warnings must survive the dimension cap."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    existing = repo / "stale_dir"
    existing.mkdir()
    (h2t / "docs-lint.yaml").write_text(
        f"exceptions:\n  - path: stale_dir/\n    reason: old\n    type: archive\n    reviewed: {old_date}\n"
    )
    msgs = [f["message"] for f in _collect_all_findings(repo)]
    assert any("stale" in m for m in msgs), "stale exception warning was capped away"
