"""§T6 — editorial landing primitives migration (#119).

Verifies that the primitives required for the semantic-pilot landing
have been migrated from the rejected #88 sandbox into this branch
without dragging along the appendix-only primitives or the failed
recipe / build / capture artefacts.

Migration scope (per user T6):
- tokens.css: System B-Landing token layer + global typography reset
- sources/landing-references.yaml (T0.5 source arbitration verdict)
- 4 specs: arbitration / design-system / composition-spec / rhythm-spec
- 7 components: page-header, section (RESET), card-grid, stats,
  comparison-table (with dual-rep), flow, editorial-cta

Forbidden in pilot scope:
- decomposition-table, prohibition-table, wave-block, comp-box, disc,
  meta-box, tags, ck/composed-brand-card, mmap, pos-grid, tabs (as
  landing nav)
- failed recipe-landing.yaml from r2b-landing
- failed dist/ outputs
- failed screenshots used as positive evidence

Out of scope here:
- semantic recipe (T8)
- build / capture (T10)
- assembler integration changes
- editorial skin (T7)
"""
import re
from pathlib import Path

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PLUGIN_ROOT / "profiles"
REPO_ROOT = PLUGIN_ROOT.parents[1]


def _editorial() -> Path:
    return PROFILES_DIR / "h2t-editorial"


def _components_dir() -> Path:
    return _editorial() / "components"


def _component_files(name: str) -> dict[str, Path]:
    d = _components_dir() / name
    return {
        "dir": d,
        "html": d / f"{name}.html",
        "css": d / f"{name}.css",
        "manifest": d / "manifest.yaml",
    }


def _tokens_css() -> Path:
    return _editorial() / "tokens.css"


# ===========================================================================
# §1 Source dossier — landing-references.yaml + arbitration verdict
# ===========================================================================

_DOSSIER = _editorial() / "sources" / "landing-references.yaml"


def test_landing_dossier_exists():
    assert _DOSSIER.exists(), (
        "expected profiles/h2t-editorial/sources/landing-references.yaml "
        "(T0.5 source arbitration verdict, migrated from r2b-landing)"
    )


def test_landing_dossier_parses():
    data = yaml.safe_load(_DOSSIER.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_landing_dossier_carries_form_landing_metadata():
    data = yaml.safe_load(_DOSSIER.read_text(encoding="utf-8"))
    assert data.get("profile") == "h2t-editorial"
    assert data.get("form") == "landing"
    assert data.get("visual_system") == "B-landing"


def test_landing_dossier_records_arbitration_verdict():
    data = yaml.safe_load(_DOSSIER.read_text(encoding="utf-8"))
    arb = data.get("arbitration", {})
    assert arb.get("step") == "T0.5"
    assert arb.get("conflict_detected") is False
    assert "decision" in arb and arb["decision"]
    assert arb.get("date") == "2026-05-07"


_EXPECTED_SOURCE_IDS = frozenset({
    "rejuve-appendix-competitive-report",
    "rejuve-appendix-elpodium-decomposition",
    "rejuve-pitch-deck",
})


def test_landing_dossier_lists_all_three_sources():
    data = yaml.safe_load(_DOSSIER.read_text(encoding="utf-8"))
    ids = {s["id"] for s in data.get("sources", [])}
    assert ids == _EXPECTED_SOURCE_IDS


@pytest.mark.parametrize("source_id,role", [
    ("rejuve-appendix-competitive-report", "primary"),
    ("rejuve-appendix-elpodium-decomposition", "secondary"),
    ("rejuve-pitch-deck", "contract-only"),
])
def test_landing_dossier_role_matches_arbitration(source_id, role):
    data = yaml.safe_load(_DOSSIER.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in data["sources"]}
    assert by_id[source_id]["role"] == role


# ===========================================================================
# §2 System B-Landing tokens layered + R1 tokens preserved
# ===========================================================================

_SYSTEM_B_TOKENS = [
    ("--ac", "#c9a96e"),
    ("--ad", "#8a6520"),
    ("--bg", "#fafaf8"),
    ("--sf", "#f5f3ee"),
    ("--bd", "#e0dbd3"),
    ("--tx", "#1a1a18"),
    ("--mu", "#666"),
    ("--gr", "#3d6b4a"),
    ("--dn", "#cc2222"),
    ("--bl", "#2255aa"),
    ("--pu", "#882299"),
]


@pytest.mark.parametrize("token,value", _SYSTEM_B_TOKENS)
def test_tokens_css_declares_system_b_landing_token(token, value):
    css = _tokens_css().read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;")
    assert pattern.search(css), (
        f"tokens.css missing System B-Landing token {token}: {value};"
    )


def test_tokens_css_declares_radius_token():
    css = _tokens_css().read_text(encoding="utf-8")
    assert re.search(r"--r\s*:\s*6px\s*;", css)


def test_tokens_css_declares_serif_chain():
    css = _tokens_css().read_text(encoding="utf-8")
    assert "--serif:" in css
    assert "Playfair" in css and "Georgia" in css


def test_tokens_css_declares_sans_chain():
    css = _tokens_css().read_text(encoding="utf-8")
    assert "--sans:" in css
    assert "system-ui" in css.lower() or "BlinkMacSystemFont" in css


@pytest.mark.parametrize("alias,canonical", [
    ("--w1", "--gr"),
    ("--w2", "--bl"),
    ("--w3", "--pu"),
])
def test_tokens_css_declares_wave_alias(alias, canonical):
    """Wave aliases let comparison-table lift elpodium golden CSS
    verbatim (`var(--w1)` etc.) — see #88 design-system §10."""
    css = _tokens_css().read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(alias)}\s*:\s*var\(\s*{re.escape(canonical)}\s*\)\s*;"
    )
    assert pattern.search(css), (
        f"tokens.css missing wave alias {alias}: var({canonical});"
    )


# Global typography reset (Batch C.1 fix) — required so primitive
# CSS isn't beaten by base.css R1 globals.
def test_tokens_css_declares_global_h1_reset():
    css = _tokens_css().read_text(encoding="utf-8")
    # Look for the System B-Landing h1: 28px / serif / --ad combo
    block = re.search(r"h1\s*\{[^}]+\}", css, re.DOTALL)
    assert block, "tokens.css must declare a global h1 reset"
    body = block.group(0)
    assert "28px" in body
    assert "var(--serif)" in body or "Playfair" in body
    assert "var(--ad)" in body


def test_tokens_css_declares_global_h2_reset():
    css = _tokens_css().read_text(encoding="utf-8")
    block = re.search(r"h2\s*\{[^}]+\}", css, re.DOTALL)
    assert block, "tokens.css must declare a global h2 reset"
    body = block.group(0)
    assert "20px" in body
    assert "var(--ad)" in body


def test_tokens_css_declares_body_centered_container():
    """System B-Landing body acts as the .page wrapper analog."""
    css = _tokens_css().read_text(encoding="utf-8")
    # Find the SECOND `body { ... }` block (the System B-Landing layer
    # comes after the R1 body block).
    body_blocks = re.findall(r"body\s*\{[^}]+\}", css, re.DOTALL)
    assert len(body_blocks) >= 2, (
        "tokens.css must carry both the R1 body rule (preserved) and "
        "the System B-Landing body rule (added)"
    )
    sysb_body = body_blocks[-1]
    assert "max-width" in sysb_body and "1100px" in sysb_body
    assert "margin" in sysb_body and "auto" in sysb_body
    assert "padding" in sysb_body
    assert "var(--bg)" in sysb_body
    assert "var(--sans)" in sysb_body


# R1 tokens preserved
_R1_TOKENS_PRESERVED = [
    "--font-display",
    "--font-body",
    "--font-mono",
    "--space-xs", "--space-sm", "--space-md", "--space-lg", "--space-xl",
    "--radius-sm", "--radius-md", "--radius-lg",
    "--z-bg", "--z-base", "--z-nav",
]


@pytest.mark.parametrize("token", _R1_TOKENS_PRESERVED)
def test_r1_token_still_declared(token):
    css = _tokens_css().read_text(encoding="utf-8")
    assert f"{token}:" in css, (
        f"R1 token {token} must be preserved (layer-alongside strategy)"
    )


# ===========================================================================
# §3 Approved component dirs / files / manifests exist
# ===========================================================================

_APPROVED_COMPONENTS = [
    "page-header",
    "section",
    "card-grid",
    "stats",
    "comparison-table",
    "flow",
    "editorial-cta",
]


@pytest.mark.parametrize("name", _APPROVED_COMPONENTS)
def test_component_dir_exists(name):
    files = _component_files(name)
    assert files["dir"].is_dir(), (
        f"expected components/{name}/ migrated for the pilot"
    )


@pytest.mark.parametrize("name", _APPROVED_COMPONENTS)
def test_component_template_exists(name):
    p = _component_files(name)["html"]
    assert p.exists() and p.stat().st_size > 0


@pytest.mark.parametrize("name", _APPROVED_COMPONENTS)
def test_component_css_exists(name):
    p = _component_files(name)["css"]
    assert p.exists() and p.stat().st_size > 0


@pytest.mark.parametrize("name", _APPROVED_COMPONENTS)
def test_component_manifest_exists_with_correct_component_field(name):
    p = _component_files(name)["manifest"]
    assert p.exists()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data["component"] == name


# ===========================================================================
# §4 Approved golden classes present in component CSS
# ===========================================================================

# Per-component golden class fragments (lifted from the design-system §10).
_COMPONENT_CLASSES = {
    "page-header": [".ph", ".ph-meta"],
    "section": [".section"],
    "card-grid": [".card", ".g2", ".g3", ".g4"],
    "stats": [".stat", ".stat-n", ".stat-l"],
    "comparison-table": [".bt", ".bt th", ".bt td", ".bt tr.rejuve"],
    "flow": [".flow", ".flow-step", ".flow-num", ".flow-body", ".flow-title", ".flow-desc", ".flow-sep"],
    "editorial-cta": [".editorial-cta", ".editorial-cta__label", ".editorial-cta__title", ".editorial-cta__primary"],
}


@pytest.mark.parametrize("component,css_class", [
    (c, klass)
    for c, klasses in _COMPONENT_CLASSES.items()
    for klass in klasses
])
def test_component_css_declares_golden_class(component, css_class):
    css = _component_files(component)["css"].read_text(encoding="utf-8")
    assert css_class in css, (
        f"components/{component}/{component}.css missing golden class "
        f"{css_class!r}"
    )


# ===========================================================================
# §5 Forbidden appendix-only / image-bearing components ABSENT
# ===========================================================================

_FORBIDDEN_COMPONENTS = [
    "decomposition-table",
    "prohibition-table",
    "wave-block",
    "comp-box",
    "disc",
    "meta-box",
    "tags",         # CSS family — out of pilot scope (no inline tag use)
    "mmap",         # categorisation primitive — not in pilot block inventory
    "pos-grid",     # differentiation primitive — not in pilot block inventory
    "ck",           # image-bearing brand cards — image policy unresolved
    "composed-brand-card",  # alternative naming
    "tabs",         # not used in pilot — single-tab tabs forbidden
]


@pytest.mark.parametrize("forbidden", _FORBIDDEN_COMPONENTS)
def test_forbidden_component_dir_absent(forbidden):
    """T6 migrates ONLY the 7 approved primitives. Appendix-only
    primitives + image-bearing primitives + landing-shape mismatched
    primitives stay on `codex/r2b-editorial-landing` as negative
    evidence."""
    d = _components_dir() / forbidden
    assert not d.exists(), (
        f"components/{forbidden}/ must NOT be migrated to the pilot. "
        f"Per #119 T6 scope, only 7 primitives migrate; the rest stay "
        f"on codex/r2b-editorial-landing as negative evidence."
    )


# ===========================================================================
# §6 Deck-token leakage — none of the 7 components reference deck-only tokens
# ===========================================================================

_DECK_ONLY_TOKENS = ["--fh", "--fb", "--fu"]


@pytest.mark.parametrize("component,deck_token", [
    (c, dt) for c in _APPROVED_COMPONENTS for dt in _DECK_ONLY_TOKENS
])
def test_component_css_no_deck_token_leak(component, deck_token):
    css = _component_files(component)["css"].read_text(encoding="utf-8")
    assert deck_token not in css, (
        f"components/{component}/{component}.css references deck-only "
        f"token {deck_token!r} — landing form has its own token namespace"
    )


def test_tokens_css_no_deck_token_leakage():
    css = _tokens_css().read_text(encoding="utf-8")
    for deck_token in _DECK_ONLY_TOKENS:
        assert f"{deck_token}:" not in css, (
            f"tokens.css declares deck-only token {deck_token!r}"
        )


# ===========================================================================
# §7 Comparison-table dual representation (dual-rep — desktop + mobile cards)
# ===========================================================================

def test_comparison_table_css_declares_bt_cards_rule():
    """Per rhythm spec §A.4 + #119 T6 scope: comparison block ships
    BOTH desktop `.bt` and mobile `.bt-cards`. No horizontal scroll
    on mobile."""
    css = _component_files("comparison-table")["css"].read_text(encoding="utf-8")
    assert ".bt-cards" in css, (
        "comparison-table.css must declare `.bt-cards` for the mobile "
        "stacked-card representation (rhythm spec §A.4)"
    )


def test_comparison_table_css_declares_bt_card_inner():
    css = _component_files("comparison-table")["css"].read_text(encoding="utf-8")
    assert ".bt-card" in css, (
        "comparison-table.css must declare `.bt-card` for the mobile "
        "per-row card primitive"
    )


def test_comparison_table_css_carries_max_width_480_breakpoint():
    """Mobile representation switch happens at the standard
    `@media (max-width: 480px)` breakpoint (System B-Landing
    convention shared with R2a deck dual-rep)."""
    css = _component_files("comparison-table")["css"].read_text(encoding="utf-8")
    pattern = re.compile(r"@media\s*\(\s*max-width\s*:\s*480px\s*\)")
    assert pattern.search(css), (
        "comparison-table.css must carry @media (max-width:480px) for "
        "mobile representation switch"
    )


def test_comparison_table_mobile_hides_bt_and_shows_bt_cards():
    """Inside the @media block, `.bt` hides and `.bt-cards` shows."""
    css = _component_files("comparison-table")["css"].read_text(encoding="utf-8")
    media_match = re.search(
        r"@media\s*\(\s*max-width\s*:\s*480px\s*\)\s*\{(?P<body>.+?)\n\}",
        css,
        re.DOTALL,
    )
    assert media_match, "expected @media (max-width:480px) block"
    media_body = media_match.group("body")
    # Either explicit display:none on .bt + display:block on .bt-cards,
    # or any equivalent CSS that toggles visibility.
    assert ".bt" in media_body, "@media block must reference .bt"
    assert ".bt-cards" in media_body, "@media block must reference .bt-cards"
    # Sentinel: at least one display: rule lives inside the block
    assert "display" in media_body


def test_comparison_table_default_css_hides_bt_cards():
    """On desktop (outside @media), `.bt-cards` must be hidden so
    the table is the only visible representation."""
    css = _component_files("comparison-table")["css"].read_text(encoding="utf-8")
    # Strip the @media block to inspect only desktop rules
    desktop_css = re.sub(
        r"@media\s*\([^)]+\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
        "",
        css,
        flags=re.DOTALL,
    )
    # Find the .bt-cards rule (without a class compound like
    # .bt-cards-something)
    rule_match = re.search(
        r"\.bt-cards\s*\{(?P<body>[^}]+)\}",
        desktop_css,
    )
    assert rule_match, "expected `.bt-cards { ... }` rule outside @media"
    body = rule_match.group("body")
    assert "display" in body and "none" in body, (
        "default `.bt-cards` rule must hide the cards on desktop "
        "(display: none); mobile @media flips it"
    )


def test_comparison_table_template_emits_both_representations():
    """The component template must emit both <table class="bt"> and
    <div class="bt-cards"> so the recipe can populate either / both
    via field_map. Either rep can have empty content; CSS controls
    visibility per viewport."""
    html = _component_files("comparison-table")["html"].read_text(encoding="utf-8")
    assert 'class="bt"' in html, "template must render the desktop `.bt` table"
    assert 'class="bt-cards"' in html, "template must render the mobile `.bt-cards` block"


def test_comparison_table_manifest_carries_optional_cards_html_field():
    """The mobile cards content is supplied via a `tbody_cards_html`
    optional field. Default is empty string — when the recipe doesn't
    provide cards, the desktop table remains the only populated
    representation. A future slice (when comparison block lands in
    pilot) populates both."""
    data = yaml.safe_load(
        _component_files("comparison-table")["manifest"].read_text(encoding="utf-8")
    )
    fields = data.get("fields", {})
    assert "tbody_cards_html" in fields, (
        "comparison-table manifest must declare `tbody_cards_html` "
        "(mobile dual-rep field)"
    )
    cards_field = fields["tbody_cards_html"]
    assert cards_field.get("required", True) is False, (
        "tbody_cards_html must be optional so legacy single-rep recipes "
        "still work without supplying mobile content"
    )


# ===========================================================================
# §8 Doc artefacts (specs migrated)
# ===========================================================================

_VR_DIR = REPO_ROOT / "docs" / "visual-regression" / "2026-05-07-r2b"
_SPECS_DIR = REPO_ROOT / "docs" / "superpowers" / "specs"

_MIGRATED_DOCS = [
    _SPECS_DIR / "2026-05-07-r2b-landing-source-arbitration.md",
    _VR_DIR / "h2t-editorial-landing-design-system.md",
    _VR_DIR / "h2t-editorial-landing-composition-spec.md",
    _VR_DIR / "h2t-editorial-landing-rhythm-spec.md",
]


@pytest.mark.parametrize("doc", _MIGRATED_DOCS)
def test_migrated_doc_exists(doc):
    assert doc.exists(), f"expected doc migrated: {doc.relative_to(REPO_ROOT)}"


def test_design_system_doc_lists_canonical_primitive_vocabulary():
    """The migrated design-system doc keeps the full extracted
    vocabulary catalogue as a forward-compat reference, even though
    only 7 primitives are migrated as components in this slice."""
    body = (_VR_DIR / "h2t-editorial-landing-design-system.md").read_text(encoding="utf-8")
    for sentinel in (".tabs", ".ph", ".section", ".card", ".stat", ".bt", ".flow"):
        assert sentinel in body


def test_failed_recipe_landing_yaml_NOT_migrated():
    """The primitive-showcase recipe-landing.yaml from the failed #88
    sandbox is negative evidence — it must NOT appear in the pilot
    branch. Plan G-A guardrail."""
    failed_recipe = (
        _editorial() / "validation" / "recipe-landing.yaml"
    )
    assert not failed_recipe.exists(), (
        "validation/recipe-landing.yaml from r2b-landing must NOT be "
        "migrated. It's negative evidence (G-A guardrail)."
    )


def test_failed_dist_NOT_migrated():
    """No failed dist artefacts in the pilot branch."""
    failed_paths = [
        REPO_ROOT / "dist" / "r2b-h2t-editorial-landing-system-b-validation",
        REPO_ROOT / "dist" / "r2b-h2t-editorial-landing-modular",
    ]
    for p in failed_paths:
        assert not p.exists(), (
            f"failed dist {p.name} must NOT be migrated (G-A guardrail)"
        )


def test_failed_screenshots_NOT_migrated_as_positive_evidence():
    """The failed PNGs from r2b-landing must not appear in
    docs/visual-regression/ within this pilot worktree as visual gate
    artefacts. (They may live under EVIDENCE.md notes if explicitly
    referenced — that is not what this test rejects; what's rejected
    is migrated PNGs.)"""
    candidates = [
        _VR_DIR / "h2t-editorial-landing-modular" / "unknown",
        _VR_DIR / "h2t-editorial-landing-system-b-modular" / "unknown",
    ]
    for c in candidates:
        if c.exists():
            pngs = list(c.glob("*.png"))
            assert not pngs, (
                f"failed screenshots in {c} must not be migrated as "
                f"positive evidence (G-A). Reference them by branch + "
                f"sha in EVIDENCE.md instead."
            )
