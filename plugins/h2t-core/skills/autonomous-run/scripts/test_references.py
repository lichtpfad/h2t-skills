from pathlib import Path
import pytest
import runbook_schema as S

_REF = Path(__file__).resolve().parents[1] / "references"
_SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


@pytest.mark.skipif(not (_REF / "decision-protocol.md").exists(), reason="M3 not built yet")
def test_decision_protocol_lists_all_hard_stops():
    text = (_REF / "decision-protocol.md").read_text(encoding="utf-8")
    for marker in S.MARKER_SECTION:
        if marker != "hard-stop or unresolvable blocker":
            assert marker in text


@pytest.mark.skipif(not (_REF / "gates.md").exists(), reason="M3 not built yet")
def test_gates_reference_has_codex_and_council():
    text = (_REF / "gates.md").read_text(encoding="utf-8").lower()
    assert "codex" in text and "council" in text and "n_gate_attempts" in text.replace(" ", "_")


@pytest.mark.skipif(not _SKILL.exists(), reason="M3 not built yet")
def test_skill_frontmatter_has_name_and_description():
    text = _SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    head = text.split("---", 2)[1]
    assert "name:" in head and "description:" in head
