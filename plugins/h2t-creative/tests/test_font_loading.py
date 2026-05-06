"""Font link injection: profile.yaml web_fonts list -> <link> tags in <head>."""
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
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, asm.PROFILES_DIR / "h2t-editorial", out)
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
