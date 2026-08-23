import inspect

import pytest
import runbook_schema as S
from new_runbook import PIPELINE_CONTRACT, create_runbook, render
from validate_runbook import RunbookInvalid, validate, validate_or_raise

_FIELDS = dict(title="Demo", today="2026-07-09", runbook_path="docs/x-runbook.md",
               branch="feat/x", spec_path="docs/x-spec.md", issue="#1",
               venv_test="pytest tests/", e2e_state="N/A")


def test_rendered_runbook_passes_validator():
    assert validate(render(**_FIELDS)) == []


def test_pipeline_rendered_as_checkboxes_for_every_step():
    text = render(**_FIELDS)
    for step in S.PIPELINE_STEPS:
        assert f"- [ ] **{step}**" in text


def test_tokens_are_substituted():
    text = render(**_FIELDS)
    assert "<<" not in text and ">>" not in text
    assert "feat/x" in text and "autonomous-run resume docs/x-runbook.md" in text


def test_contract_covers_every_step():
    assert set(PIPELINE_CONTRACT) == set(S.PIPELINE_STEPS)


def test_render_kwargs_match_run_fields():
    params = [p for p in inspect.signature(render).parameters]
    assert set(params) == set(S.RUN_FIELDS)


def test_invalid_e2e_state_rejected():
    with pytest.raises(ValueError):
        render(**{**_FIELDS, "e2e_state": "maybe"})


def test_tampered_output_is_rejected():
    text = render(**_FIELDS)
    with pytest.raises(RunbookInvalid):
        validate_or_raise(text.replace("Irreversible / destructive", ""))


def test_shell_redirect_in_venv_test_not_a_token_residue():
    # a `>>` in a field value must not trip the token-residue check (codex-council Lens A)
    text = render(**{**_FIELDS, "venv_test": "pytest x >> log.txt"})
    assert validate(text) == []


def test_e2e_generate_real_runbook_and_validate(tmp_path):
    out = tmp_path / "2026-07-09-autonomous-run-orchestrator-runbook.md"
    p = create_runbook(
        str(out), title="Autonomous run orchestrator", today="2026-07-09",
        runbook_path=str(out), branch="feat/autonomous-run-orchestrator",
        spec_path="docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md",
        issue="(none)", venv_test="pytest plugins/h2t-core/skills/autonomous-run/scripts/",
        e2e_state="applies (generate->validate)")
    text = p.read_text(encoding="utf-8")
    assert validate(text) == []
    assert "autonomous-run resume" in text
    for step in S.PIPELINE_STEPS:
        assert f"- [ ] **{step}**" in text
