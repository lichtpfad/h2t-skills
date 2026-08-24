"""Tests for docs-lint v2 extensions: severity, vendor filter, cap, exceptions."""
import datetime
from pathlib import Path


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
    from collections import Counter

    from lint import _DIM_LIMIT, _collect_all_findings
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


def test_audit_applies_vendor_filter(tmp_path, capsys):
    """_run_audit must not output vendor paths."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _run_audit
    repo = _make_repo(tmp_path)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "README.md").write_text("vendor\n")
    try:
        _run_audit(repo)
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert ".venv" not in captured.out, ".venv path leaked into audit output"


# --- Truncation honesty (the cap must not be silent) -------------------------
#
# _DIM_LIMIT capped every dimension at 50 and said nothing. This repo had 136
# orphans and every surface reported 50 — audit, doctor, doctor --json, and the
# baseline copied into .claude/rules/linting.md. It also made the report
# insensitive to real change: excluding three frozen trees took orphans 136 → 93
# and moved the printed number not at all.

def _lint():
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    import lint
    return lint


def _plans_without_dates(repo: Path, n: int) -> None:
    for i in range(n):
        (repo / "docs" / "superpowers" / "plans" / f"plan-no-date-{i}.md").write_text(
            "---\ntitle: x\n---\n"
        )


def test_cap_returns_the_uncapped_totals():
    lint = _lint()
    findings = [{"type": "naming"} for _ in range(60)] + [{"type": "orphan"}]
    kept, totals = lint._cap_by_dimension(findings, limit=50)
    assert len(kept) == 51
    assert totals == {"naming": 60, "orphan": 1}


def test_a_capped_dimension_reports_what_it_dropped(tmp_path):
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    notes = [f for f in lint._collect_all_findings(repo) if f["type"] == "truncated"]
    naming = [n for n in notes if n["dimension"] == "naming"]
    assert len(naming) == 1
    assert naming[0]["total"] == 60
    assert naming[0]["shown"] == 50
    assert "10 not shown" in naming[0]["message"]


def test_no_truncation_notice_when_nothing_is_capped(tmp_path):
    """A notice on an uncapped run would be noise, and would train people past it."""
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 3)
    assert [f for f in lint._collect_all_findings(repo) if f["type"] == "truncated"] == []


def test_doctor_summary_reports_the_total_not_the_capped_list(tmp_path, capsys):
    import pytest
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    with pytest.raises(SystemExit):
        lint._run_doctor(repo, no_pymarkdown=True)
    out = capsys.readouterr().out
    assert "60 naming issue(s)" in out
    assert "50 naming issue(s)" not in out


def test_doctor_json_carries_the_truncation_notice(tmp_path, capsys):
    """The JSON envelope is the machine contract — a partial list must say so."""
    import json as _json
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    lint._run_doctor(repo, json_output=True, no_pymarkdown=True)
    report = _json.loads(capsys.readouterr().out)
    assert "60 naming issue(s)" in report["summary"]
    notes = [f for f in report["findings"] if f["type"] == "truncated"]
    assert [n["total"] for n in notes if n["dimension"] == "naming"] == [60]


def test_audit_says_how_many_it_did_not_list(tmp_path, capsys):
    import pytest
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    with pytest.raises(SystemExit):
        lint._run_audit(repo, no_pymarkdown=True)
    out = capsys.readouterr().out
    assert "--- Naming (60) ---" in out
    assert "10 more not listed" in out


def test_audit_result_counts_everything_found(tmp_path, capsys):
    import pytest
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    with pytest.raises(SystemExit):
        lint._run_audit(repo, no_pymarkdown=True)
    out = capsys.readouterr().out
    result = [ln for ln in out.splitlines() if "RESULT:" in ln][0]
    assert "60 naming" not in result  # sanity: it is a total, not a per-dimension echo
    n = int(result.split("RESULT:")[1].strip().split()[0])
    assert n >= 60, f"result total {n} must include every naming finding"


# --- exclude_dirs must reach every walk over docs/ ---------------------------
#
# It reached find_orphan_files and check_naming_all_docs only. The five other
# walks kept reporting inside a tree the config had declared frozen (#271).

def _with_exclusions(repo: Path, dirs: list[str]) -> None:
    (repo / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\nexclude_dirs:\n"
        + "".join(f"  - {d}\n" for d in dirs)
    )


def test_exclude_dirs_reaches_the_frontmatter_check(tmp_path):
    """Fixtures exist without frontmatter on purpose — some tests assert that."""
    lint = _lint()
    repo = _make_repo(tmp_path)
    fixtures = repo / "docs" / "superpowers" / "plans" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "2026-01-01-no-frontmatter.md").write_text("# bare\n")
    before = lint.check_frontmatter(repo)
    after = lint.check_frontmatter(repo, exclude_dirs=["docs/superpowers/plans/fixtures"])
    assert any("no-frontmatter" in m for m in before)
    assert not any("no-frontmatter" in m for m in after)


def test_exclude_dirs_reaches_the_data_in_docs_check(tmp_path):
    lint = _lint()
    repo = _make_repo(tmp_path)
    frozen = repo / "docs" / "archive"
    frozen.mkdir(parents=True)
    (frozen / "recipe.yaml").write_text("a: 1\n")
    assert any("recipe.yaml" in m for m in lint.check_data_docs_boundary(repo))
    assert not any(
        "recipe.yaml" in m
        for m in lint.check_data_docs_boundary(repo, exclude_dirs=["docs/archive"])
    )


def test_exclude_dirs_reaches_the_misplaced_deliverable_check(tmp_path):
    """Golden references are pinned to their path; moving them breaks the baseline."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/lib")))
    from docs.misplaced_files import check_misplaced_deliverables
    repo = _make_repo(tmp_path)
    golden = repo / "docs" / "visual-regression" / "r1"
    golden.mkdir(parents=True)
    (golden / "index.html").write_text("<html></html>")
    assert len(check_misplaced_deliverables(repo)) == 1
    assert check_misplaced_deliverables(
        repo, exclude_dirs=["docs/visual-regression"]
    ) == []


def test_the_fix_path_honours_the_same_exclusions(tmp_path):
    """A fixer that moves what the reporter stopped reporting is worse than either.

    _apply_misplaced_moves runs git mv. Without the exclusion the audit would go
    quiet about the golden references while fix-safe still relocated them.
    """
    lint = _lint()
    repo = _make_repo(tmp_path)
    golden = repo / "docs" / "visual-regression" / "r1"
    golden.mkdir(parents=True)
    (golden / "index.html").write_text("<html></html>")
    cfg = {"deliverables_dir": "deliverables", "exclude_dirs": ["docs/visual-regression"]}
    assert lint._apply_misplaced_moves(repo, cfg) == []
    assert lint._apply_misplaced_moves(repo, {"deliverables_dir": "deliverables"}) != []


def test_excluding_a_tree_moves_the_reported_total(tmp_path):
    """The end-to-end property the silent cap was hiding: exclusion changes the number."""
    lint = _lint()
    repo = _make_repo(tmp_path)
    frozen = repo / "docs" / "archive"
    frozen.mkdir(parents=True)
    for i in range(5):
        (frozen / f"old-{i}.md").write_text("# old\n")
    before = len(lint._collect_all_findings(repo, no_pymarkdown=True))
    _with_exclusions(repo, ["docs/archive"])
    after = len(lint._collect_all_findings(repo, no_pymarkdown=True))
    assert after < before, f"{before} -> {after}: exclusion had no effect"


# --- codex review findings on the truncation work itself ---------------------
#
# The first pass fixed audit and doctor and left `plan` — the surface people act
# from — silently partial, and fixed the deliverable *fixer* while leaving the
# frontmatter fixer walking the excluded trees. Same class both times: the
# reporter learned the rule and the thing that acts on it did not.

def test_plan_says_its_worklist_is_partial(tmp_path, capsys):
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    lint._run_plan(repo)
    out = capsys.readouterr().out
    assert "10 more not listed" in out
    assert "this list is partial" in out


def test_plan_json_carries_the_truncation(tmp_path, capsys):
    """The JSON plan is what an applier consumes; a short action list must say so."""
    import json as _json
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 60)
    lint._run_plan(repo, json_output=True)
    plan = _json.loads(capsys.readouterr().out)
    naming = [t for t in plan["truncated"] if t["dimension"] == "naming"]
    assert naming == [{"dimension": "naming", "total": 60, "shown": 50}]


def test_plan_json_omits_the_key_when_nothing_was_cut(tmp_path, capsys):
    import json as _json
    lint = _lint()
    repo = _make_repo(tmp_path)
    _plans_without_dates(repo, 2)
    lint._run_plan(repo, json_output=True)
    assert "truncated" not in _json.loads(capsys.readouterr().out)


def test_the_frontmatter_fixer_honours_the_same_exclusions(tmp_path):
    """A fixture kept bare on purpose must not be handed frontmatter by fix-safe."""
    lint = _lint()
    repo = _make_repo(tmp_path)
    fixtures = repo / "docs" / "superpowers" / "plans" / "fixture-kb"
    fixtures.mkdir(parents=True)
    bare = fixtures / "2026-01-01-bare.md"
    bare.write_text("# bare\n")
    assert lint.fix_frontmatter_action(
        repo, exclude_dirs=["docs/superpowers/plans/fixture-kb"]
    ) == []
    assert bare.read_text() == "# bare\n", "the excluded fixture must be untouched"
    assert lint.fix_frontmatter_action(repo) != []


def test_fix_safe_frontmatter_skips_the_excluded_tree(tmp_path, capsys):
    """End to end through the command, not just the function it calls."""
    lint = _lint()
    repo = _make_repo(tmp_path)
    fixtures = repo / "docs" / "superpowers" / "plans" / "fixture-kb"
    fixtures.mkdir(parents=True)
    bare = fixtures / "2026-01-01-bare.md"
    bare.write_text("# bare\n")
    _with_exclusions(repo, ["docs/superpowers/plans/fixture-kb"])
    lint._run_fix_safe(repo, only="frontmatter")
    capsys.readouterr()
    assert bare.read_text() == "# bare\n"


def test_the_legacy_flag_path_still_runs(tmp_path, monkeypatch, capsys):
    """--fix-frontmatter now reads exclude_dirs, and it reads it before the
    repo loop's other setup. A use-before-assignment there is a runtime
    NameError that ruff's F821 does not see, because the name *is* bound —
    later in the same scope.

    _legacy_main resolves its targets through repo_path(), i.e. C:/dev/<name>,
    which does not exist on a dev machine — so every target is SKIPped and the
    loop body never executes. Pointing repo_path at tmp is what makes this test
    touch the code it is named for.
    """
    import argparse as _argparse
    lint = _lint()
    repo = _make_repo(tmp_path)
    (repo / "docs" / "superpowers" / "plans" / "2026-01-01-bare.md").write_text("# bare\n")
    _with_exclusions(repo, ["docs/superpowers/plans/fixture-kb"])
    monkeypatch.setattr(lint, "repo_path", lambda name: repo)
    monkeypatch.setattr(lint, "_load_projects_yaml", lambda: {})
    args = _argparse.Namespace(
        repos=["h2t-skills"], all=False, fix=False, fix_frontmatter=True,
        fix_labels=False, no_pymarkdown=True, repo_root=False, root=None,
    )
    try:
        lint._legacy_main(args)
    except SystemExit:
        pass  # the legacy path exits 1 whenever the repo has findings
    out = capsys.readouterr().out
    assert "SKIP: repo not found" not in out, "the loop body must actually run"
    assert "FIX: added frontmatter fields" in out, "the fixer must have done work"


# --- codex round 2: grouped totals and the markdown linter ------------------

def test_a_grouped_header_counts_its_uncapped_siblings_too(tmp_path):
    """Project Layer sums five types. Defaulting the four uncapped ones to zero
    made the header report only the capped one — a "total found" line that could
    be smaller than the list under it (codex [P2])."""
    lint = _lint()
    findings = (
        [{"type": "misplaced_deliverable"} for _ in range(50)]
        + [{"type": "root_structure"}, {"type": "root_structure"},
           {"type": "agent_instructions"},
           {"type": "truncated", "dimension": "misplaced_deliverable",
            "total": 60, "shown": 50}]
    )
    total = sum(lint._dimension_total(findings, d) for d in lint._PROJECT_TYPES)
    assert total == 63, f"expected 60 capped + 3 uncapped siblings, got {total}"


def test_dimension_total_falls_back_to_what_is_present(tmp_path):
    lint = _lint()
    findings = [{"type": "naming"}, {"type": "naming"}, {"type": "orphan"}]
    assert lint._dimension_total(findings, "naming") == 2
    assert lint._dimension_total(findings, "orphan") == 1
    assert lint._dimension_total(findings, "structure") == 0


def test_pymarkdown_output_drops_the_frozen_trees(tmp_path, monkeypatch):
    """pymarkdownlnt scans the directory it is handed, so exclude_dirs has to be
    applied to its output. It is often not installed at all, and then this check
    returns [] — which reads exactly like a clean tree."""
    import subprocess as _sp
    lint = _lint()
    repo = _make_repo(tmp_path)
    (repo / "docs" / "archive").mkdir(parents=True)
    monkeypatch.setattr(lint.shutil, "which", lambda _n: "/usr/bin/pymarkdownlnt")

    class _R:
        returncode = 1
        stdout = (
            f"{repo}/docs/archive/old.md:1:1: MD041: First line should be a heading\n"
            f"{repo}/docs/README.md:3:1: MD022: Headings should be surrounded\n"
        )
        stderr = ""

    monkeypatch.setattr(_sp, "run", lambda *a, **k: _R())
    monkeypatch.setattr(lint.subprocess, "run", lambda *a, **k: _R())
    out = lint.run_pymarkdownlnt(repo, exclude_dirs=["docs/archive"])
    assert len(out) == 1
    assert "README.md" in out[0]
    assert "archive" not in out[0]


def test_pymarkdown_says_when_it_stops_listing(tmp_path, monkeypatch):
    """Its own [:20] slice was a second silent cap in the same file."""
    import subprocess as _sp
    lint = _lint()
    repo = _make_repo(tmp_path)

    class _R:
        returncode = 1
        stdout = "".join(
            f"{repo}/docs/f{i}.md:1:1: MD041: whatever\n" for i in range(30)
        )
        stderr = ""

    monkeypatch.setattr(lint.shutil, "which", lambda _n: "/usr/bin/pymarkdownlnt")
    monkeypatch.setattr(_sp, "run", lambda *a, **k: _R())
    monkeypatch.setattr(lint.subprocess, "run", lambda *a, **k: _R())
    out = lint.run_pymarkdownlnt(repo)
    assert len(out) == lint._PYMD_LIMIT + 1
    assert "10 more not listed" in out[-1]
