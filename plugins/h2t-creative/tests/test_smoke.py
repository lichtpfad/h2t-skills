"""Smoke tests: every profile × palette assembles without error."""
from pathlib import Path

import assembler as asm
import pytest

# R1 profiles (h2t-graphs, h2t-mono) follow golden component contract with profile-specific
# hero/cta fields — see test_r1_legacy_fidelity.py for assembly tests.
PROFILES = {
    "h2t-default":   ["default"],
    "h2t-editorial": ["default", "night", "warm"],
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
    """Generic deck smoke for legacy multi-file profiles. Deck-form profiles (those with a
    `deck/` subdir) are covered by test_deck_smoke_form_v2_with_temp_fixture below — skipping
    them here keeps `_DECK_RECIPE`'s legacy layout vocabulary (`title-only`, `title-body`)
    from leaking into the form-v2 path. See plan §A.3 (R2a)."""
    profile_dir = asm.PROFILES_DIR / profile
    if asm._is_deck_form_profile(profile_dir):
        pytest.skip(
            f"{profile} is deck-form; covered by test_deck_smoke_form_v2_with_temp_fixture"
        )
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, profile_dir, out)
    assert (out / "index.html").exists()
    assert (out / "profile.css").exists()


def test_terminal_deck_smoke_with_validation_recipe(tmp_path):
    """End-to-end smoke for the real h2t-terminal validation deck (T9 §5.9).
    Complements `test_deck_smoke[h2t-terminal]` (which is correctly skipped
    because h2t-terminal is now deck-form). We assemble the recipe shipped at
    `profiles/h2t-terminal/validation/recipe-deck.yaml` and confirm a
    single-file `index.html` lands."""
    import yaml as _yaml

    profile_dir = asm.PROFILES_DIR / "h2t-terminal"
    recipe_path = profile_dir / "validation" / "recipe-deck.yaml"
    recipe = _yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    out = tmp_path / "out"
    asm.assemble_deck(
        recipe, profile_dir, out, palette=recipe.get("palette", "default")
    )
    files = sorted(p.name for p in out.iterdir())
    assert files == ["index.html"], f"Expected only index.html, got: {files}"


def test_deck_smoke_form_v2_with_temp_fixture(tmp_path):
    """Deck-form (form-v2) smoke. Uses a self-contained temp fixture so this does not
    depend on the rollout of any specific profile's deck/ tree (h2t-terminal lands in
    T4–T7). Verifies the dispatcher routes to form-v2 and produces single-file output."""
    profile_dir = tmp_path / "profile-form-v2-smoke"
    deck = profile_dir / "deck"
    deck.mkdir(parents=True)
    (deck / "tokens.css").write_text(":root { --bg: #0d1117; }")
    (deck / "palettes").mkdir()
    (deck / "palettes" / "default.css").write_text(":root { --border: #30363d; }")
    (deck / "frame").mkdir()
    (deck / "frame" / "frame.css").write_text("#progress-bar { height: 3px; }")
    (deck / "js").mkdir()
    (deck / "js" / "deck-nav.js").write_text(
        "(function(){document.addEventListener('keydown',function(e){});})();"
    )
    layout = deck / "slides" / "title"
    layout.mkdir(parents=True)
    (layout / "manifest.yaml").write_text(
        "component: title\nfields:\n  headline:\n    type: text\n    required: true\n"
    )
    (layout / "title.html").write_text(
        '<div class="slide-inner"><h1>{{ headline }}</h1></div>'
    )
    (layout / "title.css").write_text(".slide-title-marker {}")
    (profile_dir / "profile.yaml").write_text("web_fonts: []\n")

    recipe = {
        "title": "Form-v2 Smoke",
        "slides": [
            {"layout": "title", "content": {"headline": "S1"}},
            {"layout": "title", "content": {"headline": "S2"}},
        ],
    }
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out)
    files = sorted(p.name for p in out.iterdir())
    assert files == ["index.html"], f"Expected single-file, got: {files}"
    content = (out / "index.html").read_text(encoding="utf-8")
    assert "<style>" in content
    assert "<script>" in content
    assert 'class="slide-menu"' not in content
    assert '<div id="progress-bar">' in content


def test_shared_component_fallback(tmp_path):
    """Component from shared/ is used when not in profile."""
    comp_dir = asm.SHARED_DIR / "components" / "_test_shared_comp"
    comp_dir.mkdir(parents=True, exist_ok=True)
    try:
        (comp_dir / "manifest.yaml").write_text(
            "component: _test_shared_comp\nfields:\n  msg:\n    type: text\n    required: true\n",
            encoding="utf-8",
        )
        (comp_dir / "_test_shared_comp.html").write_text(
            "<div class='test'>{{ msg }}</div>", encoding="utf-8"
        )
        (comp_dir / "_test_shared_comp.css").write_text(".test {}", encoding="utf-8")

        recipe = {
            "title": "Shared Test",
            "sections": [
                {"component": "_test_shared_comp", "content": {"msg": "hello"}},
            ],
        }
        out = tmp_path / "out"
        asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", out)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "hello" in html
    finally:
        import shutil
        shutil.rmtree(comp_dir)


def test_shared_features_grid(tmp_path):
    recipe = {
        "title": "FG Test",
        "sections": [{
            "component": "features-grid",
            "content": {
                "item1_icon": "🔥", "item1_title": "A", "item1_body": "Body A",
                "item2_icon": "⚡", "item2_title": "B", "item2_body": "Body B",
                "item3_icon": "🎯", "item3_title": "C", "item3_body": "Body C",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Body A" in html
    assert "Body C" in html


def test_shared_stats(tmp_path):
    recipe = {
        "title": "Stats Test",
        "sections": [{
            "component": "stats",
            "content": {
                "stat1_value": "120+", "stat1_label": "Lessons",
                "stat2_value": "12h",  "stat2_label": "Runtime",
                "stat3_value": "2500+","stat3_label": "Students",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "120+" in html
    assert "Students" in html


def test_shared_testimonials(tmp_path):
    recipe = {
        "title": "Testimonials Test",
        "sections": [{
            "component": "testimonials",
            "content": {
                "quote": "Best course ever.",
                "author": "Jane Smith",
                "role": "Motion Designer",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Best course ever." in html
    assert "Jane Smith" in html


def test_shared_pricing(tmp_path):
    recipe = {
        "title": "Pricing Test",
        "sections": [{
            "component": "pricing",
            "content": {
                "plan_name": "Full Access",
                "price": "$149",
                "period": "one-time",
                "features": "<li>Lifetime access</li><li>All updates</li>",
                "cta_text": "Enrol Now",
                "cta_href": "https://example.com/checkout",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "$149" in html
    assert "Enrol Now" in html


def test_shared_faq(tmp_path):
    recipe = {
        "title": "FAQ Test",
        "sections": [{
            "component": "faq",
            "content": {
                "title": "FAQ",
                "body": "<div><dt>Q?</dt><dd>A.</dd></div>",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Q?" in html


def test_shared_logos(tmp_path):
    recipe = {
        "title": "Logos Test",
        "sections": [{
            "component": "logos",
            "content": {
                "logos": "<span>Acme</span><span>Corp</span>",
            },
        }],
    }
    asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Acme" in html


def test_css_cascade_order(tmp_path):
    """Shared CSS appears strictly BEFORE profile override CSS in profile.css."""
    import shutil

    shared_comp = asm.SHARED_DIR / "components" / "_test_cascade_comp"
    profile_comp = asm.PROFILES_DIR / "h2t-default" / "components" / "_test_cascade_comp"
    manifest_text = (
        "component: _test_cascade_comp\n"
        "fields:\n  x:\n    type: text\n    required: false\n    default: ''\n"
    )
    html_text = "<div>{{ x }}</div>"

    shared_comp.mkdir(parents=True, exist_ok=True)
    profile_comp.mkdir(parents=True, exist_ok=True)
    try:
        for d, marker in [(shared_comp, "SHARED_MARKER"), (profile_comp, "PROFILE_MARKER")]:
            (d / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
            (d / "_test_cascade_comp.html").write_text(html_text, encoding="utf-8")
            (d / "_test_cascade_comp.css").write_text(f"/* {marker} */", encoding="utf-8")

        recipe = {
            "title": "Cascade Test",
            "sections": [{"component": "_test_cascade_comp", "content": {}}],
        }
        out = tmp_path / "out"
        asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", out)
        css = (out / "profile.css").read_text(encoding="utf-8")
        assert "SHARED_MARKER" in css, "shared CSS missing from profile.css"
        assert "PROFILE_MARKER" in css, "profile override CSS missing from profile.css"
        assert css.index("SHARED_MARKER") < css.index("PROFILE_MARKER"), (
            "shared CSS must appear before profile override CSS"
        )
    finally:
        shutil.rmtree(shared_comp)
        shutil.rmtree(profile_comp)
