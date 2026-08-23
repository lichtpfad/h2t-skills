"""§T7 — h2t-editorial landing skin (#119).

Verifies `profiles/h2t-editorial/skins/landing.yaml` shape:
- loads via skin_loader.load_skin()
- maps all 7 required roles to migrated System B-Landing primitives
- comparison block carries `mobile_representation: cards` for the
  dual-representation contract from rhythm spec §A.4
- field_map values use only paths supported by field_mapper
  (plain / nested / indexed) or helper invocations using only
  ALLOWED_HELPERS
- unsupported architecture §4 roles documented in
  `unsupported_in_v0` so future maintainers know what's deferred
- no role maps to R1 generic components (bare names hero / nav /
  cta / footer)
- every mapped component dir + manifest exists and parses

Out of scope (per user T7 scope):
- pilot recipe (T8)
- build / capture (T10)
- assembler / field_mapper / skin_loader code changes
"""
import re
from pathlib import Path

import pytest
import yaml
from renderer.field_mapper import ALLOWED_HELPERS
from renderer.semantic_parser import KNOWN_BLOCK_TYPES
from renderer.skin_loader import BlockMapping, Skin, load_skin

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _editorial_profile_dir() -> Path:
    return PLUGIN_ROOT / "profiles" / "h2t-editorial"


def _components_dir() -> Path:
    return _editorial_profile_dir() / "components"


def _skin_path() -> Path:
    return _editorial_profile_dir() / "skins" / "landing.yaml"


@pytest.fixture(scope="module")
def skin() -> Skin:
    """Loaded once per test module — skin parsing is read-only."""
    return load_skin(_editorial_profile_dir())


# ---------------------------------------------------------------------------
# §1 File exists and loads
# ---------------------------------------------------------------------------

def test_landing_skin_file_exists():
    assert _skin_path().exists(), (
        "expected profiles/h2t-editorial/skins/landing.yaml"
    )


def test_landing_skin_loads_via_skin_loader(skin):
    assert isinstance(skin, Skin)


def test_skin_profile_is_h2t_editorial(skin):
    assert skin.profile == "h2t-editorial"


def test_skin_format_is_landing(skin):
    assert skin.format == "landing"


# ---------------------------------------------------------------------------
# §2 Required roles map to expected primitives
# ---------------------------------------------------------------------------

_EXPECTED_ROLE_TO_COMPONENT = {
    "hero": "page-header",
    "proof": "stats",
    "features": "card-grid",
    "process": "flow",
    "comparison": "comparison-table",
    "evidence": "section",
    "cta": "editorial-cta",
}


@pytest.mark.parametrize("role", sorted(_EXPECTED_ROLE_TO_COMPONENT))
def test_required_role_present_in_skin(role, skin):
    assert role in skin.blocks, (
        f"required semantic role {role!r} missing from editorial "
        f"landing skin (architecture spec §13 step 4 mapping)"
    )


@pytest.mark.parametrize("role,expected", _EXPECTED_ROLE_TO_COMPONENT.items())
def test_role_maps_to_expected_component(role, expected, skin):
    assert role in skin.blocks
    assert skin.blocks[role].component == expected, (
        f"role {role!r} must map to {expected!r} (System B-Landing "
        f"primitive), got {skin.blocks[role].component!r}"
    )


def test_cta_role_explicitly_maps_to_editorial_cta_not_r1_cta(skin):
    """Hard guardrail per #119 T7 scope: cta semantic role MUST map
    to editorial-cta (the new System B-Landing extension), NOT to
    the R1 cta component which has different visual grammar."""
    assert skin.blocks["cta"].component == "editorial-cta"
    assert skin.blocks["cta"].component != "cta"


def test_hero_role_explicitly_maps_to_page_header_not_r1_hero(skin):
    """Hard guardrail per #119 T7 scope: hero semantic role MUST map
    to page-header (compact editorial header), NOT to the R1 hero
    component (marketing headline)."""
    assert skin.blocks["hero"].component == "page-header"
    assert skin.blocks["hero"].component != "hero"


# ---------------------------------------------------------------------------
# §3 No role maps to R1 generic components
# ---------------------------------------------------------------------------

_R1_GENERIC_COMPONENTS = frozenset({"hero", "nav", "cta", "footer"})


def test_no_role_maps_to_r1_generic_component(skin):
    """Per design-system §10 + composition spec §3: R1 generic
    components are out-of-scope. The skin must use the seven
    migrated System B-Landing primitives."""
    for role, mapping in skin.blocks.items():
        assert mapping.component not in _R1_GENERIC_COMPONENTS, (
            f"role {role!r} maps to R1 generic component "
            f"{mapping.component!r} — must use the System B-Landing "
            f"primitive instead"
        )


# ---------------------------------------------------------------------------
# §4 Comparison block carries mobile_representation: cards
# ---------------------------------------------------------------------------

def test_comparison_role_carries_mobile_representation_cards(skin):
    """Rhythm spec §A.4 requires landing comparison-table to switch
    to stacked cards on mobile (no horizontal scroll). The skin
    declares this via mobile_representation: cards."""
    assert skin.blocks["comparison"].mobile_representation == "cards"


# ---------------------------------------------------------------------------
# §5 Field_map values use only field_mapper-supported syntax
# ---------------------------------------------------------------------------

# Helper invocation regex matches the field_mapper grammar:
# ${ helper_name(args) } where helper_name is a bare identifier.
_HELPER_CALL_RE = re.compile(r"^\$\{(\w+)\((.*)\)\}$")
# Plain or indexed path: name, name.sub, name[0], name[0].sub, etc.
_PATH_TOKEN_RE = re.compile(
    r"^[A-Za-z_][\w\-]*(\[\d+\])?(\.[A-Za-z_][\w\-]*(\[\d+\])?)*$"
)


def _classify_field_map_value(value: str) -> str:
    """Return 'helper' / 'path' / 'invalid'."""
    if _HELPER_CALL_RE.match(value):
        return "helper"
    if _PATH_TOKEN_RE.match(value):
        return "path"
    return "invalid"


def test_all_field_map_values_have_valid_syntax(skin):
    """Every field_map value must be either a plain/indexed path or
    a helper invocation. No raw HTML, no inline values, no
    unsupported syntax — the field_mapper has a closed grammar."""
    bad: list[str] = []
    for role, mapping in skin.blocks.items():
        for target, source in mapping.field_map.items():
            if not isinstance(source, str):
                bad.append(f"{role}.{target}: non-string {source!r}")
                continue
            if _classify_field_map_value(source) == "invalid":
                bad.append(
                    f"{role}.{target}: {source!r} is neither a path "
                    f"nor a recognised helper invocation"
                )
    assert not bad, "\n  ".join(["field_map syntax errors:"] + bad)


def test_helpers_used_in_skin_are_in_allowlist(skin):
    """Every ${helper(...)} invocation in the skin must use a helper
    name in renderer.field_mapper.ALLOWED_HELPERS. Helpers outside
    the allowlist would fail at render time."""
    for role, mapping in skin.blocks.items():
        for target, source in mapping.field_map.items():
            m = _HELPER_CALL_RE.match(str(source))
            if m:
                helper_name = m.group(1)
                assert helper_name in ALLOWED_HELPERS, (
                    f"{role}.{target} invokes unknown helper "
                    f"{helper_name!r} — not in ALLOWED_HELPERS"
                )


def test_at_least_one_helper_invocation_present(skin):
    """Sanity check: the skin should use SOME helpers — otherwise
    it can't bridge structured semantic blocks (lists of items,
    rows, steps) to component-template HTML fields."""
    helper_count = 0
    for mapping in skin.blocks.values():
        for source in mapping.field_map.values():
            if _HELPER_CALL_RE.match(str(source)):
                helper_count += 1
    assert helper_count >= 3, (
        "expected ≥ 3 helper invocations in editorial skin "
        "(features→render_cards, process→render_flow_steps, "
        "comparison→render_table_head/render_table_body)"
    )


# ---------------------------------------------------------------------------
# §6 Unsupported roles documented in unsupported_in_v0
# ---------------------------------------------------------------------------

# Architecture §4 universal block roles that the editorial pilot
# does NOT implement. Either no migrated primitive exists, or the
# rhythm spec §A.9 / composition spec §4 explicitly omits them.
_REQUIRED_UNSUPPORTED_DOCUMENTATION = [
    "nav",          # single-purpose landing — no nav primitive
    "problem",      # D7 of rhythm spec — folded into hero lede
    "solution",    # D5(a) tight regime — features carries the role
    "gallery",      # image-bearing — deferred
    "video",        # media-bearing — deferred
    "case_study",   # deferred
    "testimonials", # deferred
    "pricing",      # editorial profile is non-transactional
    "faq",          # D8 — no objection cluster
    "footer",       # closing role covered by `evidence` block
]


def test_unsupported_in_v0_section_present(skin):
    raw = skin.raw
    assert "unsupported_in_v0" in raw, (
        "skin must declare an `unsupported_in_v0` mapping listing "
        "architecture §4 roles deferred for the pilot — without this "
        "future maintainers don't know what's intentionally omitted"
    )
    assert isinstance(raw["unsupported_in_v0"], dict)


@pytest.mark.parametrize("role", _REQUIRED_UNSUPPORTED_DOCUMENTATION)
def test_role_documented_as_unsupported_in_v0(role, skin):
    raw = skin.raw
    unsupported = raw.get("unsupported_in_v0") or {}
    assert role in unsupported, (
        f"role {role!r} (architecture §4 universal vocabulary) is not "
        f"mapped by this skin and must be listed in "
        f"`unsupported_in_v0` with a one-line rationale"
    )
    rationale = unsupported[role]
    assert isinstance(rationale, str) and len(rationale) >= 5, (
        f"unsupported_in_v0[{role!r}] must carry a non-empty rationale"
    )


def test_unsupported_role_names_are_valid_block_types(skin):
    """Every documented unsupported role must be a real architecture
    §4 universal block role — not a typo or made-up name."""
    raw = skin.raw
    for role in (raw.get("unsupported_in_v0") or {}):
        assert role in KNOWN_BLOCK_TYPES, (
            f"unsupported_in_v0 lists {role!r} but it's not in "
            f"KNOWN_BLOCK_TYPES (architecture §4 universal roles)"
        )


def test_unsupported_and_supported_partition_known_block_types(skin):
    """Every architecture §4 role must be either supported (in
    skin.blocks) or documented as unsupported. No silent gaps."""
    raw = skin.raw
    supported = set(skin.blocks.keys())
    unsupported = set((raw.get("unsupported_in_v0") or {}).keys())
    union = supported | unsupported
    missing = KNOWN_BLOCK_TYPES - union
    assert not missing, (
        f"architecture §4 roles {sorted(missing)} are neither mapped "
        f"in skin.blocks nor documented in unsupported_in_v0 — fix "
        f"by either adding a mapping or listing as deferred"
    )


# ---------------------------------------------------------------------------
# §7 Each mapped component dir + manifest exists
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role,component", _EXPECTED_ROLE_TO_COMPONENT.items())
def test_mapped_component_dir_exists(role, component, skin):
    comp_dir = _components_dir() / component
    assert comp_dir.is_dir(), (
        f"role {role!r} maps to component {component!r} but "
        f"{comp_dir} does not exist"
    )


@pytest.mark.parametrize("role,component", _EXPECTED_ROLE_TO_COMPONENT.items())
def test_mapped_component_manifest_parses(role, component, skin):
    manifest = _components_dir() / component / "manifest.yaml"
    assert manifest.exists()
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert data.get("component") == component


# ---------------------------------------------------------------------------
# §8 Forward-compat sanity: skin shape matches BlockMapping API
# ---------------------------------------------------------------------------

def test_skin_blocks_returns_block_mapping_dataclass(skin):
    for mapping in skin.blocks.values():
        assert isinstance(mapping, BlockMapping)


def test_comparison_field_map_uses_render_table_helpers(skin):
    """Sanity-pin the comparison mapping: thead_html and tbody_html
    must come from render_table_head / render_table_body."""
    fm = skin.blocks["comparison"].field_map
    assert "thead_html" in fm
    assert "tbody_html" in fm
    assert "render_table_head" in fm["thead_html"]
    assert "render_table_body" in fm["tbody_html"]


def test_features_field_map_uses_render_cards(skin):
    fm = skin.blocks["features"].field_map
    assert any("render_cards" in str(v) for v in fm.values())


def test_process_field_map_uses_render_flow_steps(skin):
    fm = skin.blocks["process"].field_map
    assert any("render_flow_steps" in str(v) for v in fm.values())
