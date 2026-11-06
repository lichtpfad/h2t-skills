"""Deck block roles: one markup and one stylesheet for every profile."""

import re

import pytest

from h2t_ops.tools.creative import assembler as asm

DECK_CSS = (asm.BASE_DIR / "deck.css").read_text(encoding="utf-8")
ALIASES = dict(re.findall(r"(--role-[\w-]+):\s*([^;]+);", DECK_CSS))


def _defined(profile_dir, palette) -> set[str]:
    text = (profile_dir / "tokens.css").read_text(encoding="utf-8")
    pal = profile_dir / "palettes" / f"{palette}.css"
    if pal.exists():
        text += pal.read_text(encoding="utf-8")
    return set(re.findall(r"(--[\w-]+)\s*:", text))


PROFILE_PALETTES = [
    (d.name, p.stem)
    for d in sorted(asm.PROFILES_DIR.iterdir()) if (d / "tokens.css").exists()
    for p in (sorted((d / "palettes").glob("*.css")) or [d / "default.css"])
]


def test_aliases_are_declared():
    assert {"--role-text", "--role-muted", "--role-surface", "--role-accent", "--role-display", "--role-body"} <= set(ALIASES)


@pytest.mark.parametrize("profile,palette", PROFILE_PALETTES)
def test_every_alias_resolves_in_every_profile(profile, palette):
    defined = _defined(asm.PROFILES_DIR / profile, palette)
    unresolved = [a for a, chain in ALIASES.items()
                  if not any(v in defined for v in re.findall(r"var\((--[\w-]+)", chain))]
    assert unresolved == [], f"{profile}/{palette}: no token behind {unresolved}"


def test_rules_use_only_aliases():
    rules = DECK_CSS.split("--role-body:", 1)[1].split("}", 1)[1]
    raw = sorted(set(re.findall(r"var\((--(?!role-|radius-)[\w-]+)", rules)))
    assert raw == [], f"deck.css reads profile tokens directly: {raw}"


SLIDE = {"title": "S", "layout": "title-body", "content": {
    "headline": "Market",
    "kicker": ["1. Market", "Question: what is taken?"],
    "blocks": [
        {"role": "thesis", "text": "One sentence."},
        {"role": "text", "text": "Plain paragraph."},
        {"role": "cards", "label": "Options", "items": ["Spa — long.", {"title": "Doctor.", "text": "When it hurts."}]},
        {"role": "steps", "items": ["Try.", "Talk.", "Choose."]},
        {"role": "number", "figures": ["44%", "72%"], "items": ["Share 44%.", "Revenue 72%."]},
        {"role": "number", "figures": ["13 of 35"], "text": "Bought on day one: 13 of 35."},
        {"role": "quote", "label": "Came without a problem:", "quotes": [{"text": "«Q1.»", "by": "client"}]},
        {"role": "quote", "quotes": [{"text": "«Q2.»"}]},
        {"role": "table", "header": ["Rival", "Frame"], "rows": [["North", "Sport"]]},
        {"role": "figure", "svg": "<svg viewBox='0 0 1 1'></svg>"},
        {"role": "conclusion", "text": "Conclusion: so."},
        {"role": "note", "text": "No data for that."},
    ],
}}


def _page(tmp_path, recipe):
    out = tmp_path / "out"
    asm.assemble_deck({"title": "D", **recipe}, asm.PROFILES_DIR / "h2t-default", out)
    return (out / "index.html").read_text(encoding="utf-8")


def test_blocks_render_each_role(tmp_path):
    page = _page(tmp_path, {"slides": [SLIDE]})
    for marker in ['<div class="thesis"><p>One sentence.</p></div>', "<p>Plain paragraph.</p>",
                   '<p class="block-label">Options</p><div class="cards n2 cards--short">',
                   '<div class="card"><b>Doctor.</b> When it hurts.</div>',
                   '<ol class="steps n3"><li>Try.</li>', '<div class="figures n2"><div><b>44%</b><span>Share 44%.</span>',
                   '<div class="figure-one"><div class="figure-one__figs"><b>13 of 35</b>',
                   '<figcaption>— client</figcaption>', '<div class="quote-row">',
                   "<th>Rival</th>", "<td>North</td>", '<div class="deck-figure"><svg',
                   '<div class="conclusion"><p>Conclusion: so.</p></div>', '<div class="note">']:
        assert marker in page, marker


def test_kicker_stands_above_the_headline(tmp_path):
    page = _page(tmp_path, {"slides": [SLIDE]})
    assert page.index('<div class="kicker"><p>1. Market</p><p>Question: what is taken?</p></div>') < page.index('class="slide-headline"')


def test_unknown_role_and_blocks_without_body_raise(tmp_path):
    with pytest.raises(ValueError, match="Unknown block role"):
        _page(tmp_path, {"slides": [{"layout": "title-body", "content": {"headline": "H", "blocks": [{"role": "x"}]}}]})
    with pytest.raises(ValueError, match="has no body for blocks"):
        _page(tmp_path, {"slides": [{"layout": "title-media", "content": {"headline": "H", "media_url": "a.png", "blocks": []}}]})


def test_lang_stylesheets_cover_menu_numbers_and_touch_nav(tmp_path):
    page = _page(tmp_path, {"lang": "ru", "menu": "numbers", "stylesheets": ["https://fonts.example/css"],
                            "slides": [{"title": "Cover", "layout": "cover", "content": {"headline": "Deck", "body": "<p>6 Nov</p>"}}]})
    assert '<html lang="ru">' in page and '<link rel="stylesheet" href="https://fonts.example/css">' in page
    assert '<section class="slide slide--cover">' in page
    assert 'title="Cover">1</a>' in page
    assert 'data-deck-step="1"' in page


def test_default_menu_keeps_titles(tmp_path):
    assert 'title="S">S</a>' in _page(tmp_path, {"slides": [SLIDE]})


def test_profile_deck_css_is_appended(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    (prof / "tokens.css").write_text(":root{--color-bg:#fff}", encoding="utf-8")
    (prof / "deck.css").write_text(".deck .thesis{color:red}", encoding="utf-8")
    asm.assemble_deck({"title": "D", "slides": [SLIDE]}, prof, tmp_path / "out")
    assert ".deck .thesis{color:red}" in (tmp_path / "out" / "profile.css").read_text(encoding="utf-8")


@pytest.mark.parametrize("profile,palette", PROFILE_PALETTES)
def test_role_deck_assembles_in_every_profile(tmp_path, profile, palette):
    out = tmp_path / "out"
    asm.assemble_deck({"title": "D", "slides": [SLIDE]}, asm.PROFILES_DIR / profile, out, palette=palette)
    assert '<div class="thesis">' in (out / "index.html").read_text(encoding="utf-8")
