"""Semantic recipe parser (T1 of v0 plan).

Pure parser: takes an already-loaded YAML dict and returns a typed
SemanticRecipe + Block tuple. No file I/O, no rendering, no skin
resolution, no asset validation, no assembler integration.

Architecture references:
- §3 Required Protocol Change — recipe top-level shape
- §4 Universal Landing Block Roles — canonical block types
- §10 Renderer v0 Scope — what this T1 implements
- §11.2 Landing Modes — `mode:` field vocabulary

Out of scope here (delegated to later slices):
- per-block-type slot validation                — T3 field_mapper
- asset model (alt / poster / fallback / role)  — T5 asset_validator
- skin / component resolution                   — T2 skin_loader
- assembler entry-point branching                — T4 adapter
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Universal Landing Block Roles — architecture spec §4. The parser
# accepts every type in this list. The renderer / skin (T2-T4) decides
# which subset a given profile actually supports.
KNOWN_BLOCK_TYPES: frozenset[str] = frozenset({
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
})

# Landing Modes — architecture spec §11.2. `mode:` is optional; when
# present it must be one of these.
KNOWN_MODES: frozenset[str] = frozenset({
    "product",
    "service",
    "editorial",
    "report",
    "portfolio",
    "deck-companion",
})


class SemanticRecipeError(ValueError):
    """Raised when a semantic recipe fails parser validation.

    Error messages always carry enough context (block index, key path)
    for the recipe author to locate the offending entry without
    re-counting list items.
    """


@dataclass(frozen=True)
class Block:
    """One parsed semantic block.

    `index` is the 0-based position in the recipe's `blocks:` list and
    is preserved through the parser so downstream errors can locate the
    block by recipe path (`blocks[index]`).

    `type` is one of `KNOWN_BLOCK_TYPES`.

    `content` carries every other field from the source block dict
    verbatim (`type` removed). Per-block-type slot validation lives in
    T3 field_mapper, not here.
    """

    index: int
    type: str
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticRecipe:
    """Parsed semantic recipe — typed, immutable view over a YAML dict.

    `blocks` is a tuple to make ordering immutable. `assets` carries
    the raw assets list verbatim (T5 owns the per-asset rules). `raw`
    is the originally-loaded dict, kept for debugging / round-tripping.
    """

    type: str
    profile: str
    palette: str
    title: str
    mode: str | None
    blocks: tuple[Block, ...]
    assets: tuple[dict[str, Any], ...]
    raw: dict[str, Any]


def parse_semantic_recipe(recipe_data: Any) -> SemanticRecipe:
    """Validate and normalise a YAML-loaded semantic recipe.

    Routing convention: the caller (T4 adapter) should only call this
    when the recipe is in semantic format (`blocks:` key present).
    The parser still validates defensively — it raises
    `SemanticRecipeError` if the recipe lacks `blocks:` or carries
    BOTH `blocks:` and `sections:`.
    """
    if not isinstance(recipe_data, dict):
        raise SemanticRecipeError(
            "recipe must be a YAML mapping at the top level, "
            f"got {type(recipe_data).__name__}"
        )

    has_blocks = "blocks" in recipe_data
    has_sections = "sections" in recipe_data

    if has_blocks and has_sections:
        raise SemanticRecipeError(
            "recipe declares BOTH 'blocks:' (semantic format) and "
            "'sections:' (legacy component format). Pick one — the "
            "two formats are mutually exclusive (architecture spec §3)."
        )
    if not has_blocks:
        raise SemanticRecipeError(
            "semantic recipe missing required 'blocks:' key. "
            "If this is a legacy component recipe, route it through "
            "the legacy assembler path instead."
        )

    # Top-level fields
    recipe_type = recipe_data.get("type")
    if recipe_type != "landing":
        raise SemanticRecipeError(
            f"recipe top-level 'type' must be 'landing' for v0, "
            f"got {recipe_type!r}. v0 does not support 'deck' via the "
            f"semantic renderer."
        )

    profile = recipe_data.get("profile")
    if not isinstance(profile, str) or not profile:
        raise SemanticRecipeError(
            f"recipe missing required 'profile:' key (or empty). "
            f"got {profile!r}"
        )

    palette = recipe_data.get("palette", "default")
    if not isinstance(palette, str):
        raise SemanticRecipeError(
            f"recipe 'palette:' must be a string, got "
            f"{type(palette).__name__}"
        )

    title = recipe_data.get("title", "")
    if not isinstance(title, str):
        raise SemanticRecipeError(
            f"recipe 'title:' must be a string, got "
            f"{type(title).__name__}"
        )

    # `mode:` is optional. Validate against known vocabulary when present.
    mode = recipe_data.get("mode")
    if mode is not None:
        if not isinstance(mode, str):
            raise SemanticRecipeError(
                f"recipe 'mode:' must be a string, got "
                f"{type(mode).__name__}"
            )
        if mode not in KNOWN_MODES:
            raise SemanticRecipeError(
                f"recipe 'mode: {mode}' is not a known landing mode. "
                f"Known modes (architecture spec §11.2): "
                f"{sorted(KNOWN_MODES)}"
            )

    # Blocks
    raw_blocks = recipe_data["blocks"]
    if not isinstance(raw_blocks, list):
        raise SemanticRecipeError(
            f"recipe 'blocks:' must be a list, got "
            f"{type(raw_blocks).__name__}"
        )
    blocks = tuple(_parse_block(item, index) for index, item in enumerate(raw_blocks))

    # Assets — accepted as opaque list; T5 asset_validator owns the
    # per-asset rules (alt required, video poster, etc.).
    raw_assets = recipe_data.get("assets")
    if raw_assets is None:
        assets: tuple[dict[str, Any], ...] = ()
    else:
        if not isinstance(raw_assets, list):
            raise SemanticRecipeError(
                f"recipe 'assets:' must be a list when present, got "
                f"{type(raw_assets).__name__}"
            )
        assets = tuple(raw_assets)

    return SemanticRecipe(
        type=recipe_type,
        profile=profile,
        palette=palette,
        title=title,
        mode=mode,
        blocks=blocks,
        assets=assets,
        raw=recipe_data,
    )


def _parse_block(item: Any, index: int) -> Block:
    """Validate a single block entry and return a Block dataclass."""
    if not isinstance(item, dict):
        raise SemanticRecipeError(
            f"blocks[{index}] must be a mapping, got "
            f"{type(item).__name__}"
        )

    if "type" not in item:
        raise SemanticRecipeError(
            f"blocks[{index}] missing required 'type' field. "
            f"Every semantic block must declare a type from the "
            f"canonical vocabulary (architecture spec §4)."
        )

    block_type = item["type"]
    if not isinstance(block_type, str):
        raise SemanticRecipeError(
            f"blocks[{index}].type must be a string, got "
            f"{type(block_type).__name__} ({block_type!r})"
        )

    if block_type not in KNOWN_BLOCK_TYPES:
        raise SemanticRecipeError(
            f"blocks[{index}].type {block_type!r} is not a known block "
            f"type. Known types (architecture spec §4 Universal "
            f"Landing Block Roles): {sorted(KNOWN_BLOCK_TYPES)}"
        )

    # Content = everything except `type`, preserved verbatim for T3.
    content = {k: v for k, v in item.items() if k != "type"}
    return Block(index=index, type=block_type, content=content)
