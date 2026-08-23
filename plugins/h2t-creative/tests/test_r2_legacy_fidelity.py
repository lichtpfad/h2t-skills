"""R2 legacy fidelity contracts (h2t-creative R2a — h2t-terminal deck)."""
import re
import sys
from pathlib import Path

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PLUGIN_ROOT / "profiles"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
import assembler as asm  # noqa: E402


def _terminal_deck_dir() -> Path:
    return PROFILES_DIR / "h2t-terminal" / "deck"


def _terminal_layouts_dir() -> Path:
    return _terminal_deck_dir() / "slides"


# §5.3 canonical layout vocabulary
EXPECTED_LAYOUTS = [
    "title", "divider", "title-body", "stats", "cards", "layers",
    "split", "code", "table", "quote", "final",
]


# --- §5.2 Token contract (deck form) ---

def test_h2t_terminal_deck_tokens_css_exists():
    assert (_terminal_deck_dir() / "tokens.css").exists()


def test_h2t_terminal_deck_palette_default_css_exists():
    assert (_terminal_deck_dir() / "palettes" / "default.css").exists()


_EXPECTED_PALETTE_TOKENS = [
    ("--bg", "#0d1117"),
    ("--bg-light", "#161b22"),
    ("--bg-card", "#1c2129"),
    ("--text", "#e6edf3"),
    ("--text-dim", "#8b949e"),
    ("--accent", "#55aa88"),
    ("--accent2", "#d4a843"),
    ("--accent3", "#4488cc"),
    ("--danger", "#cc4444"),
    ("--highlight", "#9966cc"),
    ("--pop", "#ee6688"),
    ("--border", "#30363d"),
]


def test_h2t_terminal_deck_palette_default_declares_all_12_tokens():
    css = (_terminal_deck_dir() / "palettes" / "default.css").read_text(encoding="utf-8")
    for token, value in _EXPECTED_PALETTE_TOKENS:
        assert f"{token}: {value}" in css, f"Missing or wrong: {token}: {value}"


def test_h2t_terminal_deck_accent_is_muted_green_not_bright():
    """Deck uses muted #55aa88 per goldens — NOT the bright #00ff41 used by terminal landing."""
    css = (_terminal_deck_dir() / "palettes" / "default.css").read_text(encoding="utf-8")
    assert "--accent: #55aa88" in css
    assert "#00ff41" not in css


def test_h2t_terminal_deck_no_color_prefix_tokens():
    """Deck uses bare --bg/--text/--accent (NOT --color-bg/--color-text — those are landing form)."""
    deck = _terminal_deck_dir()
    for css_path in [
        deck / "tokens.css",
        deck / "palettes" / "default.css",
        deck / "frame" / "frame.css",
    ]:
        css = css_path.read_text(encoding="utf-8")
        decls = re.findall(r"--color-[a-z][a-z0-9-]*\s*:", css)
        assert decls == [], (
            f"{css_path.name} declares --color-* tokens (landing-form contract), found: {decls}"
        )


# --- §5.5 Frame contract ---

def test_h2t_terminal_deck_frame_css_exists():
    assert (_terminal_deck_dir() / "frame" / "frame.css").exists()


def test_h2t_terminal_deck_frame_has_progress_bar():
    css = (_terminal_deck_dir() / "frame" / "frame.css").read_text(encoding="utf-8")
    assert "#progress-bar" in css


def test_h2t_terminal_deck_frame_has_slide_counter():
    css = (_terminal_deck_dir() / "frame" / "frame.css").read_text(encoding="utf-8")
    assert "#slide-counter" in css


def test_h2t_terminal_deck_frame_has_nav_hint():
    css = (_terminal_deck_dir() / "frame" / "frame.css").read_text(encoding="utf-8")
    assert "#nav-hint" in css


def test_h2t_terminal_deck_has_scanlines_overlay():
    """Scanlines may live in tokens.css (body::after overlay) or frame.css. Check both."""
    deck = _terminal_deck_dir()
    combined = (
        (deck / "tokens.css").read_text(encoding="utf-8")
        + "\n"
        + (deck / "frame" / "frame.css").read_text(encoding="utf-8")
    )
    assert "body::after" in combined
    assert "repeating-linear-gradient" in combined


def test_h2t_terminal_deck_chrome_z_above_scanlines():
    """Frame chrome (progress/counter/nav-hint/nav-btn) must render ABOVE the scanline
    overlay. Goldens technically place chrome below scanlines — readable only because
    stripes are near-transparent. We correct that defensively (T4.1)."""
    deck = _terminal_deck_dir()
    # Strip CSS comments so z-index numbers in documentation text don't leak into the parse.
    comment_re = re.compile(r"/\*.*?\*/", re.DOTALL)
    tokens_css = comment_re.sub("", (deck / "tokens.css").read_text(encoding="utf-8"))
    frame_css = comment_re.sub("", (deck / "frame" / "frame.css").read_text(encoding="utf-8"))

    sc_match = re.search(
        r"body::after[^{]*\{[^}]*?z-index:\s*(\d+)",
        tokens_css,
        re.DOTALL,
    )
    assert sc_match, "tokens.css body::after must declare a z-index"
    scanline_z = int(sc_match.group(1))

    chrome_zs = [int(m) for m in re.findall(r"z-index:\s*(\d+)", frame_css)]
    assert chrome_zs, "frame.css must declare at least one z-index for chrome"
    assert min(chrome_zs) > scanline_z, (
        f"Frame chrome min z-index ({min(chrome_zs)}) must be > scanlines z-index "
        f"({scanline_z}); otherwise chrome renders below the overlay."
    )


# --- Forbidden patterns ---

def test_h2t_terminal_deck_no_crosshair_cursor():
    """Deck does not use crosshair cursor (unlike graphs/PFAD-style profiles)."""
    deck = _terminal_deck_dir()
    for css_path in [
        deck / "tokens.css",
        deck / "palettes" / "default.css",
        deck / "frame" / "frame.css",
    ]:
        css = css_path.read_text(encoding="utf-8")
        assert "cursor: crosshair" not in css, (
            f"{css_path.name}: cursor: crosshair forbidden in deck (terminal is mono-cursor)"
        )


# NOTE: `test_h2t_terminal_deck_no_mobile_reflow_rules` was withdrawn in T12.5/T14.
# The original blanket ban on `@media (max-width:` was incorrect; mobile rules are
# now required (Gate B). See `_mobile_block` / desktop-invariant tests in the T14
# contract block at the bottom of this file.


# --- Mono-font contract ---

def test_h2t_terminal_deck_tokens_declare_font_heading_and_body():
    css = (_terminal_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    assert "--font-heading:" in css
    assert "--font-body:" in css


def test_h2t_terminal_deck_uses_jetbrains_mono_chain():
    """All declared font tokens must lean on JetBrains Mono fallback chain — no serif/sans."""
    css = (_terminal_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    assert "JetBrains Mono" in css
    assert "monospace" in css
    # No serif fallback:
    assert "serif" not in css.lower(), "Deck typography must be monospace-only"


# --- §5.3 Slide layout coverage ---


def test_h2t_terminal_deck_layouts_dir_exists():
    assert _terminal_layouts_dir().is_dir()


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_dir_exists(layout):
    assert (_terminal_layouts_dir() / layout).is_dir(), (
        f"Missing layout dir: deck/slides/{layout}/"
    )


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_has_html(layout):
    assert (_terminal_layouts_dir() / layout / f"{layout}.html").exists()


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_has_css(layout):
    assert (_terminal_layouts_dir() / layout / f"{layout}.css").exists()


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_has_manifest(layout):
    assert (_terminal_layouts_dir() / layout / "manifest.yaml").exists()


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_manifest_parses(layout):
    manifest = yaml.safe_load(
        (_terminal_layouts_dir() / layout / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(manifest, dict)
    assert manifest.get("layout") == layout, (
        f"manifest.yaml `layout` must equal '{layout}', got {manifest.get('layout')!r}"
    )
    assert isinstance(manifest.get("fields", {}), dict)


def test_h2t_terminal_deck_layout_set_matches_expected():
    """No extra layouts; no missing layouts. Vocabulary is closed at 11."""
    actual = sorted(
        d.name for d in _terminal_layouts_dir().iterdir() if d.is_dir()
    )
    assert actual == sorted(EXPECTED_LAYOUTS), (
        f"Layout set mismatch: actual={actual}, expected={sorted(EXPECTED_LAYOUTS)}"
    )


# --- Forbidden patterns inside layout files ---

# Common emoji codepoint blocks (pictographs, dingbats, supplementals).
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF"   # Misc symbols & pictographs, supplemental, extended
    r"\U00002600-\U000027BF"    # Misc symbols + dingbats
    r"\U0001F000-\U0001F0FF"    # Mahjong, dominoes, playing cards
    r"]"
)


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_html_no_emoji(layout):
    html_text = (_terminal_layouts_dir() / layout / f"{layout}.html").read_text(
        encoding="utf-8"
    )
    found = _EMOJI_RE.findall(html_text)
    assert not found, f"{layout}.html contains emoji codepoints: {found}"


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_no_mermaid_refs(layout):
    layout_dir = _terminal_layouts_dir() / layout
    for path in layout_dir.iterdir():
        if path.suffix in {".html", ".css", ".yaml"}:
            text = path.read_text(encoding="utf-8").lower()
            assert "mermaid" not in text, (
                f"{path.relative_to(_terminal_layouts_dir())}: mermaid reference "
                f"forbidden — not used in either golden"
            )


# NOTE: `test_h2t_terminal_deck_layout_css_no_mobile_reflow` was withdrawn in T12.5/T14.
# Layout CSS is allowed to declare `@media (max-width: 480px)` blocks; the
# T14 contract enforces *what* mobile rules look like, not their absence.


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_no_crosshair_cursor(layout):
    layout_dir = _terminal_layouts_dir() / layout
    for path in layout_dir.iterdir():
        if path.suffix in {".html", ".css"}:
            text = path.read_text(encoding="utf-8")
            assert "cursor: crosshair" not in text, (
                f"{path.name}: cursor: crosshair forbidden in deck"
            )


# --- Render smoke per layout ---

# Minimal content per layout that satisfies required fields. Optional fields
# come from manifest defaults so smoke does not depend on validation recipe.
_LAYOUT_MIN_CONTENT = {
    "title":      {"headline": 'Hero <span class="accent">Headline</span>'},
    "divider":    {"headline": "Section Divider"},
    "title-body": {"headline": "H2 Headline", "body_html": "<p>body content</p>"},
    "stats":      {"headline": "Stats", "stats": [{"number": "1", "label": "x"}]},
    "cards":      {"headline": "Cards",
                   "cards": [{"icon": "01", "title": "T", "desc": "D"}]},
    "layers":     {"headline": "Layers",
                   "layers": [{"num": "01", "name": "L", "desc": "D"}]},
    "split":      {"headline": "Split",
                   "left_html": "<p>L</p>", "right_html": "<p>R</p>"},
    "code":       {"headline": "Code",
                   "code_html": '<span class="code-prompt">$</span>'},
    "table":      {"headline": "Table",
                   "table_headers": ["A", "B"], "table_rows": [["1", "2"]]},
    "quote":      {"headline": "Quote", "quote_html": "not a tool"},
    "final":      {"headline": "Final"},
}


@pytest.mark.parametrize("layout", EXPECTED_LAYOUTS)
def test_h2t_terminal_deck_layout_renders_smoke(layout):
    """Each layout assembles into a <section class='slide'> with the minimal content."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    slide = {"layout": layout, "content": _LAYOUT_MIN_CONTENT[layout]}
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert out.startswith('<section class="slide'), out[:80]
    assert out.endswith("</section>"), out[-80:]
    assert 'class="slide-inner' in out, (
        f"{layout}: rendered slide must contain a slide-inner wrapper"
    )


# --- T5.1: code layout contract (layout owns <pre>; recipe carries inner code only) ---


def test_h2t_terminal_deck_code_layout_emits_exactly_one_pre():
    """The code layout wraps `code_html` in exactly one <pre>. Recipe must NOT
    include an outer <pre> in `code_html` — only inner code lines / spans."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    slide = {
        "layout": "code",
        "content": {
            "headline": "Code",
            "code_html": (
                '<span class="code-prompt">$</span> '
                '<span class="code-cmd">mkdir</span> '
                '<span class="code-arg">~/.claude/skills</span>'
            ),
        },
    }
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert out.count("<pre>") == 1, (
        f"code layout must emit exactly one <pre>, got {out.count('<pre>')}: {out!r}"
    )
    assert out.count("</pre>") == 1


def test_h2t_terminal_deck_code_layout_no_nested_pre():
    """If a recipe author accidentally wraps `code_html` in <pre>, the assembler
    will produce a nested `<pre><pre>...` — guard the contract by asserting no
    nested-<pre> sequence appears in well-formed (contract-compliant) output."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    slide = {
        "layout": "code",
        "content": {
            "headline": "Code",
            "code_html": '<span class="code-prompt">$</span>',
        },
    }
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert "<pre><pre>" not in out
    assert "</pre></pre>" not in out


def test_h2t_terminal_deck_code_layout_renders_caption_raw_after_code_block():
    """`caption_html` (optional) renders as raw HTML positioned AFTER </div> of
    the .code-block, mirroring goldens (caption sits below the terminal box)."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    slide = {
        "layout": "code",
        "content": {
            "headline": "Code",
            "code_html": '<span class="code-prompt">$</span>',
            "caption_html": '<p class="caption">// initialize the workspace</p>',
        },
    }
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    out.rfind("</div>")
    caption_idx = out.find('<p class="caption">')
    assert caption_idx != -1, "caption_html must render when provided"
    assert "&lt;p" not in out, (
        "caption_html must be raw HTML (rendered via | safe), not escaped"
    )
    assert out.find("</pre>") < caption_idx, (
        "caption must appear AFTER the <pre> closes (i.e. below .code-block)"
    )


def test_h2t_terminal_deck_code_layout_caption_optional():
    """When `caption_html` is omitted, the layout still renders without error
    and produces no caption element."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    slide = {
        "layout": "code",
        "content": {
            "headline": "Code",
            "code_html": '<span class="code-prompt">$</span>',
        },
    }
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert 'class="caption"' not in out


# --- T6: deck-nav.js contract ---


def _terminal_deck_nav_path() -> Path:
    return _terminal_deck_dir() / "js" / "deck-nav.js"


def _terminal_deck_nav_text() -> str:
    return _terminal_deck_nav_path().read_text(encoding="utf-8")


def test_h2t_terminal_deck_nav_js_exists():
    assert _terminal_deck_nav_path().exists(), (
        "Expected profiles/h2t-terminal/deck/js/deck-nav.js"
    )


@pytest.mark.parametrize("key", [
    "ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp",
    "Enter", "Backspace", "Home", "End",
])
def test_h2t_terminal_deck_nav_js_binds_required_keys(key):
    js = _terminal_deck_nav_text()
    assert key in js, f"deck-nav.js must reference '{key}' key binding"


def test_h2t_terminal_deck_nav_js_binds_space_key():
    """Space is matched as the literal ' ' string in e.key."""
    js = _terminal_deck_nav_text()
    assert "case ' '" in js or "=== ' '" in js or "== ' '" in js, (
        "deck-nav.js must handle the Space key (e.key === ' ')"
    )


def test_h2t_terminal_deck_nav_js_listens_for_keydown():
    js = _terminal_deck_nav_text()
    assert "addEventListener('keydown'" in js or 'addEventListener("keydown"' in js


def test_h2t_terminal_deck_nav_js_has_touch_swipe():
    js = _terminal_deck_nav_text()
    assert "touchstart" in js, "deck-nav.js must register touchstart"
    assert "touchend" in js, "deck-nav.js must register touchend"
    # Swipe threshold > 40px per design-system
    assert "40" in js, "deck-nav.js must encode the >40px swipe threshold"


def test_h2t_terminal_deck_nav_js_updates_progress_and_counter():
    js = _terminal_deck_nav_text()
    assert "progress-bar" in js, "deck-nav.js must reference #progress-bar"
    assert "cnt-current" in js, "deck-nav.js must update #cnt-current"
    assert "cnt-total" in js, "deck-nav.js must update #cnt-total"


def test_h2t_terminal_deck_nav_js_zero_pads_counter():
    """Counter format is '01 / 07' style — zero-padded single digits."""
    js = _terminal_deck_nav_text()
    assert "padStart(2" in js, (
        "deck-nav.js must zero-pad slide-counter via String#padStart(2, '0')"
    )


def test_h2t_terminal_deck_nav_js_uses_merkazim_progress_formula():
    """Progress formula must be ((current+1)/total)*100 per design-system §Navigation —
    first slide shows >0% progress (more intuitive than the pos-sprint normalized form)."""
    js = _terminal_deck_nav_text()
    # Allow either spaced or compact JS, but require the (current+1)/total shape.
    assert re.search(r"\(\s*current\s*\+\s*1\s*\)\s*/\s*total", js), (
        "deck-nav.js must compute progress as ((current+1)/total)*100"
    )


def test_h2t_terminal_deck_nav_js_supports_optional_prev_next_buttons():
    """When recipe.nav_buttons is true, assembler renders #btn-prev / #btn-next.
    deck-nav.js must wire them up + maintain disabled state at edges."""
    js = _terminal_deck_nav_text()
    assert "btn-prev" in js, "deck-nav.js must reference #btn-prev"
    assert "btn-next" in js, "deck-nav.js must reference #btn-next"
    assert "disabled" in js, (
        "deck-nav.js must toggle a disabled state on edge buttons"
    )


def test_h2t_terminal_deck_nav_js_hash_sync():
    js = _terminal_deck_nav_text()
    assert "location.hash" in js, "deck-nav.js must read location.hash on init"
    assert "history.replaceState" in js, (
        "deck-nav.js must replaceState on slide change (hash sync)"
    )


def test_h2t_terminal_deck_nav_js_exposes_window_showSlide():
    """Screenshot tooling drives slides via window.showSlide(idx) for determinism —
    keyboard fallback is fragile across headless browsers."""
    js = _terminal_deck_nav_text()
    assert re.search(r"window\.showSlide\s*=", js), (
        "deck-nav.js must assign window.showSlide for T12 screenshot tooling"
    )


def test_h2t_terminal_deck_nav_js_no_external_refs():
    js = _terminal_deck_nav_text()
    assert "<script src" not in js
    # No ES module imports — entire script is inlined into <script>...</script>
    assert not re.search(r"\bimport\s+[^;]*\bfrom\b", js), (
        "deck-nav.js must not contain ES module imports"
    )
    assert "mermaid" not in js.lower()


def test_h2t_terminal_deck_nav_js_no_viewport_branching():
    """JS must not branch on viewport — mobile is CSS-only (T14 contract).
    Replaces the T6 `_no_mobile_reflow` check with an intent-based assertion:
    no `matchMedia`, no `innerWidth` reads, no embedded CSS-style `max-width`."""
    js = _terminal_deck_nav_text()
    assert "matchMedia" not in js, "deck-nav.js must not use window.matchMedia"
    assert "innerWidth" not in js, "deck-nav.js must not branch on window.innerWidth"
    assert not re.search(r"max-width:\s*\d+", js), (
        "deck-nav.js must not embed CSS-style `max-width:` queries"
    )


# --- T8: source dossier (references.yaml + reference screenshots) ---

REPO_ROOT = PLUGIN_ROOT.parents[1]


def _terminal_sources_dir() -> Path:
    return PROFILES_DIR / "h2t-terminal" / "sources"


def _terminal_references_path() -> Path:
    return _terminal_sources_dir() / "references.yaml"


def _terminal_screenshots_dir() -> Path:
    return _terminal_sources_dir() / "screenshots"


def _load_terminal_references() -> dict:
    return yaml.safe_load(_terminal_references_path().read_text(encoding="utf-8"))


def test_h2t_terminal_source_dossier_dir_exists():
    assert _terminal_sources_dir().is_dir()
    assert _terminal_screenshots_dir().is_dir()


def test_h2t_terminal_references_yaml_exists():
    assert _terminal_references_path().exists()


def test_h2t_terminal_references_yaml_parses():
    data = _load_terminal_references()
    assert isinstance(data, dict)
    assert isinstance(data.get("sources", []), list)


_REQUIRED_SOURCE_IDS = {
    "pos-sprint-terminal-example",
    "merkazim",
    "pos-sprint-deck-skill",
}


def test_h2t_terminal_references_yaml_links_all_three_goldens():
    data = _load_terminal_references()
    ids = {s.get("id") for s in data.get("sources", [])}
    missing = _REQUIRED_SOURCE_IDS - ids
    assert not missing, f"references.yaml missing source ids: {missing}; got {ids}"


def test_h2t_terminal_references_yaml_paths_exist():
    """Every `path` in references.yaml must point to a real file under
    docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/."""
    data = _load_terminal_references()
    for src in data.get("sources", []):
        rel_path = src.get("path")
        assert rel_path, f"source {src.get('id')!r} missing `path`"
        full = (REPO_ROOT / rel_path).resolve()
        assert full.exists(), (
            f"source {src.get('id')!r} path does not exist: {rel_path}"
        )


def test_h2t_terminal_reference_desktop_screenshot_exists():
    p = _terminal_screenshots_dir() / "reference-desktop.png"
    assert p.exists(), f"Missing {p}"
    assert p.stat().st_size > 1024, (
        f"reference-desktop.png is suspiciously small ({p.stat().st_size} bytes)"
    )


def test_h2t_terminal_reference_mobile_screenshot_exists():
    p = _terminal_screenshots_dir() / "reference-mobile.png"
    assert p.exists(), f"Missing {p}"
    assert p.stat().st_size > 1024, (
        f"reference-mobile.png is suspiciously small ({p.stat().st_size} bytes)"
    )


# Forbidden phrasing in dossier — these signal a stub recovered at session
# time rather than a static fidelity gate. Plan #92 makes mobile a
# baseline-only gate; the dossier must describe fixed snapshots only.
_DOSSIER_FORBIDDEN = [
    "live-only",
    "live only",
    "llm rebuild",
    "ai rebuild",
    "to be regenerated",
    "regenerate at runtime",
    "synthesized at build time",
]


def test_h2t_terminal_references_yaml_no_live_only_wording():
    text = _terminal_references_path().read_text(encoding="utf-8").lower()
    found = [phrase for phrase in _DOSSIER_FORBIDDEN if phrase in text]
    assert not found, (
        f"references.yaml contains forbidden 'live rebuild' wording: {found}"
    )


# --- T7: validation/recipe-deck.yaml contract ---


def _terminal_validation_recipe_path() -> Path:
    return PROFILES_DIR / "h2t-terminal" / "validation" / "recipe-deck.yaml"


def _load_validation_recipe() -> dict:
    return yaml.safe_load(
        _terminal_validation_recipe_path().read_text(encoding="utf-8")
    )


def test_h2t_terminal_validation_recipe_exists():
    assert _terminal_validation_recipe_path().exists(), (
        "Expected profiles/h2t-terminal/validation/recipe-deck.yaml"
    )


def test_h2t_terminal_validation_recipe_metadata():
    r = _load_validation_recipe()
    assert r.get("type") == "deck", f"recipe.type must be 'deck', got {r.get('type')!r}"
    assert r.get("profile") == "h2t-terminal"
    assert r.get("palette") == "default"
    assert r.get("lang") == "en"
    assert isinstance(r.get("title"), str) and r["title"].strip()
    assert r.get("nav_buttons") is False, (
        "nav_buttons must be False unless plan explicitly opts in"
    )


def test_h2t_terminal_validation_recipe_has_exactly_11_slides():
    r = _load_validation_recipe()
    slides = r.get("slides", [])
    assert len(slides) == 11, f"Expected 11 slides, got {len(slides)}"


def test_h2t_terminal_validation_recipe_covers_every_layout():
    r = _load_validation_recipe()
    actual = sorted(s["layout"] for s in r.get("slides", []))
    assert actual == sorted(EXPECTED_LAYOUTS), (
        f"Layout coverage mismatch: actual={actual}, expected={sorted(EXPECTED_LAYOUTS)}"
    )


def test_h2t_terminal_validation_recipe_no_duplicate_layouts():
    r = _load_validation_recipe()
    layouts = [s["layout"] for s in r.get("slides", [])]
    duplicates = [name for name in set(layouts) if layouts.count(name) > 1]
    assert not duplicates, f"Duplicate layouts in recipe: {duplicates}"


# Words / phrases that flag synthetic recovery-stub copy. The recipe must lift
# content from goldens / approved plan; placeholder copy fails the gate.
_SYNTHETIC_COPY_FORBIDDEN = [
    "lorem ipsum",
    "todo:",
    "tbd",
    "placeholder",
    "fixme",
    "xxx ",
    "synthetic",
    "r2 recovery",
    "recovery copy",
    "stub content",
    "sample text",
    "test slide content",
]


def test_h2t_terminal_validation_recipe_no_synthetic_copy():
    raw = _terminal_validation_recipe_path().read_text(encoding="utf-8").lower()
    found = [phrase for phrase in _SYNTHETIC_COPY_FORBIDDEN if phrase in raw]
    assert not found, (
        f"Validation recipe contains synthetic placeholder copy: {found}. "
        f"All slide content must come from goldens / approved plan §4."
    )


def test_h2t_terminal_validation_recipe_code_html_has_no_pre():
    """Per T5.1: layout owns the <pre> wrapper; recipe carries inner code only."""
    r = _load_validation_recipe()
    code_slide = next(
        s for s in r["slides"] if s["layout"] == "code"
    )
    code_html = code_slide["content"]["code_html"]
    assert "<pre>" not in code_html and "</pre>" not in code_html, (
        f"code_html in validation recipe must not contain outer <pre>; "
        f"layout owns the wrapper. Got: {code_html!r}"
    )


def test_h2t_terminal_validation_recipe_assembles(tmp_path):
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = _load_validation_recipe()
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out, palette=recipe.get("palette", "default"))
    assert (out / "index.html").exists()


def test_h2t_terminal_validation_recipe_output_single_file(tmp_path):
    """Single-file contract: out_dir contains only index.html (no base.css, no
    profile.css, no fx.js, no separate deck-nav.js)."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = _load_validation_recipe()
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out, palette=recipe.get("palette", "default"))
    files = sorted(p.name for p in out.iterdir())
    assert files == ["index.html"], f"Expected only index.html, got: {files}"


def test_h2t_terminal_validation_recipe_output_inlines_css_and_js(tmp_path):
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = _load_validation_recipe()
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out, palette=recipe.get("palette", "default"))
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert "<style>" in html_text and "</style>" in html_text
    assert "<script>" in html_text and "</script>" in html_text
    # Sentinel rule from inlined CSS — should land verbatim
    assert "--bg: #0d1117" in html_text
    # Sentinel from inlined JS
    assert "addEventListener('keydown'" in html_text


def test_h2t_terminal_validation_recipe_output_contains_all_11_sections(tmp_path):
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = _load_validation_recipe()
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out, palette=recipe.get("palette", "default"))
    html_text = (out / "index.html").read_text(encoding="utf-8")
    section_count = len(re.findall(r'<section class="slide[^"]*" data-index=', html_text))
    assert section_count == 11, (
        f"Expected 11 <section class='slide ...' data-index=...> in output, "
        f"got {section_count}"
    )
    # And no legacy slide-menu sidebar from the multi-file path
    assert 'class="slide-menu"' not in html_text
    # showSlide signature inlined exactly once
    assert html_text.count("window.showSlide = showSlide") == 1


def test_h2t_terminal_deck_nav_js_appears_inlined_in_form_v2_output(tmp_path):
    """Assembled deck-form output inlines deck-nav.js once inside <script>."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = {
        "title": "T6 Smoke",
        "slides": [
            {"layout": "title", "content": {"headline": "S1"}},
            {"layout": "final", "content": {"headline": "S2"}},
        ],
    }
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out)
    html_text = (out / "index.html").read_text(encoding="utf-8")
    _terminal_deck_nav_text().strip()
    # Pick a stable signature line from the JS to verify inlining occurred
    # exactly once (not zero, not duplicated).
    signature = "window.showSlide"
    assert html_text.count(signature) == 1, (
        f"window.showSlide signature must appear exactly once in inlined output; "
        f"got {html_text.count(signature)}"
    )
    # And no <script src=> appears anywhere
    assert "<script src" not in html_text


# --- T9: assembled-output guards (plan §5.4 / §5.5 / §5.6 / §5.7) ---
# These tests run against the assembled validation deck (`assemble_deck`
# applied to validation/recipe-deck.yaml) and verify chrome / forbidden /
# font contracts hold AT THE OUTPUT LEVEL, not just in source files.


@pytest.fixture(scope="module")
def assembled_terminal_validation_html(tmp_path_factory):
    """Assemble the h2t-terminal validation deck once per test module."""
    profile_dir = PROFILES_DIR / "h2t-terminal"
    recipe = yaml.safe_load(
        _terminal_validation_recipe_path().read_text(encoding="utf-8")
    )
    out = tmp_path_factory.mktemp("terminal-validation")
    asm.assemble_deck(
        recipe, profile_dir, out, palette=recipe.get("palette", "default")
    )
    return (out / "index.html").read_text(encoding="utf-8")


# §5.4 single-file output contract — output-level guards.

def test_h2t_terminal_deck_output_no_external_app_stylesheets(
    assembled_terminal_validation_html,
):
    """Only Google Fonts <link rel="stylesheet"> permitted; no base.css/profile.css."""
    html_text = assembled_terminal_validation_html
    sheet_links = re.findall(
        r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', html_text, re.IGNORECASE
    )
    for link in sheet_links:
        assert "fonts.googleapis.com" in link, (
            f"Non-Google-Fonts stylesheet link forbidden in deck output: {link}"
        )
    assert 'href="base.css"' not in html_text
    assert 'href="profile.css"' not in html_text


def test_h2t_terminal_deck_output_no_script_src(assembled_terminal_validation_html):
    """All JS must be inline; zero <script src=...> occurrences."""
    html_text = assembled_terminal_validation_html
    assert "<script src" not in html_text


# §5.5 frame contract — output level.

def test_h2t_terminal_deck_output_has_progress_bar(
    assembled_terminal_validation_html,
):
    assert '<div id="progress-bar">' in assembled_terminal_validation_html


def test_h2t_terminal_deck_output_has_counter(assembled_terminal_validation_html):
    html_text = assembled_terminal_validation_html
    assert '<div id="slide-counter">' in html_text
    assert 'id="cnt-current"' in html_text
    assert 'id="cnt-total"' in html_text


def test_h2t_terminal_deck_output_has_nav_hint(assembled_terminal_validation_html):
    html_text = assembled_terminal_validation_html
    m = re.search(
        r'<div id="nav-hint">\s*([^<]+?)\s*</div>', html_text
    )
    assert m, "Output must contain non-empty <div id='nav-hint'>...</div>"
    assert m.group(1).strip(), "Nav hint text must be non-empty"


def test_h2t_terminal_deck_output_has_scanlines(assembled_terminal_validation_html):
    html_text = assembled_terminal_validation_html
    assert "body::after" in html_text, "scanline overlay rule must be inlined"
    assert "repeating-linear-gradient" in html_text


def test_h2t_terminal_deck_output_lang_attr_matches_recipe(
    assembled_terminal_validation_html,
):
    """`<html lang="...">` must match the recipe's `lang` field."""
    recipe = yaml.safe_load(
        _terminal_validation_recipe_path().read_text(encoding="utf-8")
    )
    expected = recipe.get("lang", "en")
    assert f'<html lang="{expected}">' in assembled_terminal_validation_html


def test_h2t_terminal_deck_output_no_slide_menu(
    assembled_terminal_validation_html,
):
    """Legacy multi-file sidebar must not appear in deck-form output."""
    assert 'class="slide-menu"' not in assembled_terminal_validation_html


# §5.6 forbidden patterns — output level.

def test_h2t_terminal_deck_output_no_mermaid(assembled_terminal_validation_html):
    """Neither golden uses mermaid; output must be free of references."""
    html_text = assembled_terminal_validation_html.lower()
    assert "mermaid.min.js" not in html_text
    assert 'class="mermaid"' not in html_text
    assert "mermaid-wrap" not in html_text


def test_h2t_terminal_deck_output_no_radius_on_slide_container(
    assembled_terminal_validation_html,
):
    """Slides must be sharp-edged; only inner cards/stats/badges may have radius.
    We scan inlined CSS for `.slide` or `.slide-inner` rules carrying
    `border-radius`. Cards-with-radius pass — only the slide containers fail."""
    html_text = assembled_terminal_validation_html
    # Extract the inlined <style>...</style> payload
    style_match = re.search(r"<style>(.*?)</style>", html_text, re.DOTALL)
    assert style_match, "expected an inlined <style> block"
    css = style_match.group(1)
    # Walk every CSS rule and check no `.slide` / `.slide-inner` selector
    # (with no further class chain) carries a border-radius declaration.
    rule_re = re.compile(
        r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL
    )
    for m in rule_re.finditer(css):
        selectors = m.group("selectors")
        body = m.group("body")
        if "border-radius" not in body:
            continue
        for raw_sel in selectors.split(","):
            sel = raw_sel.strip()
            # Exact `.slide` or `.slide-inner` (with optional pseudo / state).
            if re.fullmatch(r"\.slide(?:[:.][\w-]+)?", sel) or re.fullmatch(
                r"\.slide-inner(?:[:.][\w-]+)?", sel
            ):
                pytest.fail(
                    f"border-radius forbidden on slide container selector "
                    f"{sel!r}; rule body: {body.strip()!r}"
                )


# §5.7 single-font contract — output level.

def test_h2t_terminal_deck_output_inlines_jetbrains_mono_chain(
    assembled_terminal_validation_html,
):
    """Both --font-heading and --font-body must lean on the JetBrains Mono
    fallback chain, end in monospace, and never declare a serif fallback."""
    html_text = assembled_terminal_validation_html
    style_match = re.search(r"<style>(.*?)</style>", html_text, re.DOTALL)
    assert style_match
    css = style_match.group(1)
    for token in ("--font-heading", "--font-body"):
        decl_re = re.compile(rf"{token}\s*:\s*([^;]+);")
        decl = decl_re.search(css)
        assert decl, f"inlined CSS missing {token}"
        value = decl.group(1)
        assert "JetBrains Mono" in value, (
            f"{token} must include 'JetBrains Mono' fallback; got {value!r}"
        )
        assert value.rstrip().endswith("monospace"), (
            f"{token} must terminate the fallback chain with `monospace`; got {value!r}"
        )
    assert "serif" not in css.lower(), "deck typography must be monospace-only"


# ───────────────────────────────────────────────────────────────────────────
# T14 — mobile adaptation contract
#
# Replaces the withdrawn T4/T5/T6 `no @media (max-width:` ban. Mobile rules are
# REQUIRED (Gate B). Desktop fidelity (Gate A) is preserved by the
# `_outside_media` invariant tests below. Implementation lands in T15; until
# then, `test_h2t_terminal_deck_mobile_*_covers_*` tests are TDD-red on
# purpose. Acceptance criteria are documented in the R2a plan §Acceptance
# gates and §Mobile adaptation contract sections.
# ───────────────────────────────────────────────────────────────────────────


_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_css_comments(css: str) -> str:
    """Remove `/* ... */` blocks so that documentation literals (e.g. the
    string `@media` mentioned inside a comment, T17.6 fix) do not confuse
    the brace-walking parser used by the helpers below."""
    return _CSS_COMMENT_RE.sub("", css)


def _all_deck_css() -> str:
    """Concatenate every CSS file shipped under deck/ for terminal profile.
    CSS comments are stripped so docstrings can mention `@media` etc. without
    poisoning the structural parsers."""
    deck = _terminal_deck_dir()
    parts = [
        (deck / "tokens.css").read_text(encoding="utf-8"),
        (deck / "palettes" / "default.css").read_text(encoding="utf-8"),
        (deck / "frame" / "frame.css").read_text(encoding="utf-8"),
    ]
    for layout in EXPECTED_LAYOUTS:
        parts.append(
            (deck / "slides" / layout / f"{layout}.css").read_text(encoding="utf-8")
        )
    return _strip_css_comments("\n".join(parts))


def _extract_media_blocks(css: str, query_pattern: str) -> list:
    """Return inner content of every `@media (<query_pattern>)` block.
    `query_pattern` is a regex applied to the part inside the parens."""
    out = []
    pat = re.compile(rf"@media\s*\({query_pattern}\)\s*\{{")
    i = 0
    while True:
        m = pat.search(css, i)
        if not m:
            break
        depth = 1
        j = m.end()
        while j < len(css) and depth > 0:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        out.append(css[m.end():j - 1])
        i = j
    return out


def _deck_css_outside_media() -> str:
    """Return deck CSS with every @media block stripped (any query)."""
    css = _all_deck_css()
    out = []
    pat = re.compile(r"@media\b")
    i = 0
    while True:
        m = pat.search(css, i)
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:m.start()])
        brace = css.find("{", m.end())
        if brace == -1:
            break
        depth = 1
        j = brace + 1
        while j < len(css) and depth > 0:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        i = j
    return "".join(out)


def _mobile_block_text() -> str:
    return "\n".join(
        _extract_media_blocks(_all_deck_css(), r"\s*max-width:\s*480px\s*")
    )


def _iter_rules(css: str):
    """Yield (selector, body) for top-level CSS rules, skipping whitespace and
    /* comments */. Sufficient for our flat (non-nested) deck CSS."""
    i = 0
    n = len(css)
    while i < n:
        # Skip whitespace + comments
        while i < n:
            c = css[i]
            if c.isspace():
                i += 1
                continue
            if css[i:i + 2] == "/*":
                end = css.find("*/", i + 2)
                if end == -1:
                    return
                i = end + 2
                continue
            break
        if i >= n:
            return
        brace = css.find("{", i)
        if brace == -1:
            return
        sel = css[i:brace].strip()
        depth = 1
        j = brace + 1
        while j < n and depth > 0:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[brace + 1:j - 1]
        yield sel, body
        i = j


def _has_mobile_rule(selector_pattern: str, decl_pattern: str) -> bool:
    """True iff some rule inside the @media (max-width: 480px) block has a
    selector matching `selector_pattern` (regex) AND a body matching
    `decl_pattern` (regex)."""
    block = _mobile_block_text()
    sel_re = re.compile(selector_pattern)
    decl_re = re.compile(decl_pattern)
    for sel, body in _iter_rules(block):
        # Check each comma-separated selector; rule applies if any matches.
        for raw in sel.split(","):
            if sel_re.search(raw) and decl_re.search(body):
                return True
    return False


# --- §T14.1 mobile breakpoint must exist ---


def test_h2t_terminal_deck_mobile_breakpoint_present():
    """Deck CSS must contain at least one `@media (max-width: 480px)` block.
    TDD-red until T15 implementation."""
    blocks = _extract_media_blocks(_all_deck_css(), r"\s*max-width:\s*480px\s*")
    assert blocks, (
        "Deck CSS must contain a `@media (max-width: 480px)` block "
        "(T14 contract; satisfied by T15 implementation)."
    )


# --- §T14.2 desktop core declarations must live OUTSIDE @media ---


_DESKTOP_INVARIANTS = [
    # (label, selector substring, declaration substring)
    # NOTE (T17.6): the `slide-padding` row was split into two dedicated tests
    # below — `_slide_padding_tokens_default_to_canonical` (asserts the four
    # `--deck-slide-padding-*` tokens default to 56/80/80/80) and
    # `_slide_rule_uses_padding_tokens` (asserts the `.slide` rule wires those
    # tokens via `var(...)`). Together they preserve the same desktop fidelity
    # invariant while exposing a per-deck handle.
    ("title-h1-size",   ".title-block h1",    "font-size: 64px"),
    ("final-h1-size",   ".final-block h1",    "font-size: 56px"),
    ("divider-h1-size", ".divider-block h1",  "font-size: 48px"),
]


@pytest.mark.parametrize(
    "label,selector_substring,decl_substring",
    _DESKTOP_INVARIANTS,
    ids=[t[0] for t in _DESKTOP_INVARIANTS],
)
def test_h2t_terminal_deck_desktop_invariant_outside_media(
    label, selector_substring, decl_substring
):
    """Authoritative desktop sizing must remain OUTSIDE any @media block;
    mobile rules only override under `(max-width: 480px)`."""
    css = _deck_css_outside_media()
    for sel, body in _iter_rules(css):
        if selector_substring.strip() in sel and decl_substring in body:
            return
    pytest.fail(
        f"Desktop invariant '{label}' missing outside @media: expected "
        f"selector with {selector_substring!r} declaring {decl_substring!r}"
    )


# --- §T17.6 desktop slide-padding tokens (infrastructure handle) ---

_SLIDE_PADDING_TOKEN_DEFAULTS = [
    ("--deck-slide-padding-top",    "56px"),
    ("--deck-slide-padding-right",  "80px"),
    ("--deck-slide-padding-bottom", "80px"),
    ("--deck-slide-padding-left",   "80px"),
]


@pytest.mark.parametrize(
    "token,default_value",
    _SLIDE_PADDING_TOKEN_DEFAULTS,
    ids=[t[0] for t in _SLIDE_PADDING_TOKEN_DEFAULTS],
)
def test_h2t_terminal_deck_slide_padding_tokens_default_to_canonical(
    token, default_value
):
    """Each `--deck-slide-padding-*` token must default to the canonical
    pos-sprint/merkazim value (56/80/80/80). Per-deck overrides change the
    token; the desktop rule is unchanged."""
    css = _deck_css_outside_media()
    pat = re.compile(rf"{re.escape(token)}\s*:\s*{re.escape(default_value)}\s*;")
    assert pat.search(css), (
        f"Expected `{token}: {default_value};` in deck tokens.css "
        f"(outside any @media block)"
    )


def test_h2t_terminal_deck_slide_rule_uses_padding_tokens():
    """Desktop `.slide` rule must wire all four padding sides via `var(...)`
    references to `--deck-slide-padding-{top,right,bottom,left}` — that is the
    handle exposed for per-deck horizontal-inset adjustments. Replaces the
    literal `padding: 56px 80px 80px` invariant from pre-T17.6."""
    css = _deck_css_outside_media()
    for sel, body in _iter_rules(css):
        if sel.strip() != ".slide":
            continue
        if "padding:" not in body:
            continue
        for side in ("top", "right", "bottom", "left"):
            assert (
                f"var(--deck-slide-padding-{side})" in body
            ), (
                f".slide padding must reference var(--deck-slide-padding-{side}); "
                f"body was: {body.strip()!r}"
            )
        return
    pytest.fail(
        "No `.slide` rule with a `padding:` declaration found outside @media"
    )


# --- §T14.3 mobile adaptation must cover each component ---


_MOBILE_COVERAGE = [
    # (label, selector regex, declaration regex)
    ("slide-padding",     r"\.slide\b",                    r"padding:\s*[^;]+"),
    ("title-h1-size",     r"\.title-block\s+h1",           r"font-size:\s*"),
    ("final-h1-size",     r"\.final-block\s+h1",           r"font-size:\s*"),
    ("divider-h1-size",   r"\.divider-block\s+h1",         r"font-size:\s*"),
    ("h2-size",           r"(^|\s|,)h2(\s|$|,)",           r"font-size:\s*"),
    ("card-row-stack",    r"\.card-row\b",                 r"flex-direction:\s*column"),
    ("layer-stack",       r"\.layer\b",                    r"flex-direction:\s*column"),
    ("split-single-col",  r"\.split\b",                    r"grid-template-columns:\s*1fr"),
    ("code-policy",       r"\.code-block\b|\.code-block\s+pre",
                                                            r"font-size:|overflow-x:|padding:"),
    ("table-mobile-representation",
                          r"\.table-desktop\b",            r"display:\s*none"),
    ("counter-chrome",    r"#slide-counter\b",             r"font-size:|top:|right:"),
    ("nav-hint-chrome",   r"#nav-hint\b",                  r"font-size:|bottom:|right:"),
]


@pytest.mark.parametrize(
    "label,selector_pattern,decl_pattern",
    _MOBILE_COVERAGE,
    ids=[t[0] for t in _MOBILE_COVERAGE],
)
def test_h2t_terminal_deck_mobile_adaptation_covers(
    label, selector_pattern, decl_pattern
):
    """For each component listed in parity-notes.md §Proposed mobile adaptation
    plan, a matching rule must exist inside the mobile @media block.
    TDD-red until T15 lands the rules."""
    assert _has_mobile_rule(selector_pattern, decl_pattern), (
        f"Mobile coverage '{label}' missing: expected rule with selector "
        f"matching /{selector_pattern}/ and declaration matching "
        f"/{decl_pattern}/ inside @media (max-width: 480px)"
    )


# --- §T14.4 mobile must not hide essential slide content ---


_ESSENTIAL_SELECTORS = [
    ".slide",
    ".slide-inner",
    ".eyebrow",
    "h1",
    "h2",
    ".body",
    ".code-block",
    ".bullet-list",
    ".card",
    ".layer",
    ".split",
    "table",
]


def test_h2t_terminal_deck_mobile_no_hidden_essential_content():
    """No mobile rule may set `display: none` or `visibility: hidden` on
    essential slide content. State-based hiding via `:empty` / `:not(...)` is
    allowed (selector retains a pseudo-class — the rule body is conditional).

    Representation-switch classes `.table-desktop` and `.table-mobile` (T15.5
    dual-representation table) are NOT in the essentials list — toggling them
    swaps which DOM tree is shown, not which content exists. Both reps carry
    the same data; assembler emits both unconditionally."""
    block = _mobile_block_text()
    for sel, body in _iter_rules(block):
        if not (
            re.search(r"display:\s*none", body)
            or re.search(r"visibility:\s*hidden", body)
        ):
            continue
        for raw in sel.split(","):
            sel_clean = raw.strip()
            if ":empty" in sel_clean or ":not(" in sel_clean:
                continue
            for essential in _ESSENTIAL_SELECTORS:
                if re.fullmatch(rf"{re.escape(essential)}(\s.*)?", sel_clean):
                    pytest.fail(
                        f"Mobile rule hides essential content: "
                        f"selector {sel_clean!r}, body {body.strip()!r}"
                    )


# --- §T14.5 mobile selectors must reference known deck symbols ---


_KNOWN_HTML_TAGS = {
    "html", "body", "section", "div", "main", "header", "footer", "nav",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
    "pre", "code", "span", "strong", "em", "button", "img", "a",
}


def test_h2t_terminal_deck_mobile_rules_use_known_selectors():
    """Mobile rules must not introduce class/id selectors absent from desktop
    CSS — keeps the mobile contract scoped to the existing layout vocabulary."""
    desktop_css = _deck_css_outside_media()
    desktop_classes = set(re.findall(r"\.[A-Za-z][\w-]*", desktop_css))
    desktop_ids = set(re.findall(r"#[A-Za-z][\w-]*", desktop_css))

    block = _mobile_block_text()
    for sel, _body in _iter_rules(block):
        for raw in sel.split(","):
            classes_in = set(re.findall(r"\.[A-Za-z][\w-]*", raw))
            ids_in = set(re.findall(r"#[A-Za-z][\w-]*", raw))
            unknown_classes = classes_in - desktop_classes
            unknown_ids = ids_in - desktop_ids
            assert not unknown_classes, (
                f"Mobile selector {raw.strip()!r} references unknown "
                f"class(es): {unknown_classes}"
            )
            assert not unknown_ids, (
                f"Mobile selector {raw.strip()!r} references unknown "
                f"id(s): {unknown_ids}"
            )
            tag_only = re.sub(r"[#.][\w-]+", "", raw)
            # Strip pseudo-classes / pseudo-elements (single OR double colon).
            tag_only = re.sub(r"::?[\w-]+(?:\([^)]*\))?", "", tag_only)
            tag_only = re.sub(r"[>+~*\[\]]", " ", tag_only)
            for tok in tag_only.split():
                if tok and tok.lower() not in _KNOWN_HTML_TAGS:
                    pytest.fail(
                        f"Mobile selector {raw.strip()!r} uses unknown "
                        f"tag {tok!r}"
                    )
