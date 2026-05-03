"""Smoke tests: every profile × palette assembles without error."""
import pytest
from pathlib import Path

import assembler as asm

PROFILES = {
    "h2t-default":   ["default"],
    "h2t-editorial": ["default", "night", "warm"],
    "h2t-graphs":    ["default", "blue", "green"],
    "h2t-mono":      ["default", "blue", "white"],
    "h2t-pfad":      ["default"],
    "h2t-terminal":  ["default", "amber", "cyan"],
}

_LANDING_RECIPE = {
    "title": "Smoke Test",
    "sections": [
        {"component": "hero", "content": {"headline": "Title", "subline": "Sub"}},
        {"component": "cta",  "content": {"text": "Go", "href": "https://example.com"}},
    ],
}

_DECK_RECIPE = {
    "title": "Smoke Deck",
    "slides": [
        {"layout": "title-only",  "content": {"headline": "Slide 1"}},
        {"layout": "title-body",  "content": {"headline": "Slide 2", "body": "<p>body</p>"}},
    ],
}


@pytest.mark.parametrize("profile,palette", [
    (p, pal) for p, pals in PROFILES.items() for pal in pals
])
def test_landing_smoke(tmp_path, profile, palette):
    profile_dir = asm.PROFILES_DIR / profile
    out = tmp_path / "out"
    asm.assemble_landing(_LANDING_RECIPE, profile_dir, out, palette=palette)
    assert (out / "index.html").exists()
    assert (out / "base.css").exists()
    assert (out / "profile.css").exists()


@pytest.mark.parametrize("profile", list(PROFILES.keys()))
def test_deck_smoke(tmp_path, profile):
    profile_dir = asm.PROFILES_DIR / profile
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, profile_dir, out)
    assert (out / "index.html").exists()
    assert (out / "profile.css").exists()
