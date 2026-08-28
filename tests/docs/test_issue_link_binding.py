"""A plan or spec must name the work it belongs to (#421, #422, #423).

`status` in a plan is written once by the generator and never again by anything that knows
whether the work happened. It is unfalsifiable — no check can call a value wrong, because
there is nothing to compare it against. Measured over 42 legacy documents on 2026-08-26:
41 carried `status: draft`, 29 had shipped in full and 10 in part, and the field had never
moved. The `issue` field is what makes the other one checkable.

Three entry paths, three gates: the generator (#422), the PreToolUse hook (#423), and CI
(#423). This file covers the rule they share and the two ends that can be imported.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "h2t-dev" / "lib"))
sys.path.insert(0, str(ROOT / "plugins" / "h2t-core" / "hooks-handlers"))

from docs.common import FRONTMATTER_RULES, issue_link_problem  # noqa: E402

# --- the rule itself ------------------------------------------------------------------

@pytest.mark.parametrize("fields,linked", [
    ({"issue": "421"}, True),
    ({"issue": "#421"}, True),
    ({"issue": "none", "reason": "one-off note, no work behind it"}, True),
    ({}, False),
    ({"issue": ""}, False),
    ({"issue": '""'}, False),
    ({"issue": "none"}, False),
    ({"issue": "none", "reason": ""}, False),
    ({"issue": "see the other doc"}, False),
])
def test_issue_link_problem(fields, linked):
    assert (issue_link_problem(fields) is None) is linked


def test_empty_string_is_not_a_link():
    """The state fix-safe leaves behind when it backfills the new field. If this passed,
    the backfill would close the gap it was supposed to make visible."""
    assert issue_link_problem({"issue": ""}) is not None


# --- the field is required, and only for plans and specs ------------------------------

def test_plans_and_specs_require_issue():
    assert "issue" in FRONTMATTER_RULES["superpowers/plans"]
    assert "issue" in FRONTMATTER_RULES["superpowers/specs"]


def test_adr_does_not():
    """An ADR records a decision, not work with a state."""
    assert "issue" not in FRONTMATTER_RULES["adr"]


# --- the hook -------------------------------------------------------------------------

def _guard(path: str, content: str) -> int:
    import structure_guard
    code, _ = structure_guard.check_issue_link(path, content, {})
    return code


_FM = '---\ntitle: "X"\nstatus: "draft"\n{extra}---\n\n# X\n'


def test_hook_blocks_a_plan_with_no_issue():
    assert _guard("docs/superpowers/plans/2026-08-28-x.md", _FM.format(extra="")) == 2


def test_hook_blocks_none_without_a_reason():
    assert _guard("docs/superpowers/plans/2026-08-28-x.md",
                  _FM.format(extra='issue: "none"\n')) == 2


def test_hook_passes_a_linked_plan():
    """Negative control: without this, a check that blocks everything would look correct."""
    assert _guard("docs/superpowers/plans/2026-08-28-x.md",
                  _FM.format(extra='issue: "421"\n')) == 0


def test_hook_passes_none_with_a_reason():
    assert _guard("docs/superpowers/plans/2026-08-28-x.md",
                  _FM.format(extra='issue: "none"\nreason: "no work behind it"\n')) == 0


def test_hook_ignores_an_adr():
    assert _guard("docs/adr/0003-x.md", _FM.format(extra="")) == 0


def test_hook_ignores_a_document_with_no_frontmatter():
    """check_frontmatter_presence owns that case — one write must not produce two messages."""
    assert _guard("docs/superpowers/plans/2026-08-28-x.md", "# X\n") == 0


# --- the generator --------------------------------------------------------------------

_LINT = ROOT / "plugins" / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py"


def _new(tmp_path, *args) -> subprocess.CompletedProcess:
    for d in ("docs/superpowers/plans", "docs/superpowers/specs", "docs/adr", ".git"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(_LINT), "new", *args, "--root", str(tmp_path)],
        capture_output=True, text=True,
    )


def test_generator_refuses_a_plan_with_no_link_and_writes_nothing(tmp_path):
    r = _new(tmp_path, "plan", "unlinked")
    assert r.returncode == 2, r.stderr
    assert not list((tmp_path / "docs/superpowers/plans").glob("*.md")), (
        "the refusal must leave no file — a half-created document is worse than none"
    )


def test_generator_accepts_an_argued_opt_out(tmp_path):
    r = _new(tmp_path, "plan", "opt-out", "--no-issue", "one-off note")
    assert r.returncode == 0, r.stderr
    written = next((tmp_path / "docs/superpowers/plans").glob("*.md")).read_text(encoding="utf-8")
    assert 'issue: "none"' in written
    assert 'reason: "one-off note"' in written


def test_generator_leaves_adr_alone(tmp_path):
    r = _new(tmp_path, "adr", "some-decision")
    assert r.returncode == 0, r.stderr
    assert list((tmp_path / "docs/adr").glob("*.md"))
