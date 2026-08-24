"""Docs debt is a number the briefing shows every session.

The counts here are the whole point of the loop: 112 of 143 plans carried
`status: "draft"` on 2026-08-24, 47 of them written in May. Nothing displayed
that number anywhere, so nobody saw it grow.
"""

from datetime import date

from gather.docs_debt import gather_docs_debt

TODAY = date(2026, 8, 24)


def _plan(root, name: str, status: str | None = "draft") -> None:
    d = root / "docs" / "superpowers" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    fm = f'---\ntitle: "x"\nstatus: {status}\n---\n' if status else "---\ntitle: x\n---\n"
    (d / name).write_text(fm + "body\n", encoding="utf-8")


def test_no_docs_tree_returns_empty(tmp_path):
    assert gather_docs_debt(tmp_path, today=TODAY) == {}


def test_counts_open_and_total(tmp_path):
    _plan(tmp_path, "2026-08-20-a.md", "draft")
    _plan(tmp_path, "2026-08-20-b.md", '"done"')
    _plan(tmp_path, "2026-08-20-c.md", "in-progress")
    debt = gather_docs_debt(tmp_path, today=TODAY)
    assert debt["total"] == 3
    assert debt["open"] == 2


def test_done_synonyms_are_not_open(tmp_path):
    for i, s in enumerate(["done", "complete", "accepted", "superseded", "deprecated"]):
        _plan(tmp_path, f"2026-08-2{i}-{s}.md", s)
    assert gather_docs_debt(tmp_path, today=TODAY)["open"] == 0


def test_missing_status_counts_as_open(tmp_path):
    """Unknown is not finished — a debt metric rounds toward the debt."""
    _plan(tmp_path, "2026-08-20-nostatus.md", status=None)
    assert gather_docs_debt(tmp_path, today=TODAY)["open"] == 1


def test_stale_is_open_and_old(tmp_path):
    _plan(tmp_path, "2026-05-01-old-draft.md", "draft")   # 115 days
    _plan(tmp_path, "2026-05-01-old-done.md", "done")     # old but finished
    _plan(tmp_path, "2026-08-20-fresh.md", "draft")       # open but fresh
    debt = gather_docs_debt(tmp_path, today=TODAY)
    assert debt["stale"] == 1
    assert debt["stale_days"] == 60


def test_date_falls_back_to_frontmatter_when_filename_has_none(tmp_path):
    d = tmp_path / "docs" / "superpowers" / "plans"
    d.mkdir(parents=True)
    (d / "legacy-plan.md").write_text(
        '---\ntitle: x\nstatus: draft\ndate: "2026-01-05"\n---\n', encoding="utf-8"
    )
    assert gather_docs_debt(tmp_path, today=TODAY)["stale"] == 1


def test_specs_and_adr_are_counted_too(tmp_path):
    for sub in ["superpowers/specs", "adr"]:
        d = tmp_path / "docs" / sub
        d.mkdir(parents=True)
        (d / "2026-05-01-x.md").write_text(
            "---\ntitle: x\nstatus: draft\n---\n", encoding="utf-8"
        )
    debt = gather_docs_debt(tmp_path, today=TODAY)
    assert debt["total"] == 2
    assert debt["stale"] == 2


def test_archive_is_not_debt(tmp_path):
    """Retired documents left the pool — counting them would make the number
    unfixable by the only remedy the loop offers."""
    d = tmp_path / "docs" / "archive" / "plans"
    d.mkdir(parents=True)
    (d / "2026-05-01-x.md").write_text(
        "---\ntitle: x\nstatus: draft\n---\n", encoding="utf-8"
    )
    assert gather_docs_debt(tmp_path, today=TODAY) == {}
