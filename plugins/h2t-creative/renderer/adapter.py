"""Semantic ↔ legacy assembler adapter (T4 of v0 plan).

Bridges the semantic-recipe path (semantic_parser → skin_loader →
field_mapper) into the legacy `assemble_landing` pipeline by deriving
a synthesised `sections:` list from semantic blocks. The legacy
`_build_section_html` / `_build_profile_css` path then runs unchanged.

The adapter does NOT duplicate the assembler's HTML/CSS emit code. It
rewrites the recipe dict in place (semantic shape → legacy shape) and
the existing legacy code path produces the final output. This keeps
backward-compat byte-identity trivially true: legacy recipes never
enter this module.

Out of scope:
- field-mapping syntax interpretation       — T3 field_mapper
- asset model / image+video validation      — T5 asset_validator
- additional formats (deck, dashboard)      — future slices
- skin-format dispatcher                    — v0 supports landing only
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from renderer.field_mapper import map_block_fields
from renderer.semantic_parser import SemanticRecipe, parse_semantic_recipe
from renderer.skin_loader import Skin, load_skin


class SemanticAdapterError(ValueError):
    """Raised when a semantic block's `type` has no matching skin
    mapping. Distinct from `SemanticRecipeError` (parser) and
    `SkinLoaderError` (loader) so callers can tell at which boundary
    a recipe failed."""


def derive_legacy_sections(
    recipe: SemanticRecipe, skin: Skin
) -> list[dict[str, Any]]:
    """For each Block, look up its skin mapping and map its content
    through the field_mapper. Returns a list of legacy-shape sections
    `[{"component": ..., "content": ...}, ...]` in the same order as
    `recipe.blocks`."""
    derived: list[dict[str, Any]] = []
    for block in recipe.blocks:
        if block.type not in skin.blocks:
            raise SemanticAdapterError(
                f"blocks[{block.index}] has type {block.type!r} but the "
                f"skin {skin.profile}/{skin.format}.yaml declares no "
                f"mapping for that type. Add "
                f"`blocks.{block.type}: {{component: ...}}` to "
                f"profiles/{skin.profile}/skins/{skin.format}.yaml, or "
                f"remove the block from the recipe."
            )
        mapping = skin.blocks[block.type]
        content = map_block_fields(block, mapping)
        derived.append({
            "component": mapping.component,
            "content": content,
        })
    return derived


def build_legacy_recipe_from_semantic(
    recipe_dict: dict[str, Any], profile_dir: Path
) -> dict[str, Any]:
    """Translate a semantic-format recipe dict into a legacy-format
    recipe dict (with synthesised `sections:` and `blocks:` removed).

    The returned dict is fed straight to the existing legacy-path
    code in `assemble_landing` — no new emit logic is added.

    All non-`blocks` top-level fields (`type`, `profile`, `palette`,
    `title`, `mode`, `assets`, …) are preserved.
    """
    parsed = parse_semantic_recipe(recipe_dict)
    skin = load_skin(profile_dir, format="landing")
    derived_sections = derive_legacy_sections(parsed, skin)

    legacy_recipe: dict[str, Any] = {
        k: v for k, v in recipe_dict.items() if k != "blocks"
    }
    legacy_recipe["sections"] = derived_sections
    return legacy_recipe
