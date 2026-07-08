import runbook_schema as S
from new_runbook import render
from runbook_state import parse_steps, unchecked_steps


def _rendered_with_two_done() -> str:
    text = render(title="D", today="2026-07-09", runbook_path="p.md", branch="b",
                  spec_path="s.md", issue="#1", venv_test="pytest", e2e_state="N/A")
    text = text.replace("- [ ] **write-spec**", "- [x] **write-spec**", 1)
    return text.replace("- [ ] **review-spec**", "- [x] **review-spec**", 1)


def test_parse_only_pipeline_steps_not_gate_checkboxes():
    names = [n for n, _ in parse_steps(_rendered_with_two_done())]
    assert names == S.PIPELINE_STEPS      # gate/decision-log checkboxes excluded


def test_unchecked_steps_after_two_done():
    assert unchecked_steps(_rendered_with_two_done()) == S.PIPELINE_STEPS[2:]


def test_all_checked_returns_empty():
    text = _rendered_with_two_done()
    for step in S.PIPELINE_STEPS:
        text = text.replace(f"- [ ] **{step}**", f"- [x] **{step}**")
    assert unchecked_steps(text) == []


def test_decoy_checkbox_outside_pipeline_ignored():
    # a stray checkbox in another section must not become resume state
    text = _rendered_with_two_done().replace(
        "## Decision-log\n", "## Decision-log\n- [ ] **write-spec**\n")
    names = [n for n, _ in parse_steps(text)]
    assert names == S.PIPELINE_STEPS      # still only the pipeline block's steps
