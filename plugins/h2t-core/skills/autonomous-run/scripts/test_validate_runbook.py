import pytest
import runbook_schema as S
from validate_runbook import validate, validate_or_raise, RunbookInvalid, split_sections


def _good_text() -> str:
    parts = []
    for h in S.REQUIRED_SECTIONS:
        body = "content"
        for marker, sec in S.MARKER_SECTION.items():
            if sec == h:
                body += f"\n{marker}"
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


def test_validate_or_raise_raises():
    with pytest.raises(RunbookInvalid):
        validate_or_raise(_good_text().replace("## Gates\n", "## Gone\n"))
