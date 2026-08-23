"""§T2 — skin mapping loader.

Per architecture spec §8 (Skin Mapping). The skin loader takes a
profile_dir + format and returns a typed Skin with per-role
BlockMapping. Role names are validated against the KNOWN_BLOCK_TYPES
vocabulary established in T1 (architecture spec §4).

Out of scope for T2 (per v0 plan + user scope refinement):
- Component existence verification (`profile_dir/components/<name>`)
  — deferred; loader does not touch the filesystem beyond the skin
  file itself.
- Default-skin fallback (`h2t-default` resolution) — deferred.
- Field-mapping syntax interpretation (`${helper(...)}`,
  `path[idx].sub` paths) — T3 field_mapper.
- Asset / palette resolution — separate slices.
- Assembler integration — T4.
"""
from pathlib import Path

import pytest
import yaml
from renderer.semantic_parser import KNOWN_BLOCK_TYPES
from renderer.skin_loader import (
    BlockMapping,
    Skin,
    SkinLoaderError,
    load_skin,
    parse_skin,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_skin_yaml() -> dict:
    """Minimal valid skin fixture — used as a raw dict for parse_skin
    or written to disk for load_skin via tmp_path."""
    return {
        "profile": "test-profile",
        "blocks": {
            "hero": {"component": "page-header"},
            "proof": {"component": "stats"},
            "cta": {"component": "editorial-cta"},
        },
    }


def _write_skin(profile_dir: Path, fmt: str, payload: dict) -> Path:
    skins_dir = profile_dir / "skins"
    skins_dir.mkdir(parents=True, exist_ok=True)
    path = skins_dir / f"{fmt}.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


@pytest.fixture
def temp_profile(tmp_path):
    """An empty profile directory. Tests write skins/<format>.yaml
    into it; no real plugin profile is touched."""
    p = tmp_path / "profiles" / "test-profile"
    p.mkdir(parents=True)
    return p


# ---------------------------------------------------------------------------
# Happy path — load_skin from disk
# ---------------------------------------------------------------------------

def test_loads_landing_skin_from_profile_dir(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile, format="landing")
    assert isinstance(skin, Skin)
    assert skin.profile == "test-profile"
    assert skin.format == "landing"
    assert set(skin.blocks.keys()) == {"hero", "proof", "cta"}


def test_load_skin_default_format_is_landing(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)  # no format= argument
    assert skin.format == "landing"


def test_load_skin_returns_block_mapping_dataclass(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    for mapping in skin.blocks.values():
        assert isinstance(mapping, BlockMapping)
        assert mapping.component  # non-empty


def test_load_skin_block_mapping_carries_role(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].role == "hero"
    assert skin.blocks["proof"].role == "proof"


# ---------------------------------------------------------------------------
# Format gate — v0 supports `landing` only
# ---------------------------------------------------------------------------

def test_supports_only_landing_format_for_v0(temp_profile):
    _write_skin(temp_profile, "deck", _minimal_skin_yaml())
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="deck")
    msg = str(exc.value).lower()
    assert "landing" in msg
    assert "deck" in msg


@pytest.mark.parametrize("bad_format", ["report", "portfolio", "weekly", ""])
def test_rejects_unknown_top_level_format(temp_profile, bad_format):
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format=bad_format)
    assert "landing" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Missing / malformed file
# ---------------------------------------------------------------------------

def test_rejects_missing_skin_file_with_clear_path(temp_profile):
    """No skins/<format>.yaml has been written into temp_profile yet."""
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    msg = str(exc.value)
    assert "skins" in msg or "skin" in msg.lower()
    assert "landing.yaml" in msg
    # Path must include the profile directory so the recipe author can
    # cd / Read directly.
    assert str(temp_profile) in msg or temp_profile.name in msg


def test_rejects_non_mapping_yaml(temp_profile):
    skins_dir = temp_profile / "skins"
    skins_dir.mkdir(parents=True, exist_ok=True)
    (skins_dir / "landing.yaml").write_text("- this\n- is\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    assert "mapping" in str(exc.value).lower() or "dict" in str(exc.value).lower()


def test_rejects_empty_yaml_file(temp_profile):
    skins_dir = temp_profile / "skins"
    skins_dir.mkdir(parents=True, exist_ok=True)
    (skins_dir / "landing.yaml").write_text("", encoding="utf-8")
    with pytest.raises(SkinLoaderError):
        load_skin(temp_profile, format="landing")


# ---------------------------------------------------------------------------
# `blocks:` key — required and shaped
# ---------------------------------------------------------------------------

def test_rejects_skin_missing_blocks_key(temp_profile):
    payload = _minimal_skin_yaml()
    del payload["blocks"]
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    assert "blocks" in str(exc.value).lower()


def test_rejects_blocks_field_that_is_not_a_mapping(temp_profile):
    payload = _minimal_skin_yaml()
    payload["blocks"] = ["hero", "proof"]
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    assert "blocks" in str(exc.value).lower()


def test_accepts_empty_blocks_mapping(temp_profile):
    """An empty `blocks: {}` is syntactically valid. Higher gates
    (semantic parser, pilot tests) catch the "skin maps no roles"
    case at recipe-resolution time."""
    payload = _minimal_skin_yaml()
    payload["blocks"] = {}
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile, format="landing")
    assert skin.blocks == {}


# ---------------------------------------------------------------------------
# Role-name validation against KNOWN_BLOCK_TYPES (architecture §4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", sorted(KNOWN_BLOCK_TYPES))
def test_validates_role_names_against_known_block_types(temp_profile, role):
    payload = {
        "profile": "test-profile",
        "blocks": {role: {"component": "any-component"}},
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile, format="landing")
    assert skin.blocks[role].component == "any-component"


def test_rejects_unknown_role_name(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {"component": "page-header"},
            "totally-made-up-role": {"component": "foo"},
        },
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    msg = str(exc.value)
    assert "totally-made-up-role" in msg
    assert any(known in msg for known in sorted(KNOWN_BLOCK_TYPES))


# ---------------------------------------------------------------------------
# Per-mapping shape: `component:` required; rest optional
# ---------------------------------------------------------------------------

def test_each_mapping_requires_component(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {"variant": "compact"},  # no `component:`
        },
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    msg = str(exc.value).lower()
    assert "component" in msg
    assert "hero" in msg


def test_rejects_mapping_with_non_string_component(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {"hero": {"component": 42}},
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError):
        load_skin(temp_profile, format="landing")


def test_rejects_mapping_that_is_not_a_dict(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {"hero": "page-header"},  # string instead of dict
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError):
        load_skin(temp_profile, format="landing")


# ---------------------------------------------------------------------------
# Optional fields: variant, field_map, mobile_representation accepted raw
# ---------------------------------------------------------------------------

def test_optional_variant_accepted_raw(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {"component": "page-header", "variant": "editorial-compact"},
        },
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].variant == "editorial-compact"


def test_variant_defaults_to_none_when_absent(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].variant is None


def test_optional_field_map_accepted_raw(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {
                "component": "page-header",
                "field_map": {
                    "title": "title",
                    "subtitle": "meta",
                    "eyebrow": "label",
                },
            },
        },
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].field_map == {
        "title": "title",
        "subtitle": "meta",
        "eyebrow": "label",
    }


def test_field_map_preserves_helper_syntax_strings_raw(temp_profile):
    """T3 field_mapper interprets `${helper(...)}` and `path[idx]`
    syntax. The skin loader stores them verbatim."""
    payload = {
        "profile": "test-profile",
        "blocks": {
            "features": {
                "component": "card-grid",
                "field_map": {
                    "cards_html": "${render_cards(features)}",
                    "stat0": "stats[0].n",
                },
            },
        },
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    fm = skin.blocks["features"].field_map
    assert fm["cards_html"] == "${render_cards(features)}"
    assert fm["stat0"] == "stats[0].n"


def test_field_map_defaults_to_empty_dict_when_absent(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].field_map == {}


def test_optional_mobile_representation_accepted_raw(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "comparison": {
                "component": "comparison-table",
                "mobile_representation": "cards",
            },
        },
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    assert skin.blocks["comparison"].mobile_representation == "cards"


def test_mobile_representation_defaults_to_none_when_absent(temp_profile):
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    assert skin.blocks["hero"].mobile_representation is None


def test_unknown_extra_keys_preserved_in_extra(temp_profile):
    """Forward-compat: unknown per-mapping keys are preserved opaquely
    so future skin-schema additions don't require touching the loader."""
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {
                "component": "page-header",
                "presentation_options": {"lede_attached": True},
                "experimental_flag": "yes",
            },
        },
    }
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    extra = skin.blocks["hero"].extra
    assert extra["presentation_options"] == {"lede_attached": True}
    assert extra["experimental_flag"] == "yes"


# ---------------------------------------------------------------------------
# Error messages carry role / path
# ---------------------------------------------------------------------------

def test_error_for_missing_component_carries_role_name(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {
            "hero": {"component": "page-header"},
            "proof": {"variant": "no-component-here"},
        },
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    msg = str(exc.value)
    assert "proof" in msg
    assert "component" in msg.lower()


def test_error_for_unknown_role_lists_canonical_vocabulary(temp_profile):
    payload = {
        "profile": "test-profile",
        "blocks": {"weird": {"component": "x"}},
    }
    _write_skin(temp_profile, "landing", payload)
    with pytest.raises(SkinLoaderError) as exc:
        load_skin(temp_profile, format="landing")
    msg = str(exc.value)
    # Multiple canonical role names should appear so the recipe author
    # can pick a correct one without re-reading the spec.
    canonical_hits = sum(1 for k in KNOWN_BLOCK_TYPES if k in msg)
    assert canonical_hits >= 5


# ---------------------------------------------------------------------------
# parse_skin direct entry (in-memory, no disk)
# ---------------------------------------------------------------------------

def test_parse_skin_accepts_in_memory_dict():
    """parse_skin is the in-memory entry point — useful for tests and
    for callers that already hold a parsed YAML dict."""
    skin = parse_skin(_minimal_skin_yaml(), format="landing")
    assert isinstance(skin, Skin)
    assert skin.format == "landing"
    assert "hero" in skin.blocks


def test_parse_skin_validates_format_argument():
    with pytest.raises(SkinLoaderError):
        parse_skin(_minimal_skin_yaml(), format="deck")


# ---------------------------------------------------------------------------
# Skin object immutability
# ---------------------------------------------------------------------------

def test_skin_blocks_is_a_plain_dict_with_immutable_block_mapping(temp_profile):
    """Skin.blocks is a regular dict (intentional — Python lacks a
    frozen dict primitive). Each value is a frozen BlockMapping
    dataclass so individual mappings cannot be mutated."""
    _write_skin(temp_profile, "landing", _minimal_skin_yaml())
    skin = load_skin(temp_profile)
    mapping = skin.blocks["hero"]
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        mapping.component = "different-component"


# ---------------------------------------------------------------------------
# Cross-cutting: profile field on skin is optional metadata
# ---------------------------------------------------------------------------

def test_skin_profile_field_is_optional_in_yaml_but_default_is_dir_name(temp_profile):
    """If the skin YAML omits `profile:`, the loader fills it from the
    profile_dir name. Keeps the YAML minimal for new skins."""
    payload = {"blocks": {"hero": {"component": "page-header"}}}
    _write_skin(temp_profile, "landing", payload)
    skin = load_skin(temp_profile)
    assert skin.profile == temp_profile.name
