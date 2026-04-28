import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "h2t-creative"))

import pytest
import assembler


# --- interpolate ---

def test_interpolate_substitutes_field():
    result = assembler.interpolate("Hello {{ name }}", {"name": "World"})
    assert result == "Hello World"


def test_interpolate_html_escapes_by_default():
    result = assembler.interpolate("{{ val }}", {"val": "<script>alert(1)</script>"})
    assert result == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_interpolate_safe_skips_escape():
    result = assembler.interpolate("{{ val | safe }}", {"val": "<b>bold</b>"})
    assert result == "<b>bold</b>"


def test_interpolate_unknown_placeholder_raises():
    with pytest.raises(ValueError, match="unknown_field"):
        assembler.interpolate("{{ unknown_field }}", {})


# --- validate_section_content ---

def test_validate_section_content_unknown_field_raises():
    manifest = {"component": "hero", "fields": {"headline": {"type": "text", "required": True}}}
    section = {"component": "hero", "content": {"headline": "Hi", "extra": "bad"}}
    with pytest.raises(ValueError, match="unknown field 'extra'"):
        assembler.validate_section_content(section, manifest)


def test_validate_section_content_missing_required_raises():
    manifest = {"component": "hero", "fields": {"headline": {"type": "text", "required": True}}}
    section = {"component": "hero", "content": {}}
    with pytest.raises(ValueError, match="required field 'headline'"):
        assembler.validate_section_content(section, manifest)


def test_validate_section_content_optional_field_passes():
    manifest = {
        "component": "hero",
        "fields": {
            "headline": {"type": "text", "required": True},
            "subline": {"type": "text", "required": False, "default": ""},
        },
    }
    section = {"component": "hero", "content": {"headline": "Hi"}}
    assembler.validate_section_content(section, manifest)  # must not raise


# --- landing ---

def _make_minimal_profile(tmp_path: Path):
    """Creates a minimal profile with hero component for testing."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "reset.css").write_text("/* reset */")
    (base_dir / "grid.css").write_text("/* grid */")
    (base_dir / "typography.css").write_text("/* type */")
    (base_dir / "animations.css").write_text("/* anim */")

    profile_dir = tmp_path / "profiles" / "test-profile"
    (profile_dir / "components" / "hero").mkdir(parents=True)
    (profile_dir / "tokens.css").write_text(":root { --color-bg: #fff; }")
    (profile_dir / "components" / "hero" / "manifest.yaml").write_text(
        "component: hero\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  subline:\n    type: text\n    required: false\n    default: ''\n"
    )
    (profile_dir / "components" / "hero" / "hero.html").write_text(
        '<section class="hero"><h1>{{ headline }}</h1><p>{{ subline }}</p></section>'
    )
    (profile_dir / "components" / "hero" / "hero.css").write_text(".hero { color: red; }")
    return profile_dir, base_dir


def test_assemble_landing_creates_dist_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "Test Page",
        "sections": [{"component": "hero", "content": {"headline": "Hello"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "base.css").exists()
    assert (out_dir / "profile.css").exists()
    assert "fx.js" not in [f.name for f in out_dir.iterdir()]


def test_assemble_landing_interpolates_content(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "My Page",
        "sections": [{"component": "hero", "content": {"headline": "Welcome <World>"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    html_content = (out_dir / "index.html").read_text()
    assert "Welcome &lt;World&gt;" in html_content
    assert "My Page" in html_content


def test_assemble_landing_profile_css_contains_tokens_and_component(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "title": "T",
        "sections": [{"component": "hero", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    profile_css = (out_dir / "profile.css").read_text()
    assert "--color-bg" in profile_css
    assert ".hero" in profile_css


def test_assemble_landing_no_fx_if_fx_dir_absent(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert "bg-canvas" not in content
    assert not (out_dir / "fx.js").exists()


# --- deck ---

def test_assemble_deck_creates_dist_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "My Deck",
        "slides": [
            {"title": "Intro", "layout": "title-only", "content": {"headline": "Start"}},
            {"title": "Content", "layout": "title-body", "content": {"headline": "Details", "body": "text"}},
        ],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "base.css").exists()
    assert (out_dir / "profile.css").exists()


def test_assemble_deck_contains_slides_and_menu(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "Deck",
        "slides": [
            {"title": "One", "layout": "title-only", "content": {"headline": "Slide One"}},
            {"title": "Two", "layout": "title-only", "content": {"headline": "Slide Two"}},
        ],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert 'class="slide"' in content
    assert "slide-menu" in content
    assert "#slide-1" in content
    assert "#slide-2" in content
    assert "Slide One" in content
    assert "ArrowRight" in content


def test_assemble_deck_speaker_note_as_html_comment(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "D",
        "slides": [{"title": "S1", "layout": "title-only", "content": {
            "headline": "Hi", "note": "Remember to pause here"
        }}],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
    content = (out_dir / "index.html").read_text()
    assert "<!-- SPEAKER NOTE:" in content
    assert "Remember to pause here" in content


def test_schema_cross_contamination_landing_with_slides_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "slides": []}
    out_dir = tmp_path / "dist"
    with pytest.raises(SystemExit):
        assembler.main_assemble("landing", recipe, profile_dir, out_dir, base_dir=base_dir)


def test_schema_cross_contamination_deck_with_sections_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "deck", "title": "T", "sections": []}
    out_dir = tmp_path / "dist"
    with pytest.raises(SystemExit):
        assembler.main_assemble("deck", recipe, profile_dir, out_dir, base_dir=base_dir)


def test_deck_unknown_layout_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "D",
        "slides": [{"title": "S", "layout": "bad-layout", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    with pytest.raises(ValueError, match="Unknown deck layout"):
        assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)


# --- fx ---

def test_fx_present_injects_canvas(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    fx_dir = profile_dir / "fx"
    fx_dir.mkdir()
    (fx_dir / "background.js").write_text("export function init(c){} export function destroy(){}")
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert 'id="bg-canvas"' in content
    assert (out_dir / "fx.js").exists()


# --- dry_run ---

def test_dry_run_does_not_write_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.dry_run(recipe, "landing", profile_dir, out_dir)

    assert not out_dir.exists()


def test_dry_run_prints_would_create(tmp_path, capsys):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": []}
    out_dir = tmp_path / "dist"
    assembler.dry_run(recipe, "landing", profile_dir, out_dir)

    captured = capsys.readouterr()
    assert "index.html" in captured.out
    assert "base.css" in captured.out
    assert "profile.css" in captured.out


# --- palette support ---

def _make_palette_profile(tmp_path: Path):
    """Profile with palettes/ directory — new schema."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    for f in ["reset.css", "grid.css", "typography.css", "animations.css"]:
        (base_dir / f).write_text(f"/* {f} */")

    profile_dir = tmp_path / "profiles" / "test-palette"
    (profile_dir / "components" / "hero").mkdir(parents=True)
    (profile_dir / "palettes").mkdir()
    (profile_dir / "tokens.css").write_text(":root { --font-body: sans-serif; }")
    (profile_dir / "palettes" / "default.css").write_text(
        ":root { --color-bg: #fff; --color-fg: #000; --color-accent: #00f; }"
    )
    (profile_dir / "palettes" / "blue.css").write_text(
        ":root { --color-bg: #001; --color-fg: #aaf; --color-accent: #44f; }"
    )
    (profile_dir / "components" / "hero" / "manifest.yaml").write_text(
        "component: hero\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  subline:\n    type: text\n    required: false\n    default: ''\n"
    )
    (profile_dir / "components" / "hero" / "hero.html").write_text(
        '<section class="hero"><h1>{{ headline }}</h1></section>'
    )
    (profile_dir / "components" / "hero" / "hero.css").write_text(
        ".hero { color: var(--color-fg); }"
    )
    return profile_dir, base_dir


def test_palette_default_loads_palette_file(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    css = assembler._build_profile_css(profile_dir, [], palette="default")
    assert "--font-body" in css
    assert "--color-bg: #fff" in css
    assert "--color-bg: #001" not in css


def test_palette_blue_loads_blue_file(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    css = assembler._build_profile_css(profile_dir, [], palette="blue")
    assert "--color-bg: #001" in css
    assert "--color-bg: #fff" not in css


def test_palette_unknown_raises_with_available_list(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    with pytest.raises(ValueError, match="Palette 'purple' not found"):
        assembler._build_profile_css(profile_dir, [], palette="purple")


def test_legacy_profile_no_palettes_dir_falls_back(tmp_path):
    profile_dir, _ = _make_minimal_profile(tmp_path)
    # _make_minimal_profile has no palettes/ dir — legacy fallback
    css = assembler._build_profile_css(profile_dir, [])
    assert "--color-bg" in css


def test_assemble_landing_with_blue_palette(tmp_path):
    profile_dir, base_dir = _make_palette_profile(tmp_path)
    recipe = {
        "type": "landing", "title": "T", "palette": "blue",
        "sections": [{"component": "hero", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir, palette="blue")
    assert "--color-bg: #001" in (out_dir / "profile.css").read_text()


def test_assemble_deck_uses_build_profile_css_not_raw_tokens(tmp_path):
    """Deck must use _build_profile_css — not read tokens.css directly."""
    profile_dir, base_dir = _make_palette_profile(tmp_path)
    recipe = {
        "type": "deck", "title": "D",
        "slides": [{"title": "S", "layout": "title-only", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir, palette="blue")
    css = (out_dir / "profile.css").read_text()
    assert "--color-bg: #001" in css
    assert "--font-body" in css
