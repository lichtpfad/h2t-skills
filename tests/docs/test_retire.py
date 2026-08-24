"""Retirement is the only remedy that lowers the docs-debt number.

The two automatic signals both failed a control on this repo: a plan slug
appears in 7 of 60 merged PR bodies, and 47 of 140 documents were created in
one commit and never touched again — which does not separate "done and never
updated" from "abandoned". So the closing judgement stays with a human, and
this module's job is to make that judgement cheap: candidates with their
evidence, and one flag to move them.
"""
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.retire import archive_target, find_retire_candidates, retire_files


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    return tmp_path


def _doc(root: Path, rel: str, status: str = "draft") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\ntitle: "x"\nstatus: {status}\n---\nbody\n', encoding="utf-8")
    return p


# ── candidate selection ─────────────────────────────────────────────────────


def test_old_open_plan_is_a_candidate(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/2026-01-05-old.md")
    cands = find_retire_candidates(tmp_path, today="2026-08-24")
    assert [c["path"] for c in cands] == ["docs/superpowers/plans/2026-01-05-old.md"]
    assert cands[0]["age_days"] > 200


def test_closed_plan_is_not_a_candidate(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/2026-01-05-done.md", status="done")
    assert find_retire_candidates(tmp_path, today="2026-08-24") == []


def test_recent_plan_is_not_a_candidate(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/2026-08-20-fresh.md")
    assert find_retire_candidates(tmp_path, today="2026-08-24") == []


def test_already_archived_is_never_a_candidate(tmp_path):
    """Otherwise the command would keep proposing to archive the archive."""
    _doc(tmp_path, "docs/archive/plans/2026-01-05-old.md")
    assert find_retire_candidates(tmp_path, today="2026-08-24") == []


def test_adr_is_never_a_candidate(tmp_path):
    """An ADR is a permanent record; a superseded one still explains a decision."""
    _doc(tmp_path, "docs/adr/0007-something.md", status="proposed")
    assert find_retire_candidates(tmp_path, today="2026-08-24") == []


def test_excluded_dirs_are_skipped(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/fixtures/2026-01-05-x.md")
    cands = find_retire_candidates(
        tmp_path, today="2026-08-24",
        exclude_dirs=["docs/superpowers/plans/fixtures"],
    )
    assert cands == []


def test_older_than_threshold_is_configurable(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/2026-08-01-x.md")
    assert find_retire_candidates(tmp_path, today="2026-08-24", stale_days=10)
    assert find_retire_candidates(tmp_path, today="2026-08-24", stale_days=90) == []


def test_candidate_carries_commit_count_as_evidence(tmp_path):
    repo = _repo(tmp_path)
    _doc(repo, "docs/superpowers/plans/2026-01-05-old.md")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add plan"], check=True)
    cands = find_retire_candidates(repo, today="2026-08-24")
    assert cands[0]["commits"] == 1


def test_commit_count_is_zero_outside_a_git_repo(tmp_path):
    """Evidence is best-effort — a missing git must not break the listing."""
    _doc(tmp_path, "docs/superpowers/plans/2026-01-05-old.md")
    assert find_retire_candidates(tmp_path, today="2026-08-24")[0]["commits"] == 0


# ── the move ────────────────────────────────────────────────────────────────


def test_archive_target_mirrors_the_section(tmp_path):
    assert archive_target("docs/superpowers/plans/2026-01-05-x.md") == (
        "docs/archive/plans/2026-01-05-x.md"
    )
    assert archive_target("docs/superpowers/specs/2026-01-05-x.md") == (
        "docs/archive/specs/2026-01-05-x.md"
    )


def test_retire_moves_the_file_and_keeps_history(tmp_path):
    repo = _repo(tmp_path)
    _doc(repo, "docs/superpowers/plans/2026-01-05-old.md")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add"], check=True)

    results = retire_files(repo, find_retire_candidates(repo, today="2026-08-24"))

    assert not (repo / "docs/superpowers/plans/2026-01-05-old.md").exists()
    assert (repo / "docs/archive/plans/2026-01-05-old.md").exists()
    assert results[0]["status"] == "moved"
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-status"],
        capture_output=True, text=True).stdout
    assert "docs/archive/plans/2026-01-05-old.md" in staged


def test_retire_refuses_to_overwrite_an_existing_archive_entry(tmp_path):
    repo = _repo(tmp_path)
    _doc(repo, "docs/superpowers/plans/2026-01-05-old.md")
    _doc(repo, "docs/archive/plans/2026-01-05-old.md")
    results = retire_files(repo, find_retire_candidates(repo, today="2026-08-24"))
    assert results[0]["status"] == "skipped"
    assert (repo / "docs/superpowers/plans/2026-01-05-old.md").exists()


# ── evidence: did work ever ship with the document ──────────────────────────
#
# Raw commit count does not discriminate. On h2t-skills the modal value was 2,
# and the second commit was the same one for dozens of files: a bulk
# `docs-lint --fix-frontmatter` pass on 2026-05-26. A tool touched the file;
# nobody worked the plan. What separates a plan that was executed from one that
# was only written is whether any commit touching it also touched code.


def test_work_commits_counts_only_commits_that_also_touched_code(tmp_path):
    repo = _repo(tmp_path)
    _doc(repo, "docs/superpowers/plans/2026-01-05-old.md")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "write the plan"], check=True)

    # a docs-only sweep — the shape that inflated the count
    (repo / "docs/superpowers/plans/2026-01-05-old.md").write_text(
        '---\ntitle: "x"\nstatus: draft\nmilestone: M1\n---\nbody\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "docs: frontmatter"], check=True)

    c = find_retire_candidates(repo, today="2026-08-24")[0]
    assert c["commits"] == 2
    assert c["work_commits"] == 0


def test_a_commit_touching_both_the_doc_and_code_counts_as_work(tmp_path):
    repo = _repo(tmp_path)
    _doc(repo, "docs/superpowers/plans/2026-01-05-old.md")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "plan + implementation"], check=True)

    c = find_retire_candidates(repo, today="2026-08-24")[0]
    assert c["work_commits"] == 1


def test_work_commits_is_zero_outside_a_git_repo(tmp_path):
    _doc(tmp_path, "docs/superpowers/plans/2026-01-05-old.md")
    assert find_retire_candidates(tmp_path, today="2026-08-24")[0]["work_commits"] == 0
