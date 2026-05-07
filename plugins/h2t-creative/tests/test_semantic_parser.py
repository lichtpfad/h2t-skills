"""§T1 — semantic recipe parser.

Per architecture spec §3 (Required Protocol Change) + §4 (Universal
Landing Block Roles) + §11.2 (Landing Modes). The parser validates
syntactic shape of a YAML-loaded recipe dict and returns a typed
SemanticRecipe + Block tuple.

Out of scope for T1 (per v0 plan §4):
- Per-block-type slot validation (T3 field_mapper).
- Asset model validation (T5 asset_validator).
- Skin / component resolution (T2 skin_loader).
- Assembler integration (T4 adapter).
"""
import pytest

from renderer.semantic_parser import (
    Block,
    SemanticRecipe,
    SemanticRecipeError,
    parse_semantic_recipe,
)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def _minimal_semantic_recipe() -> dict:
    """Minimal valid semantic recipe fixture used by happy-path tests."""
    return {
        "type": "landing",
        "profile": "h2t-editorial",
        "palette": "default",
        "title": "h2t-editorial — landing",
        "blocks": [
            {"type": "hero", "title": "Heading", "subtitle": "Sub"},
            {"type": "proof", "items": [{"value": "16", "label": "primitives"}]},
            {"type": "cta", "label": "Next", "title": "Open the deck"},
        ],
    }


def test_parses_recipe_with_blocks():
    parsed = parse_semantic_recipe(_minimal_semantic_recipe())
    assert isinstance(parsed, SemanticRecipe)
    assert parsed.type == "landing"
    assert parsed.profile == "h2t-editorial"
    assert parsed.palette == "default"
    assert parsed.title == "h2t-editorial — landing"
    assert parsed.mode is None  # optional, absent in minimal fixture
    assert len(parsed.blocks) == 3


def test_parsed_blocks_are_block_dataclass_instances():
    parsed = parse_semantic_recipe(_minimal_semantic_recipe())
    for block in parsed.blocks:
        assert isinstance(block, Block)


def test_parser_returns_immutable_blocks_tuple():
    """SemanticRecipe.blocks must be a tuple — caller cannot mutate ordering."""
    parsed = parse_semantic_recipe(_minimal_semantic_recipe())
    assert isinstance(parsed.blocks, tuple)


# ---------------------------------------------------------------------------
# Mutually exclusive `blocks:` / `sections:`
# ---------------------------------------------------------------------------

def test_rejects_recipe_with_both_blocks_and_sections():
    recipe = _minimal_semantic_recipe()
    recipe["sections"] = [{"component": "hero", "content": {}}]
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value).lower()
    assert "blocks" in msg and "sections" in msg


def test_rejects_semantic_recipe_without_blocks():
    """A recipe routed to the semantic parser MUST carry `blocks:`.

    The legacy `sections:` path is handled by the existing assembler
    code; the semantic parser is only ever called when the adapter
    has detected `blocks:` — but defensive validation is still
    required (forward-compat against future routing changes)."""
    recipe = _minimal_semantic_recipe()
    del recipe["blocks"]
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    assert "blocks" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Block-level validation
# ---------------------------------------------------------------------------

def test_rejects_block_without_type():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"][1] = {"title": "no type field here"}  # missing `type`
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value).lower()
    assert "type" in msg
    assert "1" in msg  # index 1 of the offending block must be reported


def test_rejects_block_with_non_string_type():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"][0] = {"type": 42}  # int is not a valid block type
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(recipe)


def test_rejects_block_that_is_not_a_mapping():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"].append("not-a-block")
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(recipe)


def test_rejects_blocks_field_that_is_not_a_list():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"] = {"hero": {"title": "wrong shape"}}
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(recipe)


def test_accepts_empty_blocks_list():
    """Parser stays minimal — an empty `blocks: []` is syntactically
    valid. Higher gates (composition spec, pilot tests in T8) enforce
    a non-empty recipe."""
    recipe = _minimal_semantic_recipe()
    recipe["blocks"] = []
    parsed = parse_semantic_recipe(recipe)
    assert parsed.blocks == ()


# ---------------------------------------------------------------------------
# Block order / index preservation
# ---------------------------------------------------------------------------

def test_preserves_block_order_and_index():
    recipe = _minimal_semantic_recipe()
    parsed = parse_semantic_recipe(recipe)
    types_in_order = [b.type for b in parsed.blocks]
    assert types_in_order == ["hero", "proof", "cta"]
    indices = [b.index for b in parsed.blocks]
    assert indices == [0, 1, 2]


def test_block_index_reflects_position_in_recipe():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"].insert(0, {"type": "nav"})  # push other blocks down by one
    parsed = parse_semantic_recipe(recipe)
    assert [b.type for b in parsed.blocks] == ["nav", "hero", "proof", "cta"]
    assert [b.index for b in parsed.blocks] == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# v0 core block types (architecture §4 — Universal Landing Block Roles)
# ---------------------------------------------------------------------------

_KNOWN_TYPES_FROM_SPEC = [
    "nav",
    "hero",
    "proof",
    "problem",
    "solution",
    "features",
    "process",
    "comparison",
    "gallery",
    "video",
    "case_study",
    "testimonials",
    "pricing",
    "faq",
    "evidence",
    "cta",
    "footer",
]


@pytest.mark.parametrize("block_type", _KNOWN_TYPES_FROM_SPEC)
def test_validates_known_block_types_from_v0_core(block_type):
    """Every type in architecture spec §4 must parse without error."""
    recipe = {
        "type": "landing",
        "profile": "h2t-editorial",
        "palette": "default",
        "title": "T",
        "blocks": [{"type": block_type}],
    }
    parsed = parse_semantic_recipe(recipe)
    assert parsed.blocks[0].type == block_type


def test_rejects_unknown_block_type():
    recipe = {
        "type": "landing",
        "profile": "h2t-editorial",
        "palette": "default",
        "title": "T",
        "blocks": [{"type": "totally-made-up-block"}],
    }
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value)
    assert "totally-made-up-block" in msg
    # Error should also list the canonical block-type vocabulary so
    # the recipe author knows what's available.
    assert any(known in msg for known in _KNOWN_TYPES_FROM_SPEC)


# ---------------------------------------------------------------------------
# `mode:` field (architecture §11.2 — Landing Modes)
# ---------------------------------------------------------------------------

_KNOWN_MODES_FROM_SPEC = [
    "product",
    "service",
    "editorial",
    "report",
    "portfolio",
    "deck-companion",
]


@pytest.mark.parametrize("mode", _KNOWN_MODES_FROM_SPEC)
def test_supports_mode_field(mode):
    recipe = _minimal_semantic_recipe()
    recipe["mode"] = mode
    parsed = parse_semantic_recipe(recipe)
    assert parsed.mode == mode


def test_mode_is_optional_and_defaults_to_none():
    recipe = _minimal_semantic_recipe()
    assert "mode" not in recipe  # sanity-check fixture
    parsed = parse_semantic_recipe(recipe)
    assert parsed.mode is None


def test_rejects_unknown_mode():
    recipe = _minimal_semantic_recipe()
    recipe["mode"] = "transactional"  # not in §11.2
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value)
    assert "transactional" in msg
    assert any(known in msg for known in _KNOWN_MODES_FROM_SPEC)


# ---------------------------------------------------------------------------
# `assets:` block accepted but not validated (T5 owns asset validation)
# ---------------------------------------------------------------------------

def test_accepts_assets_field_but_does_not_validate():
    recipe = _minimal_semantic_recipe()
    recipe["assets"] = [
        {"id": "hero_video", "type": "video", "src": "assets/hero.mp4"},
        {"id": "studio_01", "type": "image", "src": "assets/studio-01.jpg"},
    ]
    parsed = parse_semantic_recipe(recipe)
    assert len(parsed.assets) == 2
    # Parser does NOT enforce asset rules (alt required, video poster
    # required, etc.) — that's T5 asset_validator scope.
    assert parsed.assets[0]["id"] == "hero_video"


def test_assets_field_is_optional():
    recipe = _minimal_semantic_recipe()
    parsed = parse_semantic_recipe(recipe)
    assert parsed.assets == ()


def test_assets_field_must_be_a_list_when_present():
    recipe = _minimal_semantic_recipe()
    recipe["assets"] = {"hero_video": {}}
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(recipe)


# ---------------------------------------------------------------------------
# Block content preservation (forward-compat for T3 field_mapper)
# ---------------------------------------------------------------------------

def test_block_content_preserves_all_fields_except_type():
    recipe = {
        "type": "landing",
        "profile": "h2t-editorial",
        "palette": "default",
        "title": "T",
        "blocks": [
            {
                "type": "hero",
                "eyebrow": "intro",
                "title": "Headline",
                "subtitle": "Sub",
                "body": "Lede",
                "actions": [{"label": "Next", "href": "#", "role": "primary"}],
                "media": {"asset": "hero_img", "role": "hero_visual"},
            }
        ],
    }
    parsed = parse_semantic_recipe(recipe)
    block = parsed.blocks[0]
    assert block.type == "hero"
    # `content` is the block dict minus the `type` key, preserved verbatim
    # for downstream consumers (T3 field_mapper, T5 asset_validator).
    assert "type" not in block.content
    assert block.content["eyebrow"] == "intro"
    assert block.content["title"] == "Headline"
    assert block.content["actions"][0]["label"] == "Next"
    assert block.content["media"]["asset"] == "hero_img"


# ---------------------------------------------------------------------------
# Top-level field defaults / required
# ---------------------------------------------------------------------------

def test_top_level_type_must_be_landing_for_v0():
    recipe = _minimal_semantic_recipe()
    recipe["type"] = "deck"
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value).lower()
    assert "type" in msg and "landing" in msg


def test_palette_defaults_to_default_when_absent():
    recipe = _minimal_semantic_recipe()
    del recipe["palette"]
    parsed = parse_semantic_recipe(recipe)
    assert parsed.palette == "default"


def test_title_defaults_to_empty_string_when_absent():
    recipe = _minimal_semantic_recipe()
    del recipe["title"]
    parsed = parse_semantic_recipe(recipe)
    assert parsed.title == ""


def test_profile_is_required():
    recipe = _minimal_semantic_recipe()
    del recipe["profile"]
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    assert "profile" in str(exc.value).lower()


def test_recipe_top_level_must_be_a_mapping():
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(["not", "a", "dict"])
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe("scalar")
    with pytest.raises(SemanticRecipeError):
        parse_semantic_recipe(None)


# ---------------------------------------------------------------------------
# Error messages carry block index + path context
# ---------------------------------------------------------------------------

def test_error_message_for_missing_block_type_carries_block_index():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"][2] = {"this": "block has no type"}
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value)
    assert "block" in msg.lower()
    assert "2" in msg  # block index 2


def test_error_message_for_unknown_block_type_carries_block_index():
    recipe = _minimal_semantic_recipe()
    recipe["blocks"][1] = {"type": "no-such-block"}
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value)
    assert "1" in msg
    assert "no-such-block" in msg


def test_error_messages_use_the_blocks_keypath():
    """The path 'blocks[N]' must appear in error context so the recipe
    author can locate the offending entry without counting list items."""
    recipe = _minimal_semantic_recipe()
    recipe["blocks"][0] = {"title": "no type"}
    with pytest.raises(SemanticRecipeError) as exc:
        parse_semantic_recipe(recipe)
    msg = str(exc.value)
    # accept either 'blocks[0]' or 'blocks: index 0' style — the key
    # is that 'blocks' + '0' co-occur in the message
    assert "blocks" in msg.lower() and "0" in msg
