"""A merged PR closes the plans it carried.

Retrospectively this link cannot be recovered — a plan slug appears in 7 of 60
merged PR bodies on this repo, and commit counts cannot separate "done and never
updated" from "abandoned". At the moment of the merge nothing has to be
inferred: the PR lists its own files. The link was never hard to compute, it was
just never written down while it was still free.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


def _load():
    path = Path(__file__).parents[2] / "h2t_ops" / "hooks" / "plan_closer.py"
    spec = importlib.util.spec_from_file_location("plan_closer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _plan(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ── reading the PR number out of the command ────────────────────────────────


def test_pr_number_from_an_explicit_merge():
    m = _load()
    assert m.extract_pr_number("gh pr merge 408 --squash --delete-branch") == 408


def test_pr_number_ignores_flag_values():
    m = _load()
    assert m.extract_pr_number("gh pr merge --squash --delete-branch") is None


def test_non_merge_commands_are_not_ours():
    m = _load()
    assert m.extract_pr_number("gh pr view 408") is None
    assert m.extract_pr_number("git commit -m 'gh pr merge 12'") is None


# ── flipping the status ─────────────────────────────────────────────────────


_VIEW = {
    "state": "MERGED",
    "files": [
        {"path": "docs/superpowers/plans/2026-08-24-thing.md"},
        {"path": "docs/superpowers/specs/2026-08-24-thing-design.md"},
        {"path": "lib/thing.py"},
        {"path": "docs/reports/2026-08-24-evidence.md"},
    ],
}


def test_plans_and_specs_in_the_pr_are_closed(tmp_path):
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\ntitle: "T"\nstatus: "draft"\ndate: "2026-08-24"\n---\nbody\n')
    _plan(tmp_path, "docs/superpowers/specs/2026-08-24-thing-design.md",
          '---\ntitle: "T"\nstatus: draft\n---\nbody\n')

    changed = m.close_plans_for_pr(tmp_path, 408, _VIEW)

    assert {c["path"] for c in changed} == {
        "docs/superpowers/plans/2026-08-24-thing.md",
        "docs/superpowers/specs/2026-08-24-thing-design.md",
    }
    text = (tmp_path / "docs/superpowers/plans/2026-08-24-thing.md").read_text()
    assert 'status: "done"' in text
    assert 'pr: 408' in text
    assert "body" in text


def test_reports_and_code_are_left_alone(tmp_path):
    """Only plans and specs carry a lifecycle. A report is a record of a moment."""
    m = _load()
    _plan(tmp_path, "docs/reports/2026-08-24-evidence.md",
          '---\ntitle: "E"\nstatus: "draft"\n---\nx\n')
    m.close_plans_for_pr(tmp_path, 408, _VIEW)
    assert 'status: "draft"' in (tmp_path / "docs/reports/2026-08-24-evidence.md").read_text()


def test_an_unmerged_pr_changes_nothing(tmp_path):
    """`gh pr merge` can fail. The hook runs either way."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    assert m.close_plans_for_pr(tmp_path, 408, {"state": "OPEN", "files": _VIEW["files"]}) == []
    assert 'status: "draft"' in (tmp_path / "docs/superpowers/plans/2026-08-24-thing.md").read_text()


def test_an_already_closed_plan_is_not_touched_again(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
              '---\nstatus: "done"\npr: 12\n---\nx\n')
    before = p.read_text()
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []
    assert p.read_text() == before


def test_a_file_deleted_by_the_pr_is_skipped(tmp_path):
    """The PR may have moved a plan into docs/archive/ — nothing to rewrite."""
    m = _load()
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []


def test_a_plan_without_frontmatter_is_skipped_not_corrupted(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md", "# Plain\n\nbody\n")
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []
    assert p.read_text() == "# Plain\n\nbody\n"


def test_existing_pr_field_is_replaced_not_duplicated(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
              '---\nstatus: "draft"\npr: 12\n---\nx\n')
    m.close_plans_for_pr(tmp_path, 408, _VIEW)
    assert p.read_text().count("pr:") == 1
    assert "pr: 408" in p.read_text()


# ── the hook's own output contract ──────────────────────────────────────────


def test_hook_reports_on_both_channels(tmp_path, monkeypatch):
    """The model reads additionalContext; the user reads systemMessage."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n, repo=None: _VIEW)
    reply = m.handle({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 408 --squash"}})
    assert "408" in reply.notice
    assert "2026-08-24-thing.md" in reply.text


def test_hook_is_silent_for_unrelated_commands():
    m = _load()
    reply = m.handle({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert (reply.text, reply.notice, reply.block) == ("", "", False)


def test_message_distinguishes_a_plan_from_its_spec(tmp_path, monkeypatch):
    """Plan and spec routinely share a stem — basenames alone read as a duplicate."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    _plan(tmp_path, "docs/superpowers/specs/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n, repo=None: {
        "state": "MERGED",
        # `lib/thing.py` is what makes this a PR that implemented something. Without
        # a code file the hook is silent by design, and this test is about naming.
        "files": [{"path": "docs/superpowers/plans/2026-08-24-thing.md"},
                  {"path": "docs/superpowers/specs/2026-08-24-thing.md"},
                  {"path": "lib/thing.py"}],
    })
    msg = m.handle({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 408"}}).notice
    assert "plans/2026-08-24-thing.md" in msg
    assert "specs/2026-08-24-thing.md" in msg


# ── "the PR listed it" is not "the document is finished" ────────────────────


_DOCS_ONLY_VIEW = {
    "state": "MERGED",
    "files": [
        {"path": "docs/superpowers/specs/2026-08-23-lms-design.md"},
        {"path": "README.md"},
    ],
}


def test_a_documentation_only_pr_closes_nothing(tmp_path):
    """The defect, in the shape it actually appeared (#455).

    h2t-business PRs #58, #59 and #60 on 2026-08-27 were documentation edits. Each
    stamped `done` on a 2300-line decision map carrying four open questions in one
    section. A PR that changed no code implemented nothing, and the file list says so.
    """
    m = _load()
    doc = _plan(tmp_path, "docs/superpowers/specs/2026-08-23-lms-design.md",
                '---\ntitle: "LMS"\nstatus: "draft"\n---\nbody\n')

    assert m.close_plans_for_pr(tmp_path, 58, _DOCS_ONLY_VIEW) == []
    assert 'status: "draft"' in doc.read_text(encoding="utf-8")
    assert "pr: 58" not in doc.read_text(encoding="utf-8")


def test_a_pr_that_changed_code_still_closes_its_plan(tmp_path):
    """The control. Without it, "closes nothing" and "hook is broken" look alike."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nbody\n')
    changed = m.close_plans_for_pr(tmp_path, 408, _VIEW)
    assert [c["path"] for c in changed] == ["docs/superpowers/plans/2026-08-24-thing.md"]


def test_an_empty_file_list_is_not_permission_to_stamp():
    """`gh` returning nothing must read as "implemented nothing", not as a free hand.

    Asserted on `_implements_something` rather than through `close_plans_for_pr`: with
    no files there is nothing to iterate either way, so the end-to-end version passed
    with the discriminator deleted. It was a comment, not a test.
    """
    m = _load()
    assert m._implements_something({"files": []}) is False
    assert m._implements_something({}) is False
    assert m._implements_something({"files": [{"path": "lib/thing.py"}]}) is True


def test_a_living_document_is_never_closed(tmp_path):
    """A decision map has no finished state; it lives as long as its open questions.

    `approved` granted permanent immunity while `draft` never could — so the documents
    still in work were the ones getting stamped. `lifecycle: living` is the author
    saying which kind of document this is, rather than the hook guessing.
    """
    m = _load()
    doc = _plan(tmp_path, "docs/superpowers/specs/2026-08-23-lms-design.md",
                '---\ntitle: "LMS"\nstatus: "draft"\nlifecycle: living\n---\nbody\n')
    view = {
        "state": "MERGED",
        "files": [
            {"path": "docs/superpowers/specs/2026-08-23-lms-design.md"},
            {"path": "lib/lms.py"},
        ],
    }
    assert m.close_plans_for_pr(tmp_path, 61, view) == []
    assert 'status: "draft"' in doc.read_text(encoding="utf-8")


def test_the_message_states_what_it_did_not_what_is_true(tmp_path, monkeypatch):
    """It used to announce that the PR "закрыл" the documents — a claim about the
    world, from a hook that can only know what it wrote."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n, repo=None: {
        "state": "MERGED",
        "files": [{"path": "docs/superpowers/plans/2026-08-24-thing.md"},
                  {"path": "lib/thing.py"}],
    })
    msg = m.handle({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 408"}}).notice
    assert "проставлен status: done" in msg
    assert "закрыл" not in msg



def test_a_refused_write_is_said_not_dropped(tmp_path, monkeypatch):
    """hooks.md: a silent hook is a failure. The allow-list refusing the stamp leaves
    the file as it was and names the path on both channels; the hook still exits 0."""
    from h2t_ops.core import repo_writers
    m = _load()
    doc = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md", '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n, repo=None: {"state": "MERGED", "files": [
        {"path": "docs/superpowers/plans/2026-08-24-thing.md"}, {"path": "lib/thing.py"}]})
    monkeypatch.setitem(repo_writers.REPO_WRITERS, "plan-closer", {})
    reply = m.handle({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 408"}})
    assert 'status: "draft"' in doc.read_text(encoding="utf-8")
    assert "plans/2026-08-24-thing.md" in reply.notice and "не удалось" in reply.notice
    assert "may not replace" in reply.text
    assert reply.block is False


# ── which repository the merge targeted (#662) ──────────────────────────────


@pytest.mark.parametrize("command, expected", [
    ("gh pr merge 25 --squash", (25, None, None)),
    ("gh pr merge 25 --repo owner/B --squash", (25, "owner/B", None)),
    ("gh pr merge --repo owner/B 25", (25, "owner/B", None)),
    ("gh pr merge 25 --repo=owner/B", (25, "owner/B", None)),
    ("gh pr merge 25 -R owner/B", (25, "owner/B", None)),
    ("gh pr merge 25 -Rowner/B", (25, "owner/B", None)),
    ("GH_REPO=owner/B gh pr merge 25", (25, "owner/B", None)),
    ("cd ~/B && gh pr merge 25 --squash", (25, None, "~/B")),
    ('cd "/x/my B"; gh pr merge 25', (25, None, "/x/my B")),
    ("git fetch && gh pr merge 25", (25, None, None)),
    # a flag value is never the number, quoted or not
    ("gh pr merge 25 --subject 'fix 7 things' --squash", (25, None, None)),
    ("gh pr merge -t 7 25", (25, None, None)),
])
def test_merge_target_reads_the_repository_the_merge_went_to(command, expected):
    m = _load()
    assert m.merge_target(command) == expected


@pytest.mark.parametrize("command", [
    "gh pr merge --squash",                       # current branch: a guess
    "gh pr merge https://github.com/o/r/pull/25",  # a URL or branch is not a number
    "cd A && cd B && gh pr merge 25",             # two cds
    "cd - && gh pr merge 25",
    "cd && gh pr merge 25",
    "pushd B && gh pr merge 25",
    "(cd B && gh pr merge 25)",
    "gh pr merge 25 --subject 'unclosed",         # unparseable
])
def test_merge_target_is_none_when_the_repository_is_uncertain(command):
    m = _load()
    assert m.merge_target(command) is None


def _git_repo(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin",
                    f"git@github.com:{slug}.git"], check=True)
    return root


_SPEC = "docs/superpowers/specs/2026-08-24-thing-design.md"


def _a_with_its_own_pr_25(tmp_path, monkeypatch, m):
    """Repo A, whose own PR #25 was merged long ago and carried a draft spec. The fake gh
    answers for A's PR whatever repository is asked: that is what gh did without --repo."""
    a = _git_repo(tmp_path / "A", "owner/A")
    spec = _plan(a, _SPEC, '---\nstatus: "draft"\n---\nx\n')
    asked = []

    def view(root, n, repo=None):
        asked.append((Path(root), n, repo))
        return {"state": "MERGED", "files": [{"path": _SPEC}, {"path": "lib/thing.py"}]}

    monkeypatch.setattr(m, "_pr_view", view)
    monkeypatch.chdir(a)
    return a, spec, asked


def test_a_merge_in_another_repository_stamps_nothing_here(tmp_path, monkeypatch):
    m = _load()
    _a, spec, _asked = _a_with_its_own_pr_25(tmp_path, monkeypatch, m)
    reply = m.handle({"tool_name": "Bash", "tool_input": {
        "command": "gh pr merge 25 --repo owner/B --squash"}})
    assert 'status: "draft"' in spec.read_text(encoding="utf-8")
    assert (reply.text, reply.notice) == ("", "")


def test_a_merge_named_for_this_repository_still_closes_and_asks_gh_for_it(
        tmp_path, monkeypatch):
    m = _load()
    a, spec, asked = _a_with_its_own_pr_25(tmp_path, monkeypatch, m)
    m.handle({"tool_name": "Bash", "tool_input": {
        "command": "gh pr merge 25 -R https://github.com/Owner/A.git --squash"}})
    assert 'status: "done"' in spec.read_text(encoding="utf-8")
    assert asked[0][2] == "owner/a"


def test_a_leading_cd_moves_the_repository_root(tmp_path, monkeypatch):
    m = _load()
    a, spec_a, asked = _a_with_its_own_pr_25(tmp_path, monkeypatch, m)
    b = _git_repo(tmp_path / "B", "owner/B")
    spec_b = _plan(b, _SPEC, '---\nstatus: "draft"\n---\nx\n')
    m.handle({"tool_name": "Bash", "tool_input": {"command": f'cd "{b}" && gh pr merge 25'}})
    assert 'status: "draft"' in spec_a.read_text(encoding="utf-8")
    assert 'status: "done"' in spec_b.read_text(encoding="utf-8")
    assert asked[0][0] == b.resolve()


def test_a_cd_to_a_missing_directory_does_nothing(tmp_path, monkeypatch):
    m = _load()
    _a, spec, asked = _a_with_its_own_pr_25(tmp_path, monkeypatch, m)
    m.handle({"tool_name": "Bash", "tool_input": {
        "command": f'cd "{tmp_path / "nowhere"}" && gh pr merge 25'}})
    assert 'status: "draft"' in spec.read_text(encoding="utf-8")
    assert asked == []
