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


# --- deck-form switch (R2a T1) ---

def test_is_deck_form_profile_false_when_no_deck_dir(tmp_path):
    """Legacy profile (no deck/ subdir) is NOT deck-form."""
    profile_dir, _ = _make_minimal_profile(tmp_path)
    assert assembler._is_deck_form_profile(profile_dir) is False


def test_is_deck_form_profile_false_when_deck_dir_lacks_tokens(tmp_path):
    """deck/ subdir alone is not enough; deck/tokens.css is the marker."""
    profile_dir, _ = _make_minimal_profile(tmp_path)
    (profile_dir / "deck").mkdir()
    assert assembler._is_deck_form_profile(profile_dir) is False


def test_is_deck_form_profile_true_when_deck_tokens_present(tmp_path):
    """Profile with deck/tokens.css IS deck-form."""
    profile_dir, _ = _make_minimal_profile(tmp_path)
    deck_dir = profile_dir / "deck"
    deck_dir.mkdir()
    (deck_dir / "tokens.css").write_text(":root { --bg: #0d1117; }")
    assert assembler._is_deck_form_profile(profile_dir) is True


def test_assemble_deck_routes_legacy_when_no_deck_dir(tmp_path):
    """Legacy profiles continue to produce multi-file output with slide-menu."""
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "Routing Test",
        "slides": [{"title": "S1", "layout": "title-only", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
    # Legacy path side effects:
    assert (out_dir / "index.html").exists()
    assert (out_dir / "base.css").exists()
    assert (out_dir / "profile.css").exists()
    content = (out_dir / "index.html").read_text()
    assert "slide-menu" in content


def test_assemble_deck_routes_form_v2_when_deck_dir_exists(tmp_path):
    """Deck-form profiles route to form-v2 path. Bare-minimum deck/ setup (only tokens.css,
    no slides/layouts) routes to form-v2 and surfaces a layout-not-found error specific to
    the new path — proves the dispatcher reaches form-v2 rather than legacy."""
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    deck_dir = profile_dir / "deck"
    deck_dir.mkdir()
    (deck_dir / "tokens.css").write_text(":root { --bg: #0d1117; }")
    recipe = {
        "type": "deck",
        "title": "Routing Test",
        "slides": [{"title": "S1", "layout": "title", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "out"
    # Form-v2-specific error message (legacy path would say "Unknown deck layout"):
    with pytest.raises(ValueError, match="not found in test-profile/deck/slides"):
        assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)


# --- deck-form rendering helpers (R2a T2) ---

# _render_stats

def test_render_stats_basic_stat_box():
    stats = [{"number": "73%", "label": "context switching every single day"}]
    out = assembler._render_stats(stats)
    assert '<div class="stat-row">' in out
    assert '<div class="stat-box" data-index="01">' in out
    assert '<div class="stat-number">73%</div>' in out
    assert '<div class="stat-label">context switching every single day</div>' in out


def test_render_stats_default_index_is_zero_padded_position():
    stats = [
        {"number": "1", "label": "L"},
        {"number": "2", "label": "L"},
    ]
    out = assembler._render_stats(stats)
    assert 'data-index="01"' in out
    assert 'data-index="02"' in out


def test_render_stats_explicit_index_overrides_default():
    stats = [{"number": "1", "label": "L", "index": "AA"}]
    out = assembler._render_stats(stats)
    assert 'data-index="AA"' in out


def test_render_stats_escapes_plain_label():
    stats = [{"number": "1", "label": "<b>raw</b>"}]
    out = assembler._render_stats(stats)
    assert "&lt;b&gt;raw&lt;/b&gt;" in out
    assert "<b>raw</b>" not in out


def test_render_stats_label_html_kept_raw():
    stats = [{"number": "1", "label_html": "first<br>second"}]
    out = assembler._render_stats(stats)
    assert "first<br>second" in out
    assert "first&lt;br&gt;second" not in out


def test_render_stats_escapes_number():
    stats = [{"number": "<x>", "label": "L"}]
    out = assembler._render_stats(stats)
    assert "&lt;x&gt;" in out
    assert "<x>" not in out.replace("&lt;x&gt;", "")


def test_render_stats_variant_stat_with_color_class():
    stats = [{"number": "build", "label": "session", "variant": "stat", "number_class": "accent"}]
    out = assembler._render_stats(stats)
    assert '<div class="stat">' in out
    assert '<div class="num accent">build</div>' in out
    assert '<div class="label">session</div>' in out
    assert "stat-box" not in out


def test_render_stats_variant_stat_without_color_class():
    stats = [{"number": "1", "label": "L", "variant": "stat"}]
    out = assembler._render_stats(stats)
    assert '<div class="num">1</div>' in out


def test_render_stats_unknown_variant_raises():
    with pytest.raises(ValueError, match="Unknown stat variant"):
        assembler._render_stats([{"number": "1", "label": "L", "variant": "bogus"}])


# _render_cards

def test_render_cards_card_row_variant():
    cards = [
        {"icon": "01 · rules", "title": "CLAUDE.md", "desc": "Persistent instructions.", "color": "var(--accent)"},
        {"icon": "02 · actions", "title": "Skills", "desc": "Reusable templates.", "color": "var(--accent2)"},
    ]
    out = assembler._render_cards(cards, variant="card-row")
    assert '<div class="card-row">' in out
    assert 'style="--card-color: var(--accent);"' in out
    assert 'style="--card-color: var(--accent2);"' in out
    assert '<div class="card-icon">01 · rules</div>' in out
    assert '<div class="card-title">CLAUDE.md</div>' in out
    assert '<div class="card-desc">Persistent instructions.</div>' in out


def test_render_cards_card_row_desc_html_raw():
    cards = [{"icon": "I", "title": "T", "desc_html": "<em>emphasis</em>"}]
    out = assembler._render_cards(cards, variant="card-row")
    assert "<em>emphasis</em>" in out
    assert "&lt;em&gt;" not in out


def test_render_cards_card_row_no_color_omits_inline_style():
    cards = [{"icon": "I", "title": "T", "desc": "D"}]
    out = assembler._render_cards(cards, variant="card-row")
    assert "--card-color" not in out


def test_render_cards_grid_variant_with_items_list():
    cards = [
        {"tag": "SESSION 1", "title": "Установка", "items": ["one", "two"]},
        {"tag": "SESSION 2", "tag_class": "amber", "title": "Контекст", "items": ["alpha"]},
    ]
    out = assembler._render_cards(cards, variant="cards")
    assert '<div class="cards">' in out
    assert '<span class="tag">SESSION 1</span>' in out
    assert '<span class="tag amber">SESSION 2</span>' in out
    assert '<h3>Установка</h3>' in out
    assert '<li>one</li>' in out
    assert '<li>two</li>' in out
    assert '<li>alpha</li>' in out


def test_render_cards_grid_items_list_escapes_each_item():
    cards = [{"tag": "T", "title": "X", "items": ["<b>plain</b>"]}]
    out = assembler._render_cards(cards, variant="cards")
    assert "<li>&lt;b&gt;plain&lt;/b&gt;</li>" in out


def test_render_cards_grid_items_html_kept_raw():
    cards = [{"tag": "T", "title": "X", "items_html": '<li class="x">raw</li>'}]
    out = assembler._render_cards(cards, variant="cards")
    assert '<li class="x">raw</li>' in out


def test_render_cards_unknown_variant_raises():
    with pytest.raises(ValueError, match="Unknown cards variant"):
        assembler._render_cards([{"icon": "I", "title": "T"}], variant="bogus")


# _render_layers

def test_render_layers_with_preset_class():
    layers = [
        {"num": "01", "name": "Physical", "desc": "hardware", "preset": "l1"},
        {"num": "02", "name": "Interface", "desc": "IDE", "preset": "l2"},
    ]
    out = assembler._render_layers(layers)
    assert '<div class="layers">' in out
    assert '<div class="layer l1">' in out
    assert '<div class="layer l2">' in out
    assert '<div class="layer-num">01</div>' in out
    assert '<div class="layer-name">Physical</div>' in out
    assert '<div class="layer-desc">hardware</div>' in out


def test_render_layers_with_inline_color():
    layers = [{"num": "01", "name": "X", "desc": "Y", "color": "#cc6677"}]
    out = assembler._render_layers(layers)
    assert 'style="--layer-color: #cc6677;"' in out
    # Should not also add a preset class:
    assert '<div class="layer l' not in out


def test_render_layers_color_overrides_preset_when_both_set():
    layers = [{"num": "1", "name": "N", "desc": "D", "color": "#abc", "preset": "l1"}]
    out = assembler._render_layers(layers)
    assert "#abc" in out
    # Preset class should be dropped when color is provided:
    assert "layer l1" not in out


def test_render_layers_desc_html_raw():
    layers = [{"num": "1", "name": "N", "desc_html": "<em>text</em>"}]
    out = assembler._render_layers(layers)
    assert "<em>text</em>" in out
    assert "&lt;em&gt;" not in out


# _render_table

def test_render_table_basic_structure():
    out = assembler._render_table(["Variant", "Volume", "Logic"], [["A", "2", "first"], ["B", "4", "second"]])
    assert "<table>" in out
    assert "<thead>" in out
    assert "<tbody>" in out
    assert "<th>Variant</th>" in out
    assert "<th>Volume</th>" in out
    assert "<th>Logic</th>" in out
    assert "<td>A</td>" in out
    assert "<td>4</td>" in out
    assert '<p class="meta-note">' not in out


def test_render_table_preserves_html_in_cells():
    """CRITICAL: cells contain raw HTML by recipe convention. Without this, validation
    recipe table cells like '<span class="accent">A</span>' render as escaped text."""
    headers = ["X", "Y"]
    rows = [['<span class="accent">A · Narrow focus</span>', '<span class="mono">2</span>']]
    out = assembler._render_table(headers, rows)
    assert '<td><span class="accent">A · Narrow focus</span></td>' in out
    assert '<td><span class="mono">2</span></td>' in out
    # Must NOT be escaped:
    assert "&lt;span" not in out


def test_render_table_escapes_plain_text_headers():
    """Headers are plain text per recipe convention — escape special chars."""
    out = assembler._render_table(["A < B", "C & D"], [["1", "2"]])
    assert "<th>A &lt; B</th>" in out
    assert "<th>C &amp; D</th>" in out


def test_render_table_with_note_appends_meta_after_table():
    out = assembler._render_table(["H"], [["v"]], note="See discussion.")
    assert "</table>" in out
    note_pos = out.find('<p class="meta-note">')
    table_end = out.find("</table>")
    assert table_end > 0
    assert note_pos > table_end
    assert "See discussion." in out


def test_render_table_note_escaped():
    out = assembler._render_table(["H"], [["v"]], note="<b>important</b>")
    assert "&lt;b&gt;important&lt;/b&gt;" in out
    assert "<b>important</b>" not in out


def test_render_table_no_note_omits_meta():
    out = assembler._render_table(["H"], [["v"]])
    assert '<p class="meta-note">' not in out


# _render_table — T15.5 dual-representation contract


def test_render_table_emits_both_desktop_and_mobile_blocks():
    """Output must carry both representations; CSS toggles which is visible."""
    out = assembler._render_table(
        ["Variant", "Volume", "Logic"],
        [["A", "2", "first"], ["B", "4", "second"]],
    )
    assert '<div class="table-desktop">' in out
    assert '<div class="table-mobile">' in out
    # Desktop wrapper still contains the original <table>
    desktop_start = out.find('<div class="table-desktop">')
    desktop_end = out.find('</div>', desktop_start)
    desktop_block = out[desktop_start:desktop_end + len('</div>')]
    assert "<table>" in desktop_block and "</table>" in desktop_block


def test_render_table_mobile_block_emits_one_card_per_row():
    out = assembler._render_table(
        ["Variant", "Volume", "Logic"],
        [["A", "2", "first"], ["B", "4", "second"], ["C", "6", "third"]],
    )
    mobile_start = out.find('<div class="table-mobile">')
    mobile_end = out.find('</div>', mobile_start) + len('</div>')
    # The outer <div class="table-mobile"> wraps the cards; find articles inside.
    assert out.count('<article class="table-card">') == 3


def test_render_table_first_cell_becomes_card_title():
    out = assembler._render_table(
        ["Variant", "Volume"],
        [["A · Narrow focus", "2 sessions"]],
    )
    assert '<article class="table-card"><h3>A · Narrow focus</h3>' in out


def test_render_table_first_cell_keeps_html_in_card_title():
    """Per existing recipe convention, cells are raw HTML — title cell included."""
    out = assembler._render_table(
        ["Variant", "Volume"],
        [['<span class="accent">A · Narrow focus</span>', "2 sessions"]],
    )
    assert (
        '<article class="table-card"><h3><span class="accent">'
        'A · Narrow focus</span></h3>' in out
    )
    assert "&lt;span" not in out


def test_render_table_remaining_cells_become_dt_dd_pairs():
    out = assembler._render_table(
        ["Variant", "Volume", "Logic"],
        [["A", "2 sessions", "Intro + first 2 sessions"]],
    )
    # Volume / Logic become <dt> labels (escaped from headers)
    assert "<dt>Volume</dt><dd>2 sessions</dd>" in out
    assert "<dt>Logic</dt><dd>Intro + first 2 sessions</dd>" in out
    # First column header (Variant) is NOT used as a dt — first cell is the h3.
    assert "<dt>Variant</dt>" not in out


def test_render_table_mobile_dl_keeps_html_in_dd():
    out = assembler._render_table(
        ["Variant", "Volume"],
        [["A", '<span class="mono">2 sessions</span>']],
    )
    assert '<dd><span class="mono">2 sessions</span></dd>' in out
    assert "&lt;span" not in out


def test_render_table_mobile_dt_escapes_plain_text_headers():
    """Headers are plain text (per existing convention) → escape special chars in <dt>."""
    out = assembler._render_table(
        ["Variant", "A < B"],
        [["x", "1"]],
    )
    assert "<dt>A &lt; B</dt>" in out


def test_render_table_preserves_all_content_across_representations():
    """Every cell value appears in both representations (no data loss)."""
    headers = ["Variant", "Volume", "Logic"]
    rows = [
        ['<span class="accent">A · Narrow focus</span>',
         '<span class="mono">2 sessions</span>',
         "Intro + first 2 sessions of one track."],
        ['<span class="accent2">B · Extended</span>',
         '<span class="mono">4 sessions</span>',
         "Intro + 2 WS from two tracks."],
    ]
    out = assembler._render_table(headers, rows)
    desktop_block = out[
        out.find('<div class="table-desktop">'):
        out.find('<div class="table-mobile">')
    ]
    mobile_block = out[out.find('<div class="table-mobile">'):]
    for row in rows:
        for cell in row:
            assert cell in desktop_block, f"missing cell in desktop: {cell!r}"
            assert cell in mobile_block, f"missing cell in mobile: {cell!r}"


def test_render_table_with_note_appends_meta_after_both_blocks():
    out = assembler._render_table(
        ["H"], [["v"]], note="See discussion."
    )
    note_pos = out.find('<p class="meta-note">')
    desktop_end = out.find('</div>', out.find('<div class="table-desktop">'))
    mobile_end = out.find('</div>', out.find('<div class="table-mobile">'))
    assert note_pos > desktop_end > 0
    assert note_pos > mobile_end > 0
    assert "See discussion." in out


def test_render_table_two_column_mobile_card_has_no_extra_dt_dd():
    """If the table has only 2 columns, each card should have exactly one
    <dt>/<dd> pair (the second column under the first as the title)."""
    out = assembler._render_table(
        ["Variant", "Volume"],
        [["A", "2 sessions"]],
    )
    assert out.count("<dt>") == 1
    assert out.count("<dd>") == 1


def test_render_table_single_column_mobile_card_has_no_dl():
    """Edge case: a 1-column table renders only a card title; <dl> is omitted."""
    out = assembler._render_table(["Variant"], [["A"]])
    assert '<article class="table-card"><h3>A</h3></article>' in out


# _render_bullets

def test_render_bullets_with_explicit_sym():
    out = assembler._render_bullets([{"text": "first", "sym": "-->"}])
    assert '<ul class="bullet-list">' in out
    # ">" is escaped in attribute value:
    assert '<li data-sym="--&gt;">first</li>' in out


def test_render_bullets_default_symbol_is_gt():
    out = assembler._render_bullets([{"text": "alpha"}, {"text": "beta"}])
    assert '<li data-sym="&gt;">alpha</li>' in out
    assert '<li data-sym="&gt;">beta</li>' in out


def test_render_bullets_text_html_raw():
    out = assembler._render_bullets([{"text_html": "<strong>raw</strong> text", "sym": "*"}])
    assert "<strong>raw</strong> text" in out
    assert "&lt;strong&gt;" not in out


def test_render_bullets_text_escaped():
    out = assembler._render_bullets([{"text": "5 < 10"}])
    assert "5 &lt; 10" in out
    assert "<li>5 < 10</li>" not in out


# --- deck-form pipeline (R2a T3) ---

def _make_deck_form_profile(tmp_path: Path, layouts=None):
    """Create a minimal deck-form profile fixture with deck/ subtree."""
    if layouts is None:
        layouts = ["title", "title-body"]
    profile_dir = tmp_path / "profiles" / "test-deck"
    deck_dir = profile_dir / "deck"
    deck_dir.mkdir(parents=True)
    (deck_dir / "tokens.css").write_text(
        ":root { --bg: #0d1117; --text: #e6edf3; --accent: #55aa88; }"
    )
    (deck_dir / "palettes").mkdir()
    (deck_dir / "palettes" / "default.css").write_text(
        ":root { --border: #30363d; }"
    )
    (deck_dir / "frame").mkdir()
    (deck_dir / "frame" / "frame.css").write_text(
        "#progress-bar { height: 3px; background: var(--accent); }"
    )
    (deck_dir / "js").mkdir()
    (deck_dir / "js" / "deck-nav.js").write_text(
        "(function(){document.addEventListener('keydown',function(e){"
        "if(e.key==='ArrowRight'){console.log('next');}});})();"
    )
    slides_root = deck_dir / "slides"
    slides_root.mkdir()
    for layout in layouts:
        layout_dir = slides_root / layout
        layout_dir.mkdir()
        (layout_dir / "manifest.yaml").write_text(
            f"component: {layout}\n"
            "fields:\n"
            "  headline:\n"
            "    type: text\n"
            "    required: true\n"
            "  eyebrow:\n"
            "    type: text\n"
            "    required: false\n"
            "    default: ''\n"
        )
        (layout_dir / f"{layout}.html").write_text(
            '<div class="slide-inner">'
            '<div class="eyebrow">{{ eyebrow }}</div>'
            '<h1>{{ headline }}</h1>'
            '</div>'
        )
        (layout_dir / f"{layout}.css").write_text(
            f".slide-{layout}-marker {{ color: red; }}"
        )
    (profile_dir / "profile.yaml").write_text(
        "web_fonts:\n"
        "  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap\n"
    )
    return profile_dir


# _load_slide_layout

def test_load_slide_layout_returns_template_and_manifest(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    template, manifest = assembler._load_slide_layout(profile_dir, "title")
    assert "{{ headline }}" in template
    assert manifest["component"] == "title"
    assert "headline" in manifest["fields"]


def test_load_slide_layout_unknown_layout_raises_with_available(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title", "title-body"])
    with pytest.raises(ValueError, match="not found"):
        assembler._load_slide_layout(profile_dir, "missing-layout")


def test_load_slide_layout_missing_html_raises(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    (profile_dir / "deck" / "slides" / "title" / "title.html").unlink()
    with pytest.raises(ValueError, match="title.html"):
        assembler._load_slide_layout(profile_dir, "title")


def test_load_slide_layout_missing_manifest_raises(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    (profile_dir / "deck" / "slides" / "title" / "manifest.yaml").unlink()
    with pytest.raises(ValueError, match="manifest.yaml"):
        assembler._load_slide_layout(profile_dir, "title")


# _build_deck_slide_html_v2

def test_build_deck_slide_html_v2_basic_section_wrapper(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title-body"])
    slide = {"layout": "title-body", "content": {"headline": "Hello", "eyebrow": "// section"}}
    out = assembler._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert '<section class="slide" data-index="0">' in out
    assert "<h1>Hello</h1>" in out
    assert '<div class="eyebrow">// section</div>' in out


def test_build_deck_slide_html_v2_applies_manifest_defaults(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title-body"])
    slide = {"layout": "title-body", "content": {"headline": "H"}}
    out = assembler._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert '<div class="eyebrow"></div>' in out


def test_build_deck_slide_html_v2_center_align_adds_class(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    slide = {"layout": "title", "align": "center", "content": {"headline": "H"}}
    out = assembler._build_deck_slide_html_v2(slide, profile_dir, index=2)
    assert '<section class="slide center" data-index="2">' in out


def test_build_deck_slide_html_v2_unknown_layout_raises(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    slide = {"layout": "missing", "content": {"headline": "H"}}
    with pytest.raises(ValueError, match="not found"):
        assembler._build_deck_slide_html_v2(slide, profile_dir, index=0)


def test_build_deck_slide_html_v2_wires_stats_helper(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title-body"])
    stats_dir = profile_dir / "deck" / "slides" / "stats"
    stats_dir.mkdir()
    (stats_dir / "manifest.yaml").write_text(
        "component: stats\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  stats_html:\n    type: html\n    required: false\n    default: ''\n"
    )
    (stats_dir / "stats.html").write_text(
        '<div class="slide-inner"><h2>{{ headline }}</h2>{{ stats_html | safe }}</div>'
    )
    (stats_dir / "stats.css").write_text(".stats-marker { color: blue; }")
    slide = {
        "layout": "stats",
        "content": {
            "headline": "Stats",
            "stats": [{"number": "73%", "label": "context"}],
        },
    }
    out = assembler._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert '<div class="stat-row">' in out
    assert '<div class="stat-number">73%</div>' in out


def test_build_deck_slide_html_v2_wires_table_helper(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    table_dir = profile_dir / "deck" / "slides" / "table"
    table_dir.mkdir()
    (table_dir / "manifest.yaml").write_text(
        "component: table\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  table_html:\n    type: html\n    required: false\n    default: ''\n"
    )
    (table_dir / "table.html").write_text(
        '<div class="slide-inner"><h2>{{ headline }}</h2>{{ table_html | safe }}</div>'
    )
    (table_dir / "table.css").write_text(".table-marker {}")
    slide = {
        "layout": "table",
        "content": {
            "headline": "Variants",
            "table_headers": ["A", "B"],
            "table_rows": [['<span class="accent">x</span>', "y"]],
            "note": "footnote",
        },
    }
    out = assembler._build_deck_slide_html_v2(slide, profile_dir, index=1)
    assert "<table>" in out
    assert '<td><span class="accent">x</span></td>' in out
    assert '<p class="meta-note">footnote</p>' in out


# _build_deck_css_inline

def test_build_deck_css_inline_concatenates_tokens_palette_frame(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title-body"])
    css = assembler._build_deck_css_inline(profile_dir, [], palette="default")
    assert "--bg: #0d1117" in css
    assert "--border: #30363d" in css
    assert "#progress-bar" in css


def test_build_deck_css_inline_dedupes_layout_css(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title", "title-body"])
    slides = [
        {"layout": "title", "content": {}},
        {"layout": "title-body", "content": {}},
        {"layout": "title", "content": {}},
        {"layout": "title-body", "content": {}},
    ]
    css = assembler._build_deck_css_inline(profile_dir, slides, palette="default")
    assert css.count(".slide-title-marker") == 1
    assert css.count(".slide-title-body-marker") == 1


def test_build_deck_css_inline_omits_layouts_not_in_slides(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title", "title-body"])
    slides = [{"layout": "title", "content": {}}]
    css = assembler._build_deck_css_inline(profile_dir, slides, palette="default")
    assert ".slide-title-marker" in css
    assert ".slide-title-body-marker" not in css


def test_build_deck_css_inline_unknown_palette_raises_with_available(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title"])
    with pytest.raises(ValueError, match="Deck palette 'missing' not found"):
        assembler._build_deck_css_inline(profile_dir, [], palette="missing")


# _build_deck_js_inline

def test_build_deck_js_inline_reads_nav_script(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    js = assembler._build_deck_js_inline(profile_dir)
    assert "addEventListener" in js
    assert "ArrowRight" in js


def test_build_deck_js_inline_missing_script_raises(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    (profile_dir / "deck" / "js" / "deck-nav.js").unlink()
    with pytest.raises(ValueError, match="deck-nav.js"):
        assembler._build_deck_js_inline(profile_dir)


# _assemble_deck_form_v2 — single-file output contract

def test_assemble_deck_form_v2_single_file_only(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title", "title-body"])
    recipe = {
        "title": "Test Deck",
        "slides": [
            {"layout": "title", "content": {"headline": "Slide 1"}},
            {"layout": "title-body", "content": {"headline": "Slide 2"}},
        ],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    files = sorted(p.name for p in out_dir.iterdir())
    assert files == ["index.html"], f"Expected only index.html, got: {files}"


def test_assemble_deck_form_v2_inlines_css_in_style_block(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<style>" in content
    assert "</style>" in content
    assert "--bg: #0d1117" in content
    assert "#progress-bar" in content


def test_assemble_deck_form_v2_inlines_js_in_script_block(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<script>" in content
    assert "addEventListener" in content


def test_assemble_deck_form_v2_no_script_src(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<script src=" not in content


def test_assemble_deck_form_v2_no_app_stylesheet_links(tmp_path):
    """All <link rel="stylesheet"> must point to fonts.googleapis.com only."""
    import re
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="base.css"' not in content
    assert 'href="profile.css"' not in content
    stylesheet_links = re.findall(
        r'<link[^>]*rel="stylesheet"[^>]*>', content
    )
    for link in stylesheet_links:
        assert "fonts.googleapis.com" in link, f"Non-fonts stylesheet: {link}"


def test_assemble_deck_form_v2_google_fonts_link_present(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" in content
    assert "fonts.gstatic.com" in content
    assert "JetBrains+Mono" in content


def test_assemble_deck_form_v2_frame_chrome_present(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {
        "title": "T",
        "slides": [
            {"layout": "title", "content": {"headline": "S1"}},
            {"layout": "title-body", "content": {"headline": "S2"}},
        ],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert '<div id="progress-bar">' in content
    assert '<div id="slide-counter">' in content
    assert '<span id="cnt-total">02</span>' in content
    assert '<div id="nav-hint">' in content
    assert "arrows / space / swipe" in content
    assert 'class="slide-menu"' not in content


def test_assemble_deck_form_v2_optional_nav_buttons_enabled(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {
        "title": "T",
        "nav_buttons": True,
        "slides": [{"layout": "title", "content": {"headline": "H"}}],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="btn-prev"' in content
    assert 'id="btn-next"' in content


def test_assemble_deck_form_v2_no_nav_buttons_by_default(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="btn-prev"' not in content
    assert 'id="btn-next"' not in content


def test_assemble_deck_form_v2_lang_from_recipe(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {
        "title": "T", "lang": "ru",
        "slides": [{"layout": "title", "content": {"headline": "H"}}],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert '<html lang="ru">' in content


def test_assemble_deck_form_v2_lang_default_en(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in content


def test_assemble_deck_form_v2_custom_nav_hint_text(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path)
    recipe = {
        "title": "T", "nav_hint_text": "← → / swipe",
        "slides": [{"layout": "title", "content": {"headline": "H"}}],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "← → / swipe" in content


def test_assemble_deck_form_v2_array_helpers_wired_end_to_end(tmp_path):
    """Stats slide passes manifest -> helper -> template -> output end-to-end."""
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title-body"])
    stats_dir = profile_dir / "deck" / "slides" / "stats"
    stats_dir.mkdir()
    (stats_dir / "manifest.yaml").write_text(
        "component: stats\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  stats_html:\n    type: html\n    required: false\n    default: ''\n"
    )
    (stats_dir / "stats.html").write_text(
        '<div class="slide-inner"><h2>{{ headline }}</h2>{{ stats_html | safe }}</div>'
    )
    (stats_dir / "stats.css").write_text(".stats-marker {}")
    recipe = {
        "title": "T",
        "slides": [{
            "layout": "stats",
            "content": {
                "headline": "Stats",
                "stats": [
                    {"number": "73%", "label": "context"},
                    {"number": "4.1h", "label": "lost"},
                ],
            },
        }],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert '<div class="stat-row">' in content
    assert '<div class="stat-number">73%</div>' in content
    assert '<div class="stat-number">4.1h</div>' in content


def test_assemble_deck_form_v2_slides_indexed_sequentially(tmp_path):
    profile_dir = _make_deck_form_profile(tmp_path, layouts=["title", "title-body"])
    recipe = {
        "title": "T",
        "slides": [
            {"layout": "title", "content": {"headline": "1"}},
            {"layout": "title-body", "content": {"headline": "2"}},
            {"layout": "title", "content": {"headline": "3"}},
        ],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-index="0"' in content
    assert 'data-index="1"' in content
    assert 'data-index="2"' in content


def test_assemble_deck_form_v2_css_braces_dont_break_template(tmp_path):
    """REGRESSION: CSS contains { and } chars; template assembly must preserve them verbatim."""
    profile_dir = _make_deck_form_profile(tmp_path)
    deck_css = profile_dir / "deck" / "tokens.css"
    deck_css.write_text(
        ":root { --bg: #0d1117; }\n"
        ".foo { color: red; } .bar { color: blue; }\n"
        "/* curly { in comment } */\n"
    )
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert ".foo { color: red; }" in content
    assert ".bar { color: blue; }" in content
    assert "/* curly { in comment } */" in content


def test_assemble_deck_form_v2_js_braces_dont_break_template(tmp_path):
    """REGRESSION: JS contains many { } chars; template assembly must preserve them verbatim."""
    profile_dir = _make_deck_form_profile(tmp_path)
    js_path = profile_dir / "deck" / "js" / "deck-nav.js"
    js_path.write_text(
        "(function(){ var x = {a: 1, b: 2}; if (x.a) { console.log('y'); } })();"
    )
    recipe = {"title": "T", "slides": [{"layout": "title", "content": {"headline": "H"}}]}
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir)
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "var x = {a: 1, b: 2}" in content
    assert "if (x.a) { console.log('y'); }" in content


def test_assemble_deck_legacy_path_still_works_after_t3(tmp_path):
    """Profile WITHOUT deck/ subdir keeps legacy multi-file output."""
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "T",
        "slides": [{"title": "S", "layout": "title-only", "content": {"headline": "H"}}],
    }
    out_dir = tmp_path / "out"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
    files = sorted(p.name for p in out_dir.iterdir())
    assert "index.html" in files
    assert "base.css" in files
    assert "profile.css" in files
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "slide-menu" in content
