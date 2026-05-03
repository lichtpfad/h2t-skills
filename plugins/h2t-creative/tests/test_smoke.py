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
