import pytest
import runbook_schema as S
from validate_runbook import RunbookInvalid, split_sections, validate, validate_or_raise


def _good_text() -> str:
    parts = []
    for h in S.REQUIRED_SECTIONS:
        body = "content"
        for marker, sec in S.MARKER_SECTION.items():
            if sec == h:
                body += f"\n{marker}"
        if h == "## Pipeline steps":
            body += "\n" + "\n".join(f"- [ ] **{s}**" for s in S.PIPELINE_STEPS)
        parts.append(f"{h}\n{body}")
    return "\n\n".join(parts) + "\n"


def test_split_sections_maps_headings_to_bodies():
    secs = split_sections(_good_text())
    assert "## Decision-protocol" in secs
    assert "Money / budget" in secs["## Decision-protocol"]


def test_valid_text_returns_empty_problem_list():
    assert validate(_good_text()) == []


def test_missing_section_is_reported():
    text = _good_text().replace("## Decision-protocol\n", "## Nope\n")
    assert any("Decision-protocol" in p for p in validate(text))


def test_marker_moved_to_wrong_section_is_rejected():
    # gut Decision-protocol content but re-append the markers under Execution principles
    good = _good_text()
    markers = "\n".join(m for m, s in S.MARKER_SECTION.items() if s == "## Decision-protocol")
    text = good.replace("Irreversible / destructive", "").replace("Money / budget", "") \
               .replace("Scope / architecture change", "").replace("Gate not fixable in", "")
    text = text.replace("## Execution principles\ncontent",
                        "## Execution principles\ncontent\n" + markers)
    assert any("Decision-protocol" in p for p in validate(text))


def test_unresolved_token_is_rejected():
    assert any("TOKEN" in p or "<<" in p for p in validate(_good_text() + "\n<<branch>>"))


def test_duplicate_required_section_is_rejected():
    # gut the real Decision-protocol, append a decoy with only the markers (codex-gate-M1 P1)
    text = _good_text() + "\n## Decision-protocol\nMoney / budget\n"
    assert any("duplicate" in p and "Decision-protocol" in p for p in validate(text))


def test_empty_body_section_is_rejected():
    text = _good_text().replace("## Decision-log\ncontent", "## Decision-log\n")
    assert any("empty body" in p and "Decision-log" in p for p in validate(text))


def test_missing_pipeline_step_is_rejected():
    text = _good_text().replace("- [ ] **handoff**", "")
    assert any("handoff" in p and "pipeline" in p.lower() for p in validate(text))


def test_validate_or_raise_raises():
    with pytest.raises(RunbookInvalid):
        validate_or_raise(_good_text().replace("## Gates\n", "## Gone\n"))
