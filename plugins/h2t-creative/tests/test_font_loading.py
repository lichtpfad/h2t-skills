"""Font link injection: profile.yaml web_fonts list -> <link> tags in <head>."""
import pytest

import assembler as asm

_RECIPE = {
    "title": "Font Test",
    "sections": [
        {"component": "hero", "content": {"headline": "T", "subline": "S"}},
    ],
}

_DECK_RECIPE = {
    "title": "Deck Font Test",
    "slides": [{"layout": "title-only", "content": {"headline": "T"}}],
}


def test_font_links_editorial(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-editorial", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" in html
    assert "Playfair" in html


# test_font_links_mono removed — h2t-mono now uses golden hero contract,
# tested in test_r1_legacy_fidelity.py (font tokens checked there).


def test_no_font_links_default(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-default", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" not in html


def test_font_links_deck_editorial(tmp_path):
    """Generic legacy-vocab font-link smoke for editorial deck.

    Mirrors R2a T3.5 mitigation for h2t-terminal: once a profile gets a
    `deck/tokens.css`, `_is_deck_form_profile` flips TRUE and the legacy
    multi-file vocab (`title-only`) no longer assembles. R2b T1 introduces
    `profiles/h2t-editorial/deck/tokens.css`, so this test must skip until
    R2b T7 ships the form-v2 validation recipe + layouts (a dedicated
    `test_font_links_deck_editorial_form_v2` will land then).
    """
    profile_dir = asm.PROFILES_DIR / "h2t-editorial"
    if asm._is_deck_form_profile(profile_dir):
        pytest.skip(
            "h2t-editorial is deck-form (R2b T1); form-v2 font-link smoke "
            "lands at R2b T7 alongside validation/recipe-deck.yaml."
        )
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, profile_dir, out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" in html


def test_font_links_deck_terminal(tmp_path):
    """Terminal is deck-form; font link must end up inlined in the single-file
    output (T9 §5.9). Drive via the validation recipe so the layout vocabulary
    matches the form-v2 path."""
    import yaml as _yaml

    profile_dir = asm.PROFILES_DIR / "h2t-terminal"
    recipe = _yaml.safe_load(
        (profile_dir / "validation" / "recipe-deck.yaml").read_text(encoding="utf-8")
    )
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out, palette=recipe.get("palette", "default"))
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" in html
    assert "JetBrains+Mono" in html or "JetBrains Mono" in html


def test_preconnect_hints(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-editorial", out)
    html = (out / "index.html").read_text()
    assert 'rel="preconnect"' in html
    assert "fonts.gstatic.com" in html
