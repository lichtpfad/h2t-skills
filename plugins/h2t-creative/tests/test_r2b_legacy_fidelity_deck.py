"""R2b legacy fidelity contracts (h2t-creative R2b — h2t-editorial deck #87).

Scope grows as the slice progresses (each T appends its tests):
- T1: source dossier + token contract + palette contract + typography +
      forbidden-pattern guards + namespace isolation deck vs landing.
- T2: 7 slide layout coverage + per-layout render smoke + editorial
      markers + no-terminal-primitives guards.

Frame chrome, JS, mobile @media, and validation recipe land in T3..T7.
"""
import re
import sys
from pathlib import Path

import pytest
import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PLUGIN_ROOT / "profiles"
REPO_ROOT = PLUGIN_ROOT.parents[1]

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
import assembler as asm  # noqa: E402


def _editorial_profile_dir() -> Path:
    return PROFILES_DIR / "h2t-editorial"


def _editorial_sources_path() -> Path:
    return _editorial_profile_dir() / "sources" / "references.yaml"


def _editorial_deck_dir() -> Path:
    return _editorial_profile_dir() / "deck"


def _editorial_layouts_dir() -> Path:
    return _editorial_deck_dir() / "slides"


# ---------------------------------------------------------------------------
# §9.1.1 Source dossier — deck-only (T1 boundary)
# ---------------------------------------------------------------------------

# Deck dossier for #87. Landing sources (rejuve-appendix-*) belong to #88
# follow-up branch; their goldens are pre-locked under
# docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-golden/ but the
# profile dossier file in this branch references DECK sources only.
_DECK_SOURCE_IDS = {
    "pos-sprint-editorial-example",   # primary — pos-sprint STYLE 2 example
    "pos-sprint-deck-skill",          # contract — STYLE 2 spec
    "pos-sprint-deck-readme",         # contract — skill readme
    "rejuve-presentation",            # secondary — 83-slide live editorial deck
    "rejuve-pitch-deck",              # secondary — 45-slide live editorial deck
}

_LANDING_SOURCE_IDS = {
    "rejuve-appendix-competitive-report",
    "rejuve-appendix-elpodium-decomposition",
}


def test_h2t_editorial_deck_dossier_exists():
    assert _editorial_sources_path().exists(), (
        "Expected profiles/h2t-editorial/sources/references.yaml"
    )


def test_h2t_editorial_deck_dossier_parses():
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    assert isinstance(data, dict)
    assert isinstance(data.get("sources", []), list)


def test_h2t_editorial_deck_dossier_has_deck_metadata():
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    assert data.get("profile") == "h2t-editorial"
    assert data.get("form") == "deck"


def test_h2t_editorial_deck_dossier_includes_all_deck_sources():
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    ids = {s.get("id") for s in data.get("sources", [])}
    missing = _DECK_SOURCE_IDS - ids
    assert not missing, f"Missing deck source ids: {missing}; got {ids}"


def test_h2t_editorial_deck_dossier_excludes_landing_sources():
    """T1 deck-only slice — landing sources belong to #88 follow-up branch."""
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    ids = {s.get("id") for s in data.get("sources", [])}
    leaks = _LANDING_SOURCE_IDS & ids
    assert not leaks, (
        f"Landing source ids present in deck dossier: {leaks}. "
        f"Landing #88 is a separate slice."
    )


def test_h2t_editorial_deck_dossier_paths_resolve():
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    for src in data.get("sources", []):
        rel_path = src.get("path")
        assert rel_path, f"source {src.get('id')!r} missing `path`"
        full = (REPO_ROOT / rel_path).resolve()
        assert full.exists(), (
            f"source {src.get('id')!r} path does not resolve on disk: {rel_path}"
        )


_DECK_GOLDEN_PREFIX = (
    "docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-golden/"
)


def test_h2t_editorial_deck_dossier_paths_under_r2b_deck_golden():
    """Every dossier source path lives under the deck-golden directory.
    Excludes landing-golden by construction."""
    data = yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )
    for src in data.get("sources", []):
        path = src.get("path", "")
        assert path.startswith(_DECK_GOLDEN_PREFIX), (
            f"source {src.get('id')!r} path must start with "
            f"{_DECK_GOLDEN_PREFIX!r}; got {path!r}"
        )


def test_h2t_editorial_deck_dossier_no_synthetic_or_live_only_wording():
    """Same forbidden phrasing as R2a dossier — dossier describes static
    snapshots, never runtime regeneration."""
    text = _editorial_sources_path().read_text(encoding="utf-8").lower()
    for phrase in [
        "live-only", "live only", "llm rebuild", "ai rebuild",
        "to be regenerated", "regenerate at runtime",
        "synthesized at build time", "lorem ipsum", "todo:", "placeholder",
    ]:
        assert phrase not in text, (
            f"references.yaml contains forbidden phrase: {phrase!r}"
        )


# ---------------------------------------------------------------------------
# §9.1.2 Token contract — deck form uses BARE token names (R2a precedent)
# ---------------------------------------------------------------------------


def test_h2t_editorial_deck_tokens_css_exists():
    assert (_editorial_deck_dir() / "tokens.css").exists()


@pytest.mark.parametrize("palette", ["default", "warm", "night"])
def test_h2t_editorial_deck_palette_css_exists(palette):
    assert (_editorial_deck_dir() / "palettes" / f"{palette}.css").exists()


# Palette token contract — System B (rejuve-pitch-deck canonical, post
# 2026-05-07 source arbitration reset). Default values are LIFTED VERBATIM
# from rejuve-pitch-deck `:root` (luxury-print editorial: gold accent +
# warm cream + Playfair/Georgia stack).  warm/night are System B variants
# kept for the 3-palette contract from DESIGN.md.
#
# Editorial deck form uses BARE token names (matches R2a deck precedent).
# Profile-root landing-form CSS keeps using `--color-*` prefix unchanged.
_PALETTE_TOKEN_VALUES = {
    "default": {
        "--bg":           "#fafaf8",
        "--bg-light":     "#f2f0eb",
        "--bg-card":      "#ffffff",
        "--text":         "#141414",
        "--text-dim":     "#6b6560",
        "--accent":       "#c9a96e",
        "--accent-text":  "#8a6520",
        "--copper":       "#7d4e2d",
        "--border":       "#e2dfd8",
    },
    "warm": {
        "--bg":           "#fbf5ea",
        "--bg-light":     "#f1ead9",
        "--bg-card":      "#fffdf9",
        "--text":         "#1c1813",
        "--text-dim":     "#7a6e5e",
        "--accent":       "#c9a96e",
        "--accent-text":  "#8a6520",
        "--copper":       "#7d4e2d",
        "--border":       "#e6dec9",
    },
    "night": {
        "--bg":           "#1a1815",
        "--bg-light":     "#23201b",
        "--bg-card":      "#2a2620",
        "--text":         "#ece4d3",
        "--text-dim":     "#9a8f7c",
        "--accent":       "#d4b27a",
        "--accent-text":  "#caa872",
        "--copper":       "#a06a3f",
        "--border":       "#3a3329",
    },
}


@pytest.mark.parametrize(
    "palette,token,value",
    [(p, t, v) for p, toks in _PALETTE_TOKEN_VALUES.items()
     for t, v in toks.items()],
    ids=[
        f"{p}-{t}"
        for p, toks in _PALETTE_TOKEN_VALUES.items()
        for t in toks
    ],
)
def test_h2t_editorial_deck_palette_declares_token(palette, token, value):
    css = (_editorial_deck_dir() / "palettes" / f"{palette}.css").read_text(
        encoding="utf-8"
    )
    pat = re.compile(
        rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;"
    )
    assert pat.search(css), (
        f"palette {palette!r} must declare `{token}: {value};`"
    )


# ---------------------------------------------------------------------------
# Typography contract — Playfair Display (heading) + Georgia (body) +
# system-ui (utility) — System B token shape `--fh / --fb / --fu`.
# Lifted verbatim from rejuve-pitch-deck `:root`. Replaced the System A
# `--font-heading / --font-body` shape after the 2026-05-07 source
# arbitration reset.
# ---------------------------------------------------------------------------


def test_h2t_editorial_deck_tokens_declare_fh_fb_fu():
    """System B shape: `--fh` (heading), `--fb` (body serif), `--fu` (utility sans).
    No `--font-heading / --font-body / --font-mono` (System A names)."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    assert "--fh:" in css, "tokens.css must declare --fh (heading font)"
    assert "--fb:" in css, "tokens.css must declare --fb (body serif font)"
    assert "--fu:" in css, "tokens.css must declare --fu (utility sans font)"


def test_h2t_editorial_deck_tokens_use_playfair_for_heading():
    """`--fh` must include 'Playfair Display' (System B canonical)."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    pat = re.compile(
        r"--fh\s*:\s*[^;]*Playfair Display", re.IGNORECASE
    )
    assert pat.search(css), (
        "--fh must include 'Playfair Display' fallback chain"
    )


def test_h2t_editorial_deck_tokens_use_georgia_for_body():
    """System B body is SERIF (Georgia), not sans (Inter was System A)."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    pat = re.compile(r"--fb\s*:\s*[^;]*\bGeorgia\b", re.IGNORECASE)
    assert pat.search(css), (
        "--fb must include 'Georgia' (System B body serif chain)"
    )


def test_h2t_editorial_deck_tokens_use_systemui_for_utility():
    """`--fu` is the utility sans (counter, .label, table chrome)."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    pat = re.compile(r"--fu\s*:\s*[^;]*\bsystem-ui\b", re.IGNORECASE)
    assert pat.search(css), (
        "--fu must include 'system-ui' (System B utility sans chain)"
    )


def test_h2t_editorial_deck_tokens_serif_fallback_for_heading():
    """Editorial heading must end on a `serif` family fallback."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    decl = re.search(r"--fh\s*:\s*([^;]+);", css)
    assert decl, "--fh declaration missing"
    assert "serif" in decl.group(1).lower(), (
        f"--fh must end on `serif` fallback; got {decl.group(1)!r}"
    )


def test_h2t_editorial_deck_tokens_serif_fallback_for_body():
    """System B body chain must also end on serif (Georgia → Times → serif)."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    decl = re.search(r"--fb\s*:\s*([^;]+);", css)
    assert decl, "--fb declaration missing"
    assert "serif" in decl.group(1).lower(), (
        f"--fb must end on `serif` fallback; got {decl.group(1)!r}"
    )


def test_h2t_editorial_deck_tokens_no_system_a_token_names():
    """Forbid the System A token shape (`--font-heading / --font-body /
    --font-mono`) — those belong to System A (pos-sprint editorial), not
    System B (rejuve-pitch-deck canonical). Strip comments first so a
    docstring can mention the demoted names without poisoning the check."""
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for forbidden in ("--font-heading", "--font-body", "--font-mono"):
        assert forbidden not in no_comments, (
            f"tokens.css must not declare System A token {forbidden!r} — "
            f"use --fh / --fb / --fu (System B canonical)"
        )


def test_h2t_editorial_deck_no_inter_body_font():
    """Inter is the System A body font (pos-sprint). System B body is
    Georgia. Forbid 'Inter' anywhere in deck CSS so a stale palette/import
    cannot silently re-introduce the sans body."""
    deck = _editorial_deck_dir()
    for path in [
        deck / "tokens.css",
        deck / "palettes" / "default.css",
        deck / "palettes" / "warm.css",
        deck / "palettes" / "night.css",
    ]:
        css = path.read_text(encoding="utf-8")
        # Allow it inside comments? No — even comments leak via CSS-comment
        # strip on assemble. Strip comments first, then check.
        no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        assert "Inter" not in no_comments, (
            f"{path.name}: 'Inter' literal forbidden — System B body is "
            f"Georgia, not Inter (System A leak)"
        )


# ---------------------------------------------------------------------------
# Forbidden patterns — terminal-style ornaments must not leak in
# ---------------------------------------------------------------------------


def _all_t1_deck_css_files():
    deck = _editorial_deck_dir()
    return [
        deck / "tokens.css",
        deck / "palettes" / "default.css",
        deck / "palettes" / "warm.css",
        deck / "palettes" / "night.css",
    ]


def test_h2t_editorial_deck_no_monospace_terminal_fonts():
    """Editorial uses Playfair (heading) + Inter (body); no monospace
    terminal-style fallback chain."""
    for css_path in _all_t1_deck_css_files():
        css = css_path.read_text(encoding="utf-8").lower()
        for forbidden in [
            "jetbrains mono", "fira code", "sf mono", "menlo",
            "consolas", "monospace",
        ]:
            assert forbidden not in css, (
                f"{css_path.name}: forbidden monospace token "
                f"{forbidden!r} (terminal-style)"
            )


def test_h2t_editorial_deck_tokens_no_scanline_overlay():
    css = (_editorial_deck_dir() / "tokens.css").read_text(encoding="utf-8")
    assert "repeating-linear-gradient" not in css, (
        "scanline overlay (repeating-linear-gradient) is terminal-style"
    )
    assert "body::after" not in css, (
        "body::after overlay is terminal-style; editorial does not use scanlines"
    )


def test_h2t_editorial_deck_no_crosshair_cursor():
    for css_path in _all_t1_deck_css_files():
        css = css_path.read_text(encoding="utf-8")
        assert "cursor: crosshair" not in css, (
            f"{css_path.name}: cursor: crosshair forbidden in editorial deck"
        )


def test_h2t_editorial_deck_no_mermaid_refs():
    for css_path in _all_t1_deck_css_files():
        css = css_path.read_text(encoding="utf-8").lower()
        assert "mermaid" not in css, (
            f"{css_path.name}: mermaid reference forbidden"
        )


def test_h2t_editorial_deck_no_terminal_hud_tokens():
    """No --terminal-* / --hud-* / --scanline-* token namespaces (they would
    leak terminal aesthetic into the editorial profile)."""
    for css_path in _all_t1_deck_css_files():
        css = css_path.read_text(encoding="utf-8")
        for prefix in ["--terminal-", "--hud-", "--scanline-"]:
            assert prefix not in css, (
                f"{css_path.name}: forbidden token prefix {prefix!r}"
            )


# ---------------------------------------------------------------------------
# Namespace isolation — deck (bare) vs landing (--color-*)
# ---------------------------------------------------------------------------


def test_h2t_editorial_deck_uses_bare_token_names_not_color_prefix():
    """Deck form uses bare `--bg/--text/--accent` (R2a precedent).
    Landing form keeps `--color-*` prefix (R1 contract). T1 enforces the
    boundary at the deck side."""
    for css_path in _all_t1_deck_css_files():
        css = css_path.read_text(encoding="utf-8")
        decls = re.findall(r"--color-[a-z][a-z0-9-]*\s*:", css)
        assert not decls, (
            f"{css_path.name}: --color-* declarations forbidden in deck form "
            f"(landing-form contract); use bare names. Found: {decls}"
        )


def test_h2t_editorial_landing_root_tokens_unchanged():
    """T1 deck slice must NOT modify profile-root landing-form tokens.css."""
    landing_tokens = _editorial_profile_dir() / "tokens.css"
    assert landing_tokens.exists(), (
        "landing-form profile-root tokens.css must remain present"
    )
    css = landing_tokens.read_text(encoding="utf-8")
    assert "--color-bg" in css, (
        "landing tokens.css must keep --color-bg per R1 contract"
    )
    assert "--color-text" in css, (
        "landing tokens.css must keep --color-text per R1 contract"
    )


@pytest.mark.parametrize("palette", ["default", "warm", "night"])
def test_h2t_editorial_landing_palette_unchanged(palette):
    """T1 deck slice must NOT modify profile-root landing palettes."""
    palette_path = (
        _editorial_profile_dir() / "palettes" / f"{palette}.css"
    )
    assert palette_path.exists(), (
        f"landing-form palette {palette}.css must remain present"
    )
    css = palette_path.read_text(encoding="utf-8")
    assert "--color-bg" in css, (
        f"landing palette {palette}.css must keep --color-bg per R1 contract"
    )


# ===========================================================================
# T2 — slide layout coverage (deck-only #87)
# ===========================================================================

# Editorial layout vocabulary — System B canonical. The 9 layouts below
# are the closed editorial vocabulary; pitch-deck `<table>` and
# `.stat-row + .stat` cards are part of System B (rejuve-pitch-deck slides
# 3, 6, 9, 10, 11, 12) and are exposed as `stats` and `table` layouts.
# Code/cards/layers/duration-tag etc. remain TERMINAL-only and are still
# forbidden inside editorial layout files via `_TERMINAL_CLASS_PATTERNS`.
EDITORIAL_LAYOUTS = [
    "title", "title-body", "quote", "two-column",
    "image-text", "divider", "final",
    "stats", "table",
]


def test_h2t_editorial_deck_slides_dir_exists():
    assert _editorial_layouts_dir().is_dir()


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_dir_exists(layout):
    assert (_editorial_layouts_dir() / layout).is_dir(), (
        f"Missing layout dir: deck/slides/{layout}/"
    )


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_has_html(layout):
    assert (_editorial_layouts_dir() / layout / f"{layout}.html").exists()


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_has_css(layout):
    assert (_editorial_layouts_dir() / layout / f"{layout}.css").exists()


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_has_manifest(layout):
    assert (_editorial_layouts_dir() / layout / "manifest.yaml").exists()


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_manifest_layout_field_matches_dir(layout):
    manifest = yaml.safe_load(
        (_editorial_layouts_dir() / layout / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(manifest, dict)
    assert manifest.get("layout") == layout, (
        f"manifest.yaml `layout` must equal {layout!r}, got {manifest.get('layout')!r}"
    )
    assert isinstance(manifest.get("fields", {}), dict)


def test_h2t_editorial_deck_layout_set_matches_expected():
    """Closed vocabulary — exactly 7 editorial layouts; no extras (no terminal
    leftovers like cards/layers/table/code/stats), no missing."""
    actual = sorted(
        d.name for d in _editorial_layouts_dir().iterdir() if d.is_dir()
    )
    assert actual == sorted(EDITORIAL_LAYOUTS), (
        f"Layout set mismatch: actual={actual}, expected={sorted(EDITORIAL_LAYOUTS)}"
    )


# --- Forbidden patterns inside layout files ---


# Common emoji codepoint blocks — editorial uses accent color, not emoji.
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF"   # Misc symbols & pictographs / supplemental
    r"\U00002600-\U000027BF"    # Misc symbols + dingbats
    r"\U0001F000-\U0001F0FF"    # Mahjong / dominoes / playing cards
    r"]"
)


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_html_no_emoji(layout):
    html_text = (
        _editorial_layouts_dir() / layout / f"{layout}.html"
    ).read_text(encoding="utf-8")
    found = _EMOJI_RE.findall(html_text)
    assert not found, f"{layout}.html contains emoji codepoints: {found}"


# Terminal-deck primitives forbidden in editorial (would leak terminal
# aesthetic). Class names taken from R2a deck/frame/frame.css inventory.
# System A `.eyebrow` is also forbidden — System B uses `.label` as the
# kicker primitive (rejuve-pitch-deck canonical).
_TERMINAL_CLASS_PATTERNS = [
    r"\bcode-block\b", r"\bcode-prompt\b", r"\bcode-cmd\b",
    r"\bcode-arg\b", r"\bcode-comment\b",
    # `.stat-box / .stat-number / .stat-label` are terminal-only stat
    # primitives; System B uses `.stat / .stat .num / .stat .lbl`.
    # `.stat-row` is shared between systems (terminal wraps `.stat-box`,
    # editorial wraps `.stat`) — NOT forbidden in editorial.
    r"\bstat-box\b", r"\bstat-number\b", r"\bstat-label\b",
    r"\bcard-row\b", r"\bcard-icon\b", r"\bcard-title\b", r"\bcard-desc\b",
    r"\.layers\b", r"\.layer-num\b", r"\.layer-name\b", r"\.layer-desc\b",
    r"\bduration-tag\b", r"\bdisclaimer-badge\b",
    # System A leak — pos-sprint editorial used `.eyebrow`; System B uses `.label`.
    r"\beyebrow\b",
]


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_no_terminal_primitives(layout):
    """Editorial deck must not reuse terminal-style component primitives.
    Tests scan both the layout HTML and CSS for forbidden class tokens."""
    layout_dir = _editorial_layouts_dir() / layout
    for path in [layout_dir / f"{layout}.html", layout_dir / f"{layout}.css"]:
        text = path.read_text(encoding="utf-8")
        for pat in _TERMINAL_CLASS_PATTERNS:
            assert not re.search(pat, text), (
                f"{path.name}: forbidden terminal-style primitive matching "
                f"/{pat}/ — editorial uses different vocabulary"
            )


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_no_terminal_data_attrs(layout):
    """Terminal layouts use `data-sym=` for bullets and `data-title=` for code
    badges; editorial uses neither."""
    html_path = _editorial_layouts_dir() / layout / f"{layout}.html"
    text = html_path.read_text(encoding="utf-8")
    assert "data-sym=" not in text, (
        f"{layout}.html: data-sym= is terminal bullet syntax — not editorial"
    )
    assert "data-title=" not in text, (
        f"{layout}.html: data-title= is terminal code-badge syntax — not editorial"
    )


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_no_monospace_or_scanline(layout):
    """Per editorial brand — no monospace fonts, scanlines, crosshair, or
    blink animation in any layout file."""
    layout_dir = _editorial_layouts_dir() / layout
    for path in layout_dir.iterdir():
        if path.suffix not in {".html", ".css", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in [
            "jetbrains mono", "fira code", "sf mono", "menlo", "consolas",
            "monospace", "repeating-linear-gradient", "body::after",
            "cursor: crosshair", "@keyframes blink", "animation: blink",
            "mermaid",
        ]:
            assert forbidden not in text, (
                f"{path.name}: forbidden terminal-style token "
                f"{forbidden!r}"
            )


# --- Editorial markers (positive contract — required vocabulary) ---


def _read_layout_files(layout):
    layout_dir = _editorial_layouts_dir() / layout
    return {
        "html": (layout_dir / f"{layout}.html").read_text(encoding="utf-8"),
        "css":  (layout_dir / f"{layout}.css").read_text(encoding="utf-8"),
        "manifest": yaml.safe_load(
            (layout_dir / "manifest.yaml").read_text(encoding="utf-8")
        ),
    }


def test_h2t_editorial_title_layout_uses_brand_wordmark_composition():
    """System B title = COVER composition (rejuve-pitch-deck canonical):
    `<div class="brand">…</div>` (Playfair 58px, with optional `<em>`
    fragment in accent gold) + `.cover-sub` + `.rule` + `.cover-meta`.
    No `<h1>` here — the brand wordmark is the visual anchor.
    No terminal `class="cursor"` blink either."""
    f = _read_layout_files("title")
    html = f["html"]
    assert 'class="brand"' in html, (
        "title.html must contain a `.brand` wordmark wrapper "
        "(System B cover composition)"
    )
    assert 'class="cover-sub"' in html, (
        "title.html must contain a `.cover-sub` subhead element"
    )
    assert 'class="rule"' in html, (
        "title.html must contain a decorative `.rule` (40×2 gold rectangle)"
    )
    assert 'class="cover-meta"' in html, (
        "title.html must contain a `.cover-meta` line for date / context"
    )
    assert 'class="cursor"' not in html, (
        "title.html must NOT use .cursor (terminal-only blinking block)"
    )


def test_h2t_editorial_title_layout_manifest_declares_brand_fields():
    """System B title manifest fields: `brand_html` (raw HTML so the em
    accent fragment can be authored as `RE<em>juve</em>`), `cover_sub`,
    `cover_meta`."""
    f = _read_layout_files("title")
    fields = f["manifest"].get("fields", {})
    assert "brand_html" in fields, (
        "title.manifest must declare `brand_html` (raw — supports <em> "
        "accent fragment)"
    )
    assert "cover_sub" in fields, (
        "title.manifest must declare `cover_sub` (uppercase subhead)"
    )
    assert "cover_meta" in fields, (
        "title.manifest must declare `cover_meta` (date / context line)"
    )
    # brand_html field must accept raw HTML (not be plain text-escaped),
    # so the template uses `{{ brand_html | safe }}`.
    assert "{{ brand_html | safe }}" in f["html"], (
        "title.html must render brand_html via `| safe` to allow the "
        "<em> accent fragment to pass through"
    )


def test_h2t_editorial_title_body_layout_uses_h2():
    """Default content slide — h2 (Playfair) over body prose."""
    f = _read_layout_files("title-body")
    assert "<h2" in f["html"], "title-body must use <h2> for headline"
    fields = f["manifest"].get("fields", {})
    assert "headline" in fields
    assert "body_html" in fields, (
        "title-body manifest must declare `body_html` field"
    )


def test_h2t_editorial_quote_layout_has_pull_quote_structure():
    """Quote slide is the editorial pull-quote — must use <blockquote>, <q>,
    or a `quote-block`/`quote-slide` wrapper class."""
    f = _read_layout_files("quote")
    html = f["html"]
    assert any(
        marker in html
        for marker in ("<blockquote", "quote-block", "quote-slide")
    ), (
        "quote.html must contain pull-quote markup "
        "(<blockquote>, .quote-block, or .quote-slide wrapper)"
    )
    fields = f["manifest"].get("fields", {})
    assert "quote_html" in fields, (
        "quote.manifest must declare `quote_html` field"
    )


def test_h2t_editorial_quote_layout_supports_attribution():
    f = _read_layout_files("quote")
    fields = f["manifest"].get("fields", {})
    assert "attribution" in fields, (
        "quote.manifest must declare optional `attribution` field"
    )


def test_h2t_editorial_two_column_layout_supports_left_right_html():
    """Two-column layout — `left_html` + `right_html` both required (R2b plan §5.1)."""
    f = _read_layout_files("two-column")
    fields = f["manifest"].get("fields", {})
    assert "left_html" in fields, (
        "two-column.manifest must declare `left_html` field"
    )
    assert "right_html" in fields, (
        "two-column.manifest must declare `right_html` field"
    )
    # And the template renders both raw
    html = f["html"]
    assert "{{ left_html | safe }}" in html or "{{left_html|safe}}" in html
    assert "{{ right_html | safe }}" in html or "{{right_html|safe}}" in html


def test_h2t_editorial_image_text_layout_supports_image_and_caption():
    """Image-text layout — `image_url` (URL plain text) + `caption` field."""
    f = _read_layout_files("image-text")
    fields = f["manifest"].get("fields", {})
    assert "image_url" in fields, (
        "image-text.manifest must declare `image_url` field"
    )
    # Caption may live as `caption` or `caption_html` (editorial may emphasize
    # spans inside captions).
    assert any(name in fields for name in ("caption", "caption_html")), (
        "image-text.manifest must declare a caption / caption_html field"
    )
    html = f["html"]
    assert "<img" in html, "image-text.html must include an <img> element"


def test_h2t_editorial_divider_layout_centered_and_h1():
    """Divider — section break with centered Playfair display."""
    f = _read_layout_files("divider")
    assert "<h1" in f["html"], "divider must use <h1>"
    fields = f["manifest"].get("fields", {})
    assert "headline" in fields


def test_h2t_editorial_final_layout_uses_h1_display():
    """Final slide — large centered display; no cursor blink (terminal-only)."""
    f = _read_layout_files("final")
    assert "<h1" in f["html"], "final must use <h1>"
    assert 'class="cursor"' not in f["html"], (
        "final.html must NOT use .cursor (terminal-only blinking block)"
    )


def test_h2t_editorial_stats_layout_supports_stats_html_field():
    """System B stats layout uses pre-rendered raw `stats_html` HTML
    (recipe author writes the full `<div class="stat-row">...</div>`
    markup with `.stat / .stat .num / .stat .lbl` cards verbatim, no
    assembler-side renderer). Manifest declares a required html field."""
    f = _read_layout_files("stats")
    fields = f["manifest"].get("fields", {})
    assert "headline" in fields, "stats.manifest must declare `headline`"
    assert "stats_html" in fields, (
        "stats.manifest must declare `stats_html` (raw HTML — full "
        "<div class=\"stat-row\">…</div> markup)"
    )
    html = f["html"]
    assert "{{ stats_html | safe }}" in html, (
        "stats.html must render stats_html via `| safe` to allow the "
        "stat-row markup to pass through unescaped"
    )


def test_h2t_editorial_stats_layout_uses_label_kicker():
    """Stats layout uses the System B `.label` kicker (10.5px sans
    uppercase letter-spaced gold), not the System A `.eyebrow`."""
    f = _read_layout_files("stats")
    html = f["html"]
    assert 'class="label"' in html, (
        "stats.html must use `.label` kicker (System B canonical)"
    )


def test_h2t_editorial_table_layout_supports_table_html_field():
    """System B table layout uses pre-rendered raw `table_html` (recipe
    author writes the full `<table>...</table>` markup with `tr.ra/.rc/
    .rcu/.rg/.rat` colour-row variants verbatim)."""
    f = _read_layout_files("table")
    fields = f["manifest"].get("fields", {})
    assert "headline" in fields, "table.manifest must declare `headline`"
    assert "table_html" in fields, (
        "table.manifest must declare `table_html` (raw HTML — full "
        "<table>…</table> markup)"
    )
    html = f["html"]
    assert "{{ table_html | safe }}" in html, (
        "table.html must render table_html via `| safe` to allow the "
        "<table> markup to pass through unescaped"
    )


def test_h2t_editorial_table_layout_uses_label_kicker():
    """Table layout uses the System B `.label` kicker."""
    f = _read_layout_files("table")
    html = f["html"]
    assert 'class="label"' in html, (
        "table.html must use `.label` kicker (System B canonical)"
    )


# --- Render smoke (uses existing form-v2 loader; assembler not modified) ---


_EDITORIAL_LAYOUT_MIN_CONTENT = {
    "title": {
        # System B cover composition — brand wordmark with em accent fragment.
        "brand_html": "RE<em>juve</em>",
        "cover_sub": "Smoke Sub",
        "cover_meta": "2026 · Smoke",
    },
    "title-body": {
        "headline": "Section heading",
        "body_html": "<p>body paragraph.</p>",
    },
    "quote": {
        "quote_html": "not a tool — an operating system.",
    },
    "two-column": {
        "headline": "Comparison",
        "left_html":  "<p>left column body.</p>",
        "right_html": "<p>right column body.</p>",
    },
    "image-text": {
        "image_url": "/assets/figure-01.png",
        "image_alt": "Figure 1.",
        "body_html": "<p>caption body.</p>",
    },
    "divider": {
        "headline": "Section II",
    },
    "final": {
        "headline": "Iterate kindly.",
    },
    "stats": {
        "label": "03 — Smoke",
        "headline": "Stats smoke",
        "stats_html": (
            '<div class="stat-row">'
            '<div class="stat"><span class="num">42</span>'
            '<div class="lbl">smoke metric</div></div>'
            '</div>'
        ),
    },
    "table": {
        "label": "06 — Smoke",
        "headline": "Table smoke",
        "table_html": (
            '<table><thead><tr><th>A</th><th>B</th></tr></thead>'
            '<tbody><tr class="ra"><td>row-a</td><td>row-b</td></tr></tbody>'
            '</table>'
        ),
    },
}


@pytest.mark.parametrize("layout", EDITORIAL_LAYOUTS)
def test_h2t_editorial_deck_layout_renders_smoke(layout):
    """Each layout assembles into a `<section class='slide'>` with the
    minimal-content recipe — proves the existing form-v2 loader supports
    editorial layouts without assembler changes."""
    profile_dir = _editorial_profile_dir()
    slide = {"layout": layout, "content": _EDITORIAL_LAYOUT_MIN_CONTENT[layout]}
    out = asm._build_deck_slide_html_v2(slide, profile_dir, index=0)
    assert out.startswith('<section class="slide'), out[:80]
    assert out.endswith("</section>"), out[-80:]
    assert 'class="slide-inner' in out, (
        f"{layout}: rendered slide must contain a slide-inner wrapper"
    )


# ===========================================================================
# T3 — frame chrome + navigation JS (deck-only #87)
# ===========================================================================


def _editorial_frame_css_path() -> Path:
    return _editorial_deck_dir() / "frame" / "frame.css"


def _editorial_deck_nav_js_path() -> Path:
    return _editorial_deck_dir() / "js" / "deck-nav.js"


# --- Frame existence ---


def test_h2t_editorial_deck_frame_css_exists():
    assert _editorial_frame_css_path().exists()


def test_h2t_editorial_deck_nav_js_exists():
    assert _editorial_deck_nav_js_path().exists()


# --- Frame chrome selectors ---


def test_h2t_editorial_deck_frame_has_progress_bar():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "#progress-bar" in css


def test_h2t_editorial_deck_frame_has_slide_counter():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "#slide-counter" in css


def test_h2t_editorial_deck_frame_has_nav_hint():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "#nav-hint" in css


def test_h2t_editorial_deck_frame_has_label_primitive():
    """Every editorial layout uses `<div class="label">` as the kicker —
    the shared primitive style lives in frame.css. System B canonical
    (replaces System A's `.eyebrow`)."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert ".label" in css, (
        "frame.css must declare a shared `.label` primitive (System B kicker)"
    )


def test_h2t_editorial_deck_frame_has_rule_primitive():
    """System B cover + per-slide grammar uses `.rule` — a 40×2 gold
    rectangle reused as section separator. Defined once in frame.css."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert ".rule" in css, (
        "frame.css must declare a shared `.rule` decorative primitive "
        "(40×2 gold rectangle — rejuve-pitch-deck canonical)"
    )


def test_h2t_editorial_deck_frame_no_eyebrow_primitive():
    """System A `.eyebrow` (pos-sprint editorial) must not appear in
    frame.css — System B uses `.label`."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert ".eyebrow" not in no_comments, (
        "frame.css must not declare `.eyebrow` (System A primitive); "
        "use `.label` (System B canonical)"
    )


# --- Frame editorial markers (positive contract) ---


def test_h2t_editorial_deck_frame_progress_bar_uses_accent_token():
    """Progress bar background must reference --accent (not a raw hex)."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    pb_match = re.search(
        r"#progress-bar\s*\{([^}]*)\}", css, re.DOTALL
    )
    assert pb_match, "frame.css must declare a #progress-bar rule"
    body = pb_match.group(1)
    assert "var(--accent)" in body, (
        "#progress-bar must reference var(--accent), not a raw hex"
    )


def test_h2t_editorial_deck_frame_progress_bar_canonical_height():
    """System B canonical (rejuve-pitch-deck): progress bar = 2px gold.
    System A used 1px; flipped post-arbitration to match canonical."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    pb_match = re.search(
        r"#progress-bar\s*\{([^}]*)\}", css, re.DOTALL
    )
    assert pb_match
    body = pb_match.group(1)
    h_match = re.search(r"height\s*:\s*(\d+)\s*px", body)
    assert h_match, "#progress-bar must declare a pixel height"
    assert int(h_match.group(1)) == 2, (
        f"#progress-bar height must be 2px (rejuve-pitch-deck canonical); "
        f"got {h_match.group(1)}px"
    )


def test_h2t_editorial_deck_frame_progress_bar_no_glow_box_shadow():
    """Terminal had `box-shadow: 0 0 8px var(--accent)` glow — editorial is
    clean, no glowing chrome."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    pb_match = re.search(
        r"#progress-bar\s*\{([^}]*)\}", css, re.DOTALL
    )
    assert pb_match
    body = pb_match.group(1)
    assert "box-shadow" not in body, (
        "#progress-bar must not use box-shadow (terminal-style glow)"
    )


def test_h2t_editorial_deck_frame_chrome_uses_body_font_not_monospace():
    """Counter / nav-hint chrome must use Inter (body), not monospace."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    for selector in ("#slide-counter", "#nav-hint"):
        m = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css, re.DOTALL)
        assert m, f"frame.css must declare a {selector} rule"
        body = m.group(1)
        # Either explicit var(--font-body), OR no font-family override
        # (inheriting body Inter). Forbid explicit var(--font-heading) and
        # any monospace literal.
        assert "var(--font-heading)" not in body, (
            f"{selector}: chrome must not use heading (Playfair) — keep Inter"
        )


def test_h2t_editorial_deck_frame_chrome_uses_dim_color_token():
    """Counter + nav-hint stay quiet (dim). Active counter number may use
    accent, but the base must be dim."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    for selector in ("#slide-counter", "#nav-hint"):
        m = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css, re.DOTALL)
        assert m
        body = m.group(1)
        assert "var(--text-dim)" in body, (
            f"{selector}: must use var(--text-dim) for editorial restraint"
        )


def test_h2t_editorial_deck_frame_no_raw_color_literals():
    """Every color value in frame.css must come from the token system —
    no raw hex / rgb / named colors that bypass the palette swap."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    # Strip comments first.
    no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for raw in re.findall(r"#[0-9A-Fa-f]{3,8}\b", no_comments):
        pytest.fail(
            f"frame.css contains raw hex color {raw!r} — use var(--*) instead"
        )


# --- Frame forbidden patterns (no terminal leak) ---


def test_h2t_editorial_deck_frame_no_scanline_overlay():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "repeating-linear-gradient" not in css, (
        "scanline overlay (repeating-linear-gradient) is terminal-style"
    )
    assert "body::after" not in css, (
        "body::after overlay is terminal-style; editorial does not use scanlines"
    )


def test_h2t_editorial_deck_frame_no_blink_animation():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "@keyframes blink" not in css, (
        "blink animation is terminal-style (cursor); editorial does not blink"
    )
    assert "animation: blink" not in css


def test_h2t_editorial_deck_frame_no_crosshair_cursor():
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    assert "cursor: crosshair" not in css


def test_h2t_editorial_deck_frame_no_monospace_fonts():
    css = _editorial_frame_css_path().read_text(encoding="utf-8").lower()
    for forbidden in [
        "jetbrains mono", "fira code", "sf mono", "menlo",
        "consolas", "monospace",
    ]:
        assert forbidden not in css, (
            f"frame.css: forbidden monospace token {forbidden!r}"
        )


def test_h2t_editorial_deck_frame_no_terminal_primitives():
    """frame.css must not declare terminal-style component primitives —
    those are R2a's vocabulary, not editorial's."""
    css = _editorial_frame_css_path().read_text(encoding="utf-8")
    forbidden = [
        ".code-block", ".code-prompt", ".code-cmd", ".code-arg",
        ".stat-row", ".stat-box", ".card-row", ".card-icon",
        ".layers", ".layer-num", ".layer-name", ".layer-desc",
        ".duration-tag", ".disclaimer-badge", ".cursor::after",
        ".bullet-list",
    ]
    for sel in forbidden:
        assert sel not in css, (
            f"frame.css: forbidden terminal primitive {sel!r}"
        )


def test_h2t_editorial_deck_frame_no_mermaid_refs():
    css = _editorial_frame_css_path().read_text(encoding="utf-8").lower()
    assert "mermaid" not in css


# --- Navigation JS contract ---


def _editorial_nav_js() -> str:
    return _editorial_deck_nav_js_path().read_text(encoding="utf-8")


@pytest.mark.parametrize("key", [
    "ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp",
    "Enter", "Backspace", "Home", "End",
])
def test_h2t_editorial_deck_nav_js_binds_required_keys(key):
    js = _editorial_nav_js()
    assert key in js, f"deck-nav.js must reference {key!r} key binding"


def test_h2t_editorial_deck_nav_js_binds_space_key():
    js = _editorial_nav_js()
    assert "case ' '" in js or "=== ' '" in js or "== ' '" in js, (
        "deck-nav.js must handle the Space key (e.key === ' ')"
    )


def test_h2t_editorial_deck_nav_js_listens_for_keydown():
    js = _editorial_nav_js()
    assert (
        "addEventListener('keydown'" in js
        or 'addEventListener("keydown"' in js
    )


def test_h2t_editorial_deck_nav_js_has_touch_swipe():
    js = _editorial_nav_js()
    assert "touchstart" in js
    assert "touchend" in js
    assert "40" in js, "deck-nav.js must encode a >40px swipe threshold"


def test_h2t_editorial_deck_nav_js_updates_progress_and_counter():
    js = _editorial_nav_js()
    assert "progress-bar" in js
    assert "cnt-current" in js
    assert "cnt-total" in js


def test_h2t_editorial_deck_nav_js_does_not_zero_pad_counter():
    """System B canonical (rejuve-pitch-deck): counter renders `1 / 15`,
    NOT `01 / 15`. Editorial deck-nav.js must not zero-pad — it must write
    plain numbers via `String(n)` only.

    The R2a terminal contract DID zero-pad; that obligation does not bind
    a different profile. Each profile owns its own deck-nav.js — the
    editorial JS must reflect System B."""
    js = _editorial_nav_js()
    no_comments = re.sub(r"/\*[\s\S]*?\*/|//.*", "", js)
    assert "padStart" not in no_comments, (
        "editorial deck-nav.js must NOT call `padStart` — System B "
        "counter renders plain `n / total` without zero-padding "
        "(rejuve-pitch-deck canonical)"
    )


def test_h2t_editorial_deck_nav_js_uses_merkazim_progress_formula():
    js = _editorial_nav_js()
    assert re.search(r"\(\s*current\s*\+\s*1\s*\)\s*/\s*total", js), (
        "deck-nav.js must compute progress as ((current+1)/total)*100"
    )


def test_h2t_editorial_deck_nav_js_supports_optional_prev_next_buttons():
    js = _editorial_nav_js()
    assert "btn-prev" in js
    assert "btn-next" in js
    assert "disabled" in js, "must toggle disabled state at edges"


def test_h2t_editorial_deck_nav_js_hash_sync():
    js = _editorial_nav_js()
    assert "location.hash" in js
    assert "history.replaceState" in js


def test_h2t_editorial_deck_nav_js_exposes_window_showSlide():
    js = _editorial_nav_js()
    assert re.search(r"window\.showSlide\s*=", js), (
        "deck-nav.js must assign window.showSlide for screenshot tooling"
    )


# --- JS forbidden patterns ---


def test_h2t_editorial_deck_nav_js_no_viewport_branching():
    """Mobile is CSS-only — JS must not branch on viewport."""
    js = _editorial_nav_js()
    assert "matchMedia" not in js
    assert "innerWidth" not in js
    assert not re.search(r"max-width:\s*\d+", js), (
        "deck-nav.js must not embed CSS-style max-width queries"
    )


def test_h2t_editorial_deck_nav_js_no_external_refs():
    js = _editorial_nav_js()
    assert "<script src" not in js
    assert not re.search(r"\bimport\s+[^;]*\bfrom\b", js), (
        "deck-nav.js must not contain ES module imports"
    )


# ===========================================================================
# §9.1.4 / §9.1.6 — Assembler routing + single-file output contract (T4)
#
# These tests verify the deck-form switch fires for h2t-editorial and that the
# assembled output respects the form-v2 single-file invariants:
#   - exactly one file (index.html), no separate base.css/profile.css/fx.js
#   - <style> + <script> blocks with editorial CSS/JS inlined verbatim
#   - only Google-Fonts <link rel="stylesheet"> permitted
#   - zero <script src=> occurrences
#   - no terminal/scanline/monospace ornaments leak into the assembled HTML
#
# Routing tests use a minimal inline recipe (no validation/recipe-deck.yaml
# dependency). Output-level forbidden-pattern guards reuse the T5 validation
# recipe via the `assembled_editorial_validation_html` fixture below.
# ===========================================================================


def _editorial_validation_recipe_path() -> Path:
    return _editorial_profile_dir() / "validation" / "recipe-deck.yaml"


_T4_MINIMAL_RECIPE = {
    "title": "T4 Routing Smoke",
    "lang": "en",
    "palette": "default",
    "nav_hint_text": "arrows / space / swipe",
    "slides": [
        # System B title = brand wordmark cover (no `headline` field).
        {"layout": "title",
         "content": {
             "brand_html": "RE<em>juve</em>",
             "cover_sub": "T4 Smoke",
             "cover_meta": "—",
         }},
        {"layout": "final",
         "content": {"label": "—", "headline": "End", "subline": "."}},
    ],
}


def test_h2t_editorial_profile_is_deck_form():
    """Routing switch: presence of deck/tokens.css flips the assembler to the
    form-v2 single-file path for h2t-editorial."""
    assert asm._is_deck_form_profile(_editorial_profile_dir()), (
        "h2t-editorial must be detected as deck-form (deck/tokens.css present)"
    )


def test_h2t_editorial_deck_assembles_routes_to_form_v2_single_file(tmp_path):
    """assemble_deck on h2t-editorial must write exactly one file: index.html."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    files = sorted(p.name for p in out.iterdir())
    assert files == ["index.html"], (
        f"deck-form output must contain only index.html, got: {files}"
    )


def test_h2t_editorial_deck_output_inlines_css_and_js(tmp_path):
    """Output must carry <style>...</style> and <script>...</script> blocks
    with editorial CSS/JS sentinels appearing verbatim inside them."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert "<style>" in html_text and "</style>" in html_text
    assert "<script>" in html_text and "</script>" in html_text
    assert "--fh:" in html_text, (
        "Editorial token sentinel (--fh) must be inlined (System B shape)"
    )
    assert "--fb:" in html_text, (
        "Editorial body-font sentinel (--fb Georgia) must be inlined"
    )
    assert "Playfair Display" in html_text, (
        "Editorial heading-font sentinel (Playfair Display) must be inlined"
    )
    assert "Georgia" in html_text, (
        "Editorial body-font sentinel (Georgia — System B body serif) "
        "must be inlined"
    )
    assert "addEventListener('keydown'" in html_text or \
        'addEventListener("keydown"' in html_text, (
        "deck-nav.js keydown listener must be inlined into <script>"
    )


def test_h2t_editorial_deck_output_no_external_app_stylesheets(tmp_path):
    """Only Google-Fonts <link rel='stylesheet'> permitted; no base.css /
    profile.css / per-layout CSS files referenced in the assembled output."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    html_text = (out / "index.html").read_text(encoding="utf-8")
    sheet_links = re.findall(
        r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', html_text, re.IGNORECASE
    )
    for link in sheet_links:
        assert "fonts.googleapis.com" in link, (
            f"Non-Google-Fonts stylesheet link forbidden in editorial deck "
            f"output: {link}"
        )
    assert 'href="base.css"' not in html_text
    assert 'href="profile.css"' not in html_text
    assert 'href="frame.css"' not in html_text
    assert 'href="tokens.css"' not in html_text


def test_h2t_editorial_deck_output_no_script_src(tmp_path):
    """All JS must be inline; zero <script src=...> occurrences."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert "<script src" not in html_text


def test_h2t_editorial_deck_output_window_show_slide_inlined_once(tmp_path):
    """The deterministic `window.showSlide` handle must appear exactly once
    in the assembled output (proves JS inlined, not duplicated/missing)."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    html_text = (out / "index.html").read_text(encoding="utf-8")
    # Match the assignment form to skip the docstring mention at the top of
    # deck-nav.js — the *handle* must be assigned exactly once.
    assignment = "window.showSlide = showSlide"
    assert html_text.count(assignment) == 1, (
        f"window.showSlide assignment must appear exactly once in inlined "
        f"output; got {html_text.count(assignment)}"
    )


def test_h2t_editorial_deck_output_no_legacy_slide_menu(tmp_path):
    """Form-v2 has no slide-menu sidebar (legacy multi-file artifact)."""
    out = tmp_path / "out"
    asm.assemble_deck(
        dict(_T4_MINIMAL_RECIPE), _editorial_profile_dir(), out, palette="default"
    )
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert 'class="slide-menu"' not in html_text


def test_h2t_editorial_deck_output_lang_attr_matches_recipe(tmp_path):
    """`<html lang="...">` must reflect the recipe's `lang` field."""
    recipe = dict(_T4_MINIMAL_RECIPE)
    recipe["lang"] = "en"
    out = tmp_path / "out"
    asm.assemble_deck(recipe, _editorial_profile_dir(), out, palette="default")
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in html_text


# ===========================================================================
# §9.1.5 — Validation recipe + assembled-output forbidden patterns (T5)
#
# T5 introduces validation/recipe-deck.yaml which exercises all 7 editorial
# layouts using copy lifted verbatim from the deck goldens (primarily
# pos-sprint-editorial-example.html slides 1–7). The same recipe is then
# fed through the assembler in module-scoped fixture
# `assembled_editorial_validation_html` so the §9.1.6 forbidden-pattern
# guards run against the *assembled* HTML, not just the source files.
# ===========================================================================


# Validation deck covers EIGHT layouts of the 9-layout closed vocabulary.
# image-text is intentionally excluded from the visual gate — no editorial
# golden carries <img> assets, so any image-text rendering would show a
# synthetic placeholder that has no canonical reference to score against.
# Structural coverage of image-text (manifest fields, render smoke) lives
# in the T2 layout tests above; visual coverage stops here.
_EDITORIAL_VALIDATION_LAYOUTS = {
    "title", "title-body", "quote", "two-column",
    "divider", "final",
    "stats", "table",
}


def _load_editorial_validation_recipe() -> dict:
    return yaml.safe_load(
        _editorial_validation_recipe_path().read_text(encoding="utf-8")
    )


def test_h2t_editorial_validation_recipe_exists():
    assert _editorial_validation_recipe_path().exists(), (
        "Expected profiles/h2t-editorial/validation/recipe-deck.yaml"
    )


def test_h2t_editorial_validation_recipe_parses():
    recipe = _load_editorial_validation_recipe()
    assert isinstance(recipe, dict)
    assert recipe.get("type") == "deck"
    assert recipe.get("profile") == "h2t-editorial"
    assert isinstance(recipe.get("slides", []), list)
    # 8 visual slides: title, title-body, quote, two-column, divider,
    # final, stats, table. image-text is intentionally absent — see
    # _EDITORIAL_VALIDATION_LAYOUTS.
    assert len(recipe["slides"]) == 8, (
        f"Validation recipe must cover the 8 visual-gate layouts; "
        f"got {len(recipe.get('slides', []))} slides"
    )


def test_h2t_editorial_validation_recipe_covers_eight_visual_layouts():
    recipe = _load_editorial_validation_recipe()
    layouts_used = {s.get("layout") for s in recipe.get("slides", [])}
    missing = _EDITORIAL_VALIDATION_LAYOUTS - layouts_used
    assert not missing, (
        f"Validation recipe must cover all 8 visual-gate layouts; "
        f"missing: {sorted(missing)}"
    )


def test_h2t_editorial_validation_recipe_excludes_image_text_layout():
    """image-text is structural-only; it must NOT appear in the visual
    validation recipe (no canonical golden image asset to score against)."""
    recipe = _load_editorial_validation_recipe()
    layouts_used = [s.get("layout") for s in recipe.get("slides", [])]
    assert "image-text" not in layouts_used, (
        "validation recipe must NOT include the image-text layout — "
        "the visual gate has no canonical asset to score against; "
        "structural coverage stays in the T2 layout tests"
    )


def test_h2t_editorial_validation_recipe_no_data_uri_placeholder():
    """No `data:image/svg+xml` synthetic placeholder may appear in the
    visual validation recipe. Synthetic visual evidence is exactly the
    pattern Source Arbitration Reset was created to eliminate."""
    raw = _editorial_validation_recipe_path().read_text(encoding="utf-8")
    # Strip YAML comments first so a docstring can mention the prior stub
    # without triggering the guard.
    no_comments = re.sub(r"(?m)^\s*#.*$", "", raw)
    assert "data:image/svg+xml" not in no_comments, (
        "validation recipe must not embed a data:image/svg+xml placeholder "
        "— if no canonical image asset exists, the slide must be excluded "
        "from the visual gate entirely"
    )


def test_h2t_editorial_validation_recipe_assembles(tmp_path):
    """Recipe round-trips through assemble_deck without raising."""
    recipe = _load_editorial_validation_recipe()
    out = tmp_path / "out"
    asm.assemble_deck(
        recipe,
        _editorial_profile_dir(),
        out,
        palette=recipe.get("palette", "default"),
    )
    assert (out / "index.html").exists()


def test_h2t_editorial_validation_recipe_lifts_from_rejuve_pitch_deck():
    """System B canonical: recipe content must be lifted from rejuve-pitch-deck
    (post-arbitration primary). Sentinel strings appear verbatim in the
    pitch-deck golden — covering the cover wordmark + a per-slide kicker
    pattern + the closing meta line + stats/table content."""
    raw = _editorial_validation_recipe_path().read_text(encoding="utf-8")
    # Cover composition sentinels (rejuve-pitch-deck slide 0).
    assert "REjuve" in raw or "RE<em>juve</em>" in raw, (
        "validation recipe must include the REjuve brand wordmark "
        "(System B cover sentinel)"
    )
    assert "AI Revenue Infrastructure" in raw, (
        "validation recipe must include the 'AI Revenue Infrastructure' "
        "subhead (rejuve-pitch-deck cover-sub)"
    )
    # Per-slide .label kicker pattern — pitch-deck uses "NN — Label text".
    # Accept any digit-prefix or em-dash kicker as evidence of pitch-deck-style
    # numbering convention.
    assert re.search(r"\b\d{2}\s*[—–-]\s*\w", raw, re.UNICODE), (
        "validation recipe must include a pitch-deck-style numbered .label "
        "kicker (`NN — text`)"
    )
    # Stats slide sentinels (pitch-deck slide 3 — Рынок Цуга).
    assert "143" in raw, (
        "validation recipe must include the '143' stat (national-count "
        "metric from pitch-deck slide 3)"
    )
    assert "Glencore" in raw, (
        "validation recipe must include 'Glencore' (commodity-firm sentinel "
        "from pitch-deck slide 3 stats)"
    )
    # Table slide sentinels (pitch-deck slide 10 — Три компетенции).
    assert "Три компетенции" in raw, (
        "validation recipe must include the 'Три компетенции' table "
        "headline (pitch-deck slide 10)"
    )
    assert "Revenue-инфраструктура" in raw, (
        "validation recipe must include 'Revenue-инфраструктура' "
        "(table row 3 sentinel from pitch-deck slide 10)"
    )


def test_h2t_editorial_validation_recipe_excludes_pos_sprint_content():
    """System A leakage guard: pos-sprint editorial copy must NOT appear
    in the validation recipe after the 2026-05-07 source arbitration
    reset. These are the most distinctive sentinel strings from the
    earlier (pre-reset) recipe."""
    raw = _editorial_validation_recipe_path().read_text(encoding="utf-8")
    forbidden_pos_sprint_sentinels = [
        "The Art of Knowledge Management",
        "capture, connect, create",
        "Tiago Forte",
        "vault folder hierarchy",
        "Three Principles",
        "Daily Practice",
        "Where to begin",
        "start small",
    ]
    for s in forbidden_pos_sprint_sentinels:
        assert s not in raw, (
            f"validation recipe must not contain pos-sprint sentinel "
            f"{s!r} (System A — demoted to secondary by 2026-05-07 "
            f"arbitration reset)"
        )


def test_h2t_editorial_validation_recipe_each_slide_has_required_fields():
    """Per-layout manifest required-field check — recipe must populate every
    `required: true` field declared in each layout manifest."""
    recipe = _load_editorial_validation_recipe()
    for s in recipe.get("slides", []):
        layout = s.get("layout")
        manifest_path = (
            _editorial_layouts_dir() / layout / "manifest.yaml"
        )
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        content = s.get("content", {})
        for field, schema in manifest.get("fields", {}).items():
            if schema.get("required"):
                assert field in content, (
                    f"layout {layout!r}: required field {field!r} missing "
                    f"from validation recipe content"
                )


# --- Assembled-output fixture (module-scope; used by §9.1.6 guards) ---


@pytest.fixture(scope="module")
def assembled_editorial_validation_html(tmp_path_factory):
    """Assemble the h2t-editorial validation deck once per test module.

    Returns the index.html text. Failures here surface in collection so the
    downstream output-level guards short-circuit cleanly when the recipe is
    missing or malformed (T5 RED → GREEN bridge)."""
    recipe = _load_editorial_validation_recipe()
    out = tmp_path_factory.mktemp("editorial-validation")
    asm.assemble_deck(
        recipe,
        _editorial_profile_dir(),
        out,
        palette=recipe.get("palette", "default"),
    )
    return (out / "index.html").read_text(encoding="utf-8")


def _extract_inlined_style(html_text: str) -> str:
    """Return the contents of the first <style>...</style> block."""
    m = re.search(r"<style>(.*?)</style>", html_text, re.DOTALL)
    assert m, "Editorial deck output must contain an inlined <style> block"
    return m.group(1)


# --- §9.1.6 forbidden patterns at the assembled-output level ---


def test_h2t_editorial_deck_output_no_scanline_overlay(
    assembled_editorial_validation_html,
):
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert "repeating-linear-gradient" not in css, (
        "scanline overlay (repeating-linear-gradient) must not appear in "
        "assembled editorial deck CSS"
    )
    assert "body::after" not in css, (
        "body::after overlay rule is terminal-only; editorial has no scanlines"
    )


def test_h2t_editorial_deck_output_no_blink_animation(
    assembled_editorial_validation_html,
):
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert "@keyframes blink" not in css
    assert "animation: blink" not in css


def test_h2t_editorial_deck_output_no_crosshair_cursor(
    assembled_editorial_validation_html,
):
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert "cursor: crosshair" not in css


def test_h2t_editorial_deck_output_no_mermaid(
    assembled_editorial_validation_html,
):
    html_lower = assembled_editorial_validation_html.lower()
    assert "mermaid.min.js" not in html_lower
    assert 'class="mermaid"' not in html_lower
    assert "mermaid-wrap" not in html_lower


def test_h2t_editorial_deck_output_no_monospace_font_references(
    assembled_editorial_validation_html,
):
    """No JetBrains Mono / Fira Code / Menlo / Consolas / monospace literal
    in the inlined CSS — editorial typography is Playfair + Inter only."""
    css = _extract_inlined_style(assembled_editorial_validation_html).lower()
    for forbidden in [
        "jetbrains mono", "fira code", "sf mono", "menlo",
        "consolas", "monospace",
    ]:
        assert forbidden not in css, (
            f"assembled output: forbidden monospace token {forbidden!r}"
        )


def test_h2t_editorial_deck_output_no_terminal_primitives(
    assembled_editorial_validation_html,
):
    """Terminal vocabulary (cards/layers/code/stats) must not appear in the
    assembled editorial deck — those are R2a's primitives."""
    css = _extract_inlined_style(assembled_editorial_validation_html)
    forbidden_selectors = [
        ".code-block", ".code-prompt", ".code-cmd", ".code-arg", ".code-comment",
        # `.stat-row` is shared with terminal but System B's `stats` layout
        # uses it canonically — only the terminal-only triple (`.stat-box /
        # .stat-number / .stat-label`) stays forbidden.
        ".stat-box", ".stat-number", ".stat-label",
        ".card-row", ".card-icon",
        ".layer-num", ".layer-name", ".layer-desc",
        ".duration-tag", ".disclaimer-badge",
        ".cursor::after", ".bullet-list",
    ]
    for sel in forbidden_selectors:
        assert sel not in css, (
            f"assembled output: forbidden terminal primitive selector "
            f"{sel!r} leaked into editorial deck CSS"
        )


def test_h2t_editorial_deck_output_no_terminal_html_classes(
    assembled_editorial_validation_html,
):
    """The terminal recipe markup classes (used by R2a layouts) must not
    appear in the editorial slide HTML either."""
    html_text = assembled_editorial_validation_html
    forbidden_html_classes = [
        # `class="stat-row"` is System B canonical (rejuve-pitch-deck slide
        # 3 stats grammar) and is INTENTIONALLY present in editorial output.
        'class="card-row"',
        'class="code-block"',
        'class="layer-item"',
    ]
    for cls in forbidden_html_classes:
        assert cls not in html_text, (
            f"assembled output: forbidden terminal HTML class {cls!r}"
        )


# --- §9.1.5 frame chrome / layout coverage at output level ---


def test_h2t_editorial_deck_output_has_progress_bar(
    assembled_editorial_validation_html,
):
    assert '<div id="progress-bar">' in assembled_editorial_validation_html


def test_h2t_editorial_deck_output_has_counter(
    assembled_editorial_validation_html,
):
    html_text = assembled_editorial_validation_html
    assert '<div id="slide-counter">' in html_text
    assert 'id="cnt-current"' in html_text
    assert 'id="cnt-total"' in html_text


def test_h2t_editorial_deck_output_has_nav_hint(
    assembled_editorial_validation_html,
):
    m = re.search(
        r'<div id="nav-hint">\s*([^<]+?)\s*</div>',
        assembled_editorial_validation_html,
    )
    assert m, "Output must contain non-empty <div id='nav-hint'>...</div>"
    assert m.group(1).strip()


def test_h2t_editorial_deck_output_has_label_primitive(
    assembled_editorial_validation_html,
):
    """System B `.label` shared kicker primitive (frame.css) must be inlined."""
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert ".label" in css


def test_h2t_editorial_deck_output_has_rule_primitive(
    assembled_editorial_validation_html,
):
    """System B `.rule` decorative primitive (40×2 gold) must be inlined."""
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert ".rule" in css


# image-text is excluded from the visual validation recipe (post
# 2026-05-07 visual-fix batch); its CSS is therefore not inlined into
# the assembled validation deck (the dedup loop in _build_deck_css_inline
# only pulls CSS for layouts that appear in the recipe). Structural
# coverage of image-text remains in the T2 layout tests.
@pytest.mark.parametrize("layout_block_class", [
    "title-block",
    "title-body-block",
    "quote-slide",
    "two-column-block",
    "divider-block",
    "final-block",
    "stats-block",
    "table-block",
])
def test_h2t_editorial_deck_output_has_layout_css(
    assembled_editorial_validation_html, layout_block_class,
):
    """Each layout's CSS block class must appear in the inlined CSS — proves
    every layout in the recipe contributes its stylesheet via the dedup loop
    in `_build_deck_css_inline`."""
    css = _extract_inlined_style(assembled_editorial_validation_html)
    assert f".{layout_block_class}" in css, (
        f"layout CSS sentinel `.{layout_block_class}` missing from inlined "
        f"editorial deck CSS"
    )


def test_h2t_editorial_deck_output_section_count_matches_recipe(
    assembled_editorial_validation_html,
):
    recipe = _load_editorial_validation_recipe()
    expected = len(recipe["slides"])
    section_count = len(re.findall(
        r'<section class="slide[^"]*" data-index=',
        assembled_editorial_validation_html,
    ))
    assert section_count == expected, (
        f"Expected {expected} <section class='slide ...'> in output; "
        f"got {section_count}"
    )


# ===========================================================================
# Batch A.5 — Image asset hygiene (image-text fidelity gap)
#
# The editorial deck goldens carry no photographic content; the image-text
# layout therefore has no visual reference. Rather than smuggle a fake
# placeholder.jpg through the visual parity gate, the slice records the
# layout as a known fidelity gap in sources/references.yaml and uses a
# deterministic neutral data-URI SVG for assemble-time rendering.
#
# These tests guard:
#   - the recipe NEVER reintroduces "placeholder.jpg"
#   - every image_url in the recipe is either a data-URI OR a local asset
#     (relative path that resolves under deck/assets/)
#   - the dossier explicitly records image-text under known_fidelity_gaps
#     with parity_gate: excluded
# ===========================================================================


def _editorial_dossier() -> dict:
    return yaml.safe_load(
        _editorial_sources_path().read_text(encoding="utf-8")
    )


def test_h2t_editorial_validation_recipe_has_no_placeholder_jpg():
    """Forbid the 'placeholder.jpg' literal — that was the synthetic-evidence
    pattern Batch A.5 was created to eliminate."""
    raw = _editorial_validation_recipe_path().read_text(encoding="utf-8")
    assert "placeholder.jpg" not in raw, (
        "validation/recipe-deck.yaml must not reference 'placeholder.jpg' — "
        "use a data-URI placeholder + dossier known_fidelity_gaps entry "
        "(Batch A.5 contract)."
    )


def test_h2t_editorial_validation_recipe_image_urls_resolve_locally():
    """Every image_url in the recipe must be either:
      (a) a data: URI (self-contained), OR
      (b) a relative path that resolves under deck/assets/.
    External http(s):// URLs are forbidden — single-file deck stays local."""
    recipe = _load_editorial_validation_recipe()
    deck_assets = _editorial_deck_dir() / "assets"
    for s in recipe.get("slides", []):
        url = s.get("content", {}).get("image_url")
        if url is None:
            continue
        if url.startswith("data:"):
            continue
        assert not re.match(r"^https?://", url, re.IGNORECASE), (
            f"image_url {url!r}: external URLs forbidden in single-file deck"
        )
        # Local relative path — must exist under deck/assets/.
        candidate = deck_assets / url
        assert candidate.exists(), (
            f"image_url {url!r} does not resolve to a local asset at "
            f"{candidate}; either commit the asset or switch to a data: URI"
        )


def test_h2t_editorial_dossier_records_known_fidelity_gaps():
    """The dossier must declare a known_fidelity_gaps section so the visual
    parity gate has an authoritative list of slides to exclude."""
    data = _editorial_dossier()
    gaps = data.get("known_fidelity_gaps")
    assert isinstance(gaps, list) and gaps, (
        "sources/references.yaml must declare a non-empty "
        "known_fidelity_gaps list (Batch A.5)"
    )


def test_h2t_editorial_dossier_documents_image_text_gap():
    """image-text layout must be the recorded gap — `parity_gate: excluded`
    flips it out of T8/T9 fidelity scoring explicitly."""
    data = _editorial_dossier()
    gaps = data.get("known_fidelity_gaps", [])
    image_text_gaps = [g for g in gaps if g.get("layout") == "image-text"]
    assert image_text_gaps, (
        "known_fidelity_gaps must include an entry for layout: image-text"
    )
    entry = image_text_gaps[0]
    assert entry.get("parity_gate") == "excluded", (
        "image-text gap entry must set parity_gate: excluded so the visual "
        "parity gate at T8/T9 skips it explicitly"
    )
    assert entry.get("reason"), (
        "image-text gap entry must record a `reason` (why no golden covers it)"
    )


def test_h2t_editorial_image_text_layout_excluded_from_visual_recipe():
    """Post 2026-05-07 visual-fix batch: image-text is intentionally
    absent from the visual validation recipe (no canonical golden image
    asset to score against). The dossier `known_fidelity_gaps` entry
    still records the gap, and structural T2 tests still cover the
    layout's manifest / template / render-smoke — only the visual gate
    skips it."""
    recipe = _load_editorial_validation_recipe()
    layouts_used = [s.get("layout") for s in recipe.get("slides", [])]
    assert "image-text" not in layouts_used, (
        "image-text must not appear in the visual validation recipe"
    )


# ===========================================================================
# §9.1.10 — R2b mobile contract (Batch B / T6)
#
# Mobile is Gate B per the R2b plan — usability, not "baseline-only".
# Editorial deck CSS must declare an `@media (max-width: 480px)` block that
# adapts each component while preserving desktop fidelity OUTSIDE the block
# (Gate A). JS must not branch on viewport (CSS-only contract).
#
# These tests are TDD-red until T7 lands the implementation. Helpers are
# modeled on the R2a precedent (test_r2_legacy_fidelity.py §T14) — comments
# are stripped before brace-walking so docstrings can mention `@media`,
# `display: none`, etc. without poisoning the parsers.
# ===========================================================================


_EDITORIAL_LAYOUTS = (
    "title", "title-body", "quote", "two-column",
    "image-text", "divider", "final",
)


_CSS_COMMENT_RE_R2B = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_css_comments_r2b(css: str) -> str:
    """Strip `/* ... */` blocks before structural CSS parsing."""
    return _CSS_COMMENT_RE_R2B.sub("", css)


def _all_editorial_deck_css() -> str:
    """Concatenate every CSS file shipped under deck/ for h2t-editorial.

    Order matches `_build_deck_css_inline` (tokens → palette → frame → per-layout)
    so the parsers see CSS in the same shape as the assembled output. Comments
    are stripped because docstrings legitimately mention `@media`, `display:
    none`, etc."""
    deck = _editorial_deck_dir()
    parts = [
        (deck / "tokens.css").read_text(encoding="utf-8"),
        (deck / "palettes" / "default.css").read_text(encoding="utf-8"),
        (deck / "frame" / "frame.css").read_text(encoding="utf-8"),
    ]
    for layout in _EDITORIAL_LAYOUTS:
        parts.append(
            (deck / "slides" / layout / f"{layout}.css").read_text(encoding="utf-8")
        )
    return _strip_css_comments_r2b("\n".join(parts))


def _extract_media_blocks_r2b(css: str, query_pattern: str) -> list:
    """Return inner content of every `@media (<query_pattern>)` block."""
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


def _editorial_css_outside_media() -> str:
    """Return the editorial deck CSS with every @media block stripped."""
    css = _all_editorial_deck_css()
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


def _editorial_mobile_block_text() -> str:
    return "\n".join(
        _extract_media_blocks_r2b(
            _all_editorial_deck_css(), r"\s*max-width:\s*480px\s*"
        )
    )


def _iter_rules_r2b(css: str):
    """Yield (selector, body) for top-level CSS rules in flat (non-nested)
    deck CSS. Skips whitespace and comments."""
    i = 0
    n = len(css)
    while i < n:
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


def _has_editorial_mobile_rule(selector_pattern: str, decl_pattern: str) -> bool:
    block = _editorial_mobile_block_text()
    sel_re = re.compile(selector_pattern)
    decl_re = re.compile(decl_pattern)
    for sel, body in _iter_rules_r2b(block):
        for raw in sel.split(","):
            if sel_re.search(raw) and decl_re.search(body):
                return True
    return False


# --- §9.1.10.1 mobile breakpoint must exist ---


def test_h2t_editorial_deck_mobile_breakpoint_present():
    """Editorial deck CSS must contain at least one
    `@media (max-width: 480px)` block (R2b plan §6 mobile contract — Gate B)."""
    blocks = _extract_media_blocks_r2b(
        _all_editorial_deck_css(), r"\s*max-width:\s*480px\s*"
    )
    assert blocks, (
        "Editorial deck CSS must contain a `@media (max-width: 480px)` "
        "block (R2b T7)."
    )


# --- §9.1.10.2 desktop invariants must remain OUTSIDE @media ---


_EDITORIAL_DESKTOP_INVARIANTS = [
    # (label, selector substring, declaration substring)
    # System B canonical sizes — rejuve-pitch-deck values.
    # Title slide is the BRAND wordmark cover (.brand 58px Playfair); not h1.
    ("brand-wordmark-size",  ".title-block .brand",            "font-size: 58px"),
    ("final-h1-size",        ".final-block h1",                "font-size: 42px"),
    ("divider-h1-size",      ".divider-block h1",              "font-size: 42px"),
    ("quote-block-size",     ".quote-slide .quote-block",      "font-size: 18.5px"),
    ("two-col-grid",         ".two-column-block .two-col",
                              "grid-template-columns: 1fr 1fr"),
]


@pytest.mark.parametrize(
    "label,selector_substring,decl_substring",
    _EDITORIAL_DESKTOP_INVARIANTS,
    ids=[t[0] for t in _EDITORIAL_DESKTOP_INVARIANTS],
)
def test_h2t_editorial_deck_desktop_invariant_outside_media(
    label, selector_substring, decl_substring
):
    """Authoritative desktop sizing/layout must remain OUTSIDE any @media;
    mobile rules only override under `(max-width: 480px)` (Gate A protected)."""
    css = _editorial_css_outside_media()
    for sel, body in _iter_rules_r2b(css):
        if selector_substring.strip() in sel and decl_substring in body:
            return
    pytest.fail(
        f"Desktop invariant '{label}' missing outside @media: expected "
        f"selector with {selector_substring!r} declaring {decl_substring!r}"
    )


_EDITORIAL_PADDING_TOKENS = [
    # System B canonical with the 2026-05-07 visual-fix batch update:
    # vertical sides keep the rejuve-pitch-deck literal (44 top / 58 bottom);
    # horizontal sides use `clamp(80px, 8vw, 160px)` so wider viewports
    # widen the editorial gutters proportionally rather than appearing
    # glued to the left/right edge. Combined with `align-items: center`
    # on `.slide` and a `slide-inner { max-width: 1100px }` cap, the
    # 1440 visual matches pitch-deck literal padding while 1920+ gets
    # generous breathing room.
    ("--deck-slide-padding-top",    "44px"),
    ("--deck-slide-padding-right",  "clamp(80px, 8vw, 160px)"),
    ("--deck-slide-padding-bottom", "58px"),
    ("--deck-slide-padding-left",   "clamp(80px, 8vw, 160px)"),
]


@pytest.mark.parametrize(
    "token,default_value",
    _EDITORIAL_PADDING_TOKENS,
    ids=[t[0] for t in _EDITORIAL_PADDING_TOKENS],
)
def test_h2t_editorial_deck_slide_padding_token_default_outside_media(
    token, default_value
):
    """Editorial padding tokens (64/80/96/80) must default outside any @media;
    mobile @media may override but must not relocate the canonical default."""
    css = _editorial_css_outside_media()
    pat = re.compile(rf"{re.escape(token)}\s*:\s*{re.escape(default_value)}\s*;")
    assert pat.search(css), (
        f"Expected `{token}: {default_value};` in editorial deck CSS "
        f"(outside any @media block)"
    )


# --- §9.1.10.3 mobile adaptation must cover each editorial component ---


_EDITORIAL_MOBILE_COVERAGE = [
    # (label, selector regex, declaration regex)
    # Padding adaptation: either the .slide rule re-declares padding, OR the
    # `:root` block re-declares the four `--deck-slide-padding-*` tokens
    # (R2a T17.6 token-override pattern). Accept either selector path.
    ("slide-padding",          r"\.slide\b|:root\b",
                                r"padding:\s*[^;]+|--deck-slide-padding-[a-z]+\s*:"),
    # System B title is the brand wordmark cover, not <h1>.
    ("brand-wordmark-size",    r"\.title-block\s+\.brand|\.brand\b",
                                r"font-size:\s*"),
    ("final-h1-size",          r"\.final-block\s+h1",      r"font-size:\s*"),
    ("divider-h1-size",        r"\.divider-block\s+h1",    r"font-size:\s*"),
    ("h2-size",                r"(^|\s|,)h2(\s|$|,)|-block\s+h2",
                                                            r"font-size:\s*"),
    ("two-column-stack",       r"\.two-col\b",
                                r"grid-template-columns:\s*1fr(\s|;|$)"),
    ("image-text-figure",      r"\.image-text-block\b|\.image-text-block\s+\.figure",
                                r"max-width:|width:|font-size:|margin:|flex-direction:"),
    ("quote-adapt",            r"\.quote-slide\s+\.quote-block\b|\.quote-block\b",
                                r"font-size:|padding-left:|padding:"),
    ("counter-chrome",         r"#slide-counter\b",
                                r"font-size:|top:|right:"),
    ("nav-hint-chrome",        r"#nav-hint\b",
                                r"font-size:|bottom:|right:"),
]


@pytest.mark.parametrize(
    "label,selector_pattern,decl_pattern",
    _EDITORIAL_MOBILE_COVERAGE,
    ids=[t[0] for t in _EDITORIAL_MOBILE_COVERAGE],
)
def test_h2t_editorial_deck_mobile_adaptation_covers(
    label, selector_pattern, decl_pattern
):
    """Each editorial component listed in R2b plan §6 must have a matching
    rule inside the mobile @media block. TDD-red until T7."""
    assert _has_editorial_mobile_rule(selector_pattern, decl_pattern), (
        f"Mobile coverage '{label}' missing: expected rule with selector "
        f"matching /{selector_pattern}/ and declaration matching "
        f"/{decl_pattern}/ inside @media (max-width: 480px)"
    )


# --- §9.1.10.4 mobile must not hide essential slide content ---


_EDITORIAL_ESSENTIAL_SELECTORS = [
    ".slide", ".slide-inner",
    # System B kicker primitive (replaces System A `.eyebrow`).
    ".label",
    "h1", "h2", "h3",
    ".body",
    # System B cover composition primitives.
    ".brand", ".cover-sub", ".cover-meta",
    ".rule",
    ".quote-block",
    ".two-col", ".two-col-side",
    ".sub",
]


def test_h2t_editorial_deck_mobile_no_hidden_essential_content():
    """No mobile rule may set `display: none` or `visibility: hidden` on
    essential slide content. State-based hiding via `:empty` / `:not(...)`
    is allowed (selector retains a pseudo-class — body is conditional).

    The image-text figure is documented as a known fidelity gap in
    sources/references.yaml::known_fidelity_gaps and is excluded from the
    visual parity gate, so hiding `.figure` / `.figure img` on mobile would
    be acceptable IF it were ever needed — but it is NOT in the essentials
    list, so the test simply does not gate that selector either way."""
    block = _editorial_mobile_block_text()
    for sel, body in _iter_rules_r2b(block):
        if not (
            re.search(r"display:\s*none", body)
            or re.search(r"visibility:\s*hidden", body)
        ):
            continue
        for raw in sel.split(","):
            sel_clean = raw.strip()
            if ":empty" in sel_clean or ":not(" in sel_clean:
                continue
            for essential in _EDITORIAL_ESSENTIAL_SELECTORS:
                if re.fullmatch(rf"{re.escape(essential)}(\s.*)?", sel_clean):
                    pytest.fail(
                        f"Mobile rule hides essential content: "
                        f"selector {sel_clean!r}, body {body.strip()!r}"
                    )


# --- §9.1.10.5 mobile selectors must reference known editorial vocabulary ---


_KNOWN_HTML_TAGS_R2B = {
    "html", "body", "section", "div", "main", "header", "footer", "nav",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
    "pre", "code", "span", "strong", "em", "button", "img", "a",
    "figure", "figcaption", "blockquote", "cite", "hr",
}


def test_h2t_editorial_deck_mobile_rules_use_known_selectors():
    """Mobile rules must not introduce class/id selectors absent from the
    editorial desktop CSS — keeps the mobile contract scoped to the existing
    layout vocabulary (no new components smuggled in via @media)."""
    desktop_css = _editorial_css_outside_media()
    desktop_classes = set(re.findall(r"\.[A-Za-z][\w-]*", desktop_css))
    desktop_ids = set(re.findall(r"#[A-Za-z][\w-]*", desktop_css))

    block = _editorial_mobile_block_text()
    for sel, _body in _iter_rules_r2b(block):
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
            tag_only = re.sub(r"::?[\w-]+(?:\([^)]*\))?", "", tag_only)
            tag_only = re.sub(r"[>+~*\[\]]", " ", tag_only)
            for tok in tag_only.split():
                if tok and tok.lower() not in _KNOWN_HTML_TAGS_R2B:
                    pytest.fail(
                        f"Mobile selector {raw.strip()!r} uses unknown "
                        f"tag {tok!r}"
                    )


# --- §9.1.10.6 mobile must not introduce terminal patterns ---


def test_h2t_editorial_deck_mobile_no_terminal_patterns():
    """Mobile @media must stay within editorial vocabulary — no scanline
    overlays, no monospace fonts, no terminal primitives smuggled in."""
    block = _editorial_mobile_block_text()
    block_lower = block.lower()
    for forbidden in [
        "repeating-linear-gradient",
        "body::after",
        "jetbrains mono", "fira code", "menlo", "consolas", "monospace",
        # `.stat-row` is System B canonical (pitch-deck stats grammar) —
        # not a terminal-only primitive. Only `.stat-box` (terminal stat
        # card variant) stays forbidden.
        ".code-block", ".code-prompt", ".stat-box",
        ".card-row", ".layer-num", ".layer-name", ".layer-desc",
        "cursor: crosshair",
        "@keyframes blink", "animation: blink",
    ]:
        assert forbidden not in block_lower, (
            f"Mobile @media block contains forbidden terminal pattern: "
            f"{forbidden!r}"
        )


# --- §9.1.10.7 mobile must be CSS-only (no JS viewport branching) ---


def test_h2t_editorial_deck_mobile_is_css_only_no_js_branching():
    """deck-nav.js must not branch on viewport — mobile is CSS-only.
    This re-asserts the T3 contract at the §9.1.10 level for explicit
    Gate B coverage in the mobile contract block."""
    js = _editorial_nav_js()
    assert "matchMedia" not in js
    assert "innerWidth" not in js
    assert not re.search(r"max-width\s*:\s*\d+", js), (
        "deck-nav.js must not embed CSS-style max-width queries"
    )
