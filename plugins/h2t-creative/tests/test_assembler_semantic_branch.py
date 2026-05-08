"""§T4 — assembler semantic-vs-legacy adapter (#118).

Verifies:
- new semantic path: recipe with `blocks:` flows through
  semantic_parser → skin_loader → field_mapper → derived legacy
  sections → existing legacy emit code.
- backward compat: recipes with `sections:` produce the same output
  as before T4. Convergence check builds a semantic recipe + skin
  that resolves to identical content as a legacy recipe and asserts
  byte-for-byte equality of the emitted index.html and profile.css.
- error surface: missing skin mapping for a block type, both
  `blocks:` + `sections:` present, missing skin file, invalid
  block type.
- live-recipe smoke for h2t-graphs and h2t-mono (skipped if their
  validation recipes are absent in the worktree).

Out of scope (per user T4 scope):
- editorial primitive migration (T6)
- editorial skin (T7)
- editorial pilot recipe (T8)
- visual / capture / Agent QA (T10)
"""
from pathlib import Path

import pytest
import yaml

import assembler
from renderer.adapter import (
    SemanticAdapterError,
    build_legacy_recipe_from_semantic,
    derive_legacy_sections,
)
from renderer.semantic_parser import SemanticRecipeError, parse_semantic_recipe
from renderer.skin_loader import SkinLoaderError, load_skin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_semantic_profile(tmp_path: Path) -> Path:
    """Build a minimal profile with one component + one skin file.
    All artefacts live under tmp_path; no real plugin profile is
    touched."""
    profile = tmp_path / "profiles" / "test-profile"
    profile.mkdir(parents=True)

    (profile / "tokens.css").write_text(
        ":root{--ac:#aaa;--bg:#fff;}\n", encoding="utf-8"
    )

    (profile / "palettes").mkdir()
    (profile / "palettes" / "default.css").write_text(
        ":root{--accent:#abc;}\n", encoding="utf-8"
    )

    comp = profile / "components" / "simple-block"
    comp.mkdir(parents=True)
    (comp / "simple-block.html").write_text(
        '<div class="simple">{{ title }}</div>\n', encoding="utf-8"
    )
    (comp / "simple-block.css").write_text(
        ".simple{color:var(--ac);}\n", encoding="utf-8"
    )
    (comp / "manifest.yaml").write_text(
        "component: simple-block\n"
        "fields:\n"
        "  title:\n"
        "    type: text\n"
        "    required: true\n",
        encoding="utf-8",
    )

    skins = profile / "skins"
    skins.mkdir()
    (skins / "landing.yaml").write_text(
        yaml.safe_dump({
            "profile": "test-profile",
            "blocks": {
                "hero": {
                    "component": "simple-block",
                    "field_map": {"title": "title"},
                },
            },
        }),
        encoding="utf-8",
    )

    return profile


def _make_base_dir(tmp_path: Path) -> Path:
    base = tmp_path / "base"
    base.mkdir()
    (base / "reset.css").write_text("*{margin:0;padding:0;}", encoding="utf-8")
    (base / "grid.css").write_text(".grid{display:grid;}", encoding="utf-8")
    (base / "typography.css").write_text(
        "body{font:14px sans-serif;}", encoding="utf-8"
    )
    (base / "animations.css").write_text(
        "/* none */\n", encoding="utf-8"
    )
    return base


def _semantic_recipe(title: str = "Hello world") -> dict:
    return {
        "type": "landing",
        "profile": "test-profile",
        "title": "Test page",
        "blocks": [{"type": "hero", "title": title}],
    }


def _legacy_recipe(title: str = "Hello legacy") -> dict:
    return {
        "type": "landing",
        "profile": "test-profile",
        "title": "Test page",
        "sections": [
            {"component": "simple-block", "content": {"title": title}},
        ],
    }


# ---------------------------------------------------------------------------
# §1 — derive_legacy_sections (adapter unit)
# ---------------------------------------------------------------------------

def test_derive_legacy_sections_translates_block_type_to_component(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    parsed = parse_semantic_recipe(_semantic_recipe())
    skin = load_skin(profile)
    sections = derive_legacy_sections(parsed, skin)
    assert len(sections) == 1
    assert sections[0]["component"] == "simple-block"


def test_derive_legacy_sections_passes_mapped_content(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    parsed = parse_semantic_recipe(_semantic_recipe(title="One"))
    skin = load_skin(profile)
    sections = derive_legacy_sections(parsed, skin)
    assert sections[0]["content"] == {"title": "One"}


def test_derive_legacy_sections_preserves_block_order(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    # Add `proof` role to the skin (same component, different field_map source)
    skin_path = profile / "skins" / "landing.yaml"
    payload = yaml.safe_load(skin_path.read_text(encoding="utf-8"))
    payload["blocks"]["proof"] = {
        "component": "simple-block",
        "field_map": {"title": "label"},
    }
    skin_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "blocks": [
            {"type": "proof", "label": "First"},
            {"type": "hero", "title": "Second"},
            {"type": "proof", "label": "Third"},
        ],
    }
    parsed = parse_semantic_recipe(recipe)
    skin = load_skin(profile)
    sections = derive_legacy_sections(parsed, skin)
    titles = [s["content"]["title"] for s in sections]
    assert titles == ["First", "Second", "Third"]


def test_missing_skin_mapping_for_block_type_raises_clear_error(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "blocks": [{"type": "cta", "label": "no skin entry"}],
    }
    parsed = parse_semantic_recipe(recipe)
    skin = load_skin(profile)
    with pytest.raises(SemanticAdapterError) as exc:
        derive_legacy_sections(parsed, skin)
    msg = str(exc.value)
    assert "cta" in msg
    assert "test-profile" in msg
    assert "landing.yaml" in msg
    assert "0" in msg  # block index


# ---------------------------------------------------------------------------
# §2 — build_legacy_recipe_from_semantic
# ---------------------------------------------------------------------------

def test_build_legacy_recipe_strips_blocks_and_adds_sections(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    legacy = build_legacy_recipe_from_semantic(_semantic_recipe(), profile)
    assert "blocks" not in legacy
    assert "sections" in legacy
    assert isinstance(legacy["sections"], list)


def test_build_legacy_recipe_preserves_other_top_level_fields(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    recipe = _semantic_recipe()
    recipe["palette"] = "default"
    recipe["title"] = "My Title"
    recipe["mode"] = "editorial"
    legacy = build_legacy_recipe_from_semantic(recipe, profile)
    assert legacy["type"] == "landing"
    assert legacy["profile"] == "test-profile"
    assert legacy["palette"] == "default"
    assert legacy["title"] == "My Title"
    assert legacy["mode"] == "editorial"


# ---------------------------------------------------------------------------
# §3 — assemble_landing routing
# ---------------------------------------------------------------------------

def test_recipe_with_both_blocks_and_sections_rejected(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "blocks": [{"type": "hero", "title": "x"}],
        "sections": [{"component": "simple-block", "content": {"title": "x"}}],
    }
    with pytest.raises(ValueError) as exc:
        assembler.assemble_landing(recipe, profile, out, base_dir=base)
    msg = str(exc.value).lower()
    assert "blocks" in msg and "sections" in msg


def test_recipe_with_neither_blocks_nor_sections_uses_legacy_default(tmp_path):
    """Legacy `assemble_landing` defaults `sections=[]` — preserved."""
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "Empty",
    }
    assembler.assemble_landing(recipe, profile, out, base_dir=base)
    assert (out / "index.html").exists()


# ---------------------------------------------------------------------------
# §4 — End-to-end semantic assembly
# ---------------------------------------------------------------------------

def test_semantic_recipe_assembles_through_temp_skin_and_component(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    assembler.assemble_landing(_semantic_recipe(), profile, out, base_dir=base)
    assert (out / "index.html").exists()
    assert (out / "base.css").exists()
    assert (out / "profile.css").exists()


def test_assembled_index_html_carries_component_output(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    assembler.assemble_landing(_semantic_recipe(title="Lifted"), profile, out, base_dir=base)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert '<div class="simple">' in index
    assert "Lifted" in index


def test_assembled_profile_css_carries_component_css(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    assembler.assemble_landing(_semantic_recipe(), profile, out, base_dir=base)
    css = (out / "profile.css").read_text(encoding="utf-8")
    assert ".simple{color:var(--ac);}" in css


# ---------------------------------------------------------------------------
# §5 — Backward-compat byte-identity
# ---------------------------------------------------------------------------

def test_legacy_recipe_output_unchanged_for_temp_fixture(tmp_path):
    """A legacy `sections:` recipe must still produce expected output —
    the legacy code path is unmodified, so no byte change vs pre-T4."""
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    assembler.assemble_landing(_legacy_recipe(title="Legacy"), profile, out, base_dir=base)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "Legacy" in index
    css = (out / "profile.css").read_text(encoding="utf-8")
    assert ".simple{color:var(--ac);}" in css


def test_semantic_and_legacy_produce_byte_identical_output_for_same_content(tmp_path):
    """Convergence check. A semantic recipe whose skin maps it to the
    SAME component+content as a hand-written legacy recipe must emit
    byte-identical index.html, profile.css, base.css. This is the
    strongest backward-compat invariant — proves the semantic path
    adds no new emit code that could diverge from legacy."""
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)

    sem_recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "Convergence",
        "blocks": [{"type": "hero", "title": "Same content"}],
    }
    leg_recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "Convergence",
        "sections": [
            {"component": "simple-block", "content": {"title": "Same content"}},
        ],
    }

    out_sem = tmp_path / "out_sem"
    out_leg = tmp_path / "out_leg"
    assembler.assemble_landing(sem_recipe, profile, out_sem, base_dir=base)
    assembler.assemble_landing(leg_recipe, profile, out_leg, base_dir=base)

    assert (out_sem / "index.html").read_bytes() == (out_leg / "index.html").read_bytes()
    assert (out_sem / "profile.css").read_bytes() == (out_leg / "profile.css").read_bytes()
    assert (out_sem / "base.css").read_bytes() == (out_leg / "base.css").read_bytes()


# ---------------------------------------------------------------------------
# §6 — Error propagation from inner layers
# ---------------------------------------------------------------------------

def test_semantic_recipe_with_invalid_block_type_propagates_parser_error(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "blocks": [{"type": "completely-fake-block-type"}],
    }
    with pytest.raises(SemanticRecipeError):
        assembler.assemble_landing(recipe, profile, out, base_dir=base)


def test_semantic_recipe_with_no_skin_file_raises_skin_loader_error(tmp_path):
    profile = tmp_path / "profiles" / "no-skin-profile"
    profile.mkdir(parents=True)
    (profile / "tokens.css").write_text("", encoding="utf-8")
    (profile / "palettes").mkdir()
    (profile / "palettes" / "default.css").write_text("", encoding="utf-8")
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    recipe = {
        "type": "landing",
        "profile": "no-skin-profile",
        "blocks": [{"type": "hero", "title": "x"}],
    }
    with pytest.raises(SkinLoaderError) as exc:
        assembler.assemble_landing(recipe, profile, out, base_dir=base)
    assert "landing.yaml" in str(exc.value)


def test_semantic_recipe_with_unmapped_block_raises_adapter_error(tmp_path):
    profile = _make_semantic_profile(tmp_path)
    base = _make_base_dir(tmp_path)
    out = tmp_path / "out"
    # `cta` is a valid block type but skin only has `hero`
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "blocks": [{"type": "cta"}],
    }
    with pytest.raises(SemanticAdapterError) as exc:
        assembler.assemble_landing(recipe, profile, out, base_dir=base)
    assert "cta" in str(exc.value)


# ---------------------------------------------------------------------------
# §7 — Live-recipe backward-compat smoke (h2t-graphs / h2t-mono)
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """`<repo>/plugins/h2t-creative/tests/this_file.py` → <repo>."""
    return Path(__file__).resolve().parents[3]


def _h2t_graphs_landing_recipe() -> Path:
    return (
        _project_root()
        / "plugins" / "h2t-creative" / "profiles" / "h2t-graphs"
        / "validation" / "recipe.yaml"
    )


def _h2t_mono_landing_recipe() -> Path:
    return (
        _project_root()
        / "plugins" / "h2t-creative" / "profiles" / "h2t-mono"
        / "validation" / "recipe.yaml"
    )


def _real_base_dir() -> Path:
    return _project_root() / "plugins" / "h2t-creative" / "base"


@pytest.mark.skipif(
    not _h2t_graphs_landing_recipe().exists(),
    reason="h2t-graphs validation recipe missing in worktree",
)
def test_active_h2t_graphs_landing_recipe_still_assembles(tmp_path):
    recipe_path = _h2t_graphs_landing_recipe()
    profile_dir = recipe_path.parent.parent  # profiles/h2t-graphs/
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    out = tmp_path / "out"
    assembler.assemble_landing(recipe, profile_dir, out, base_dir=_real_base_dir())
    assert (out / "index.html").exists() and (out / "index.html").stat().st_size > 0
    assert (out / "profile.css").exists() and (out / "profile.css").stat().st_size > 0


@pytest.mark.skipif(
    not _h2t_mono_landing_recipe().exists(),
    reason="h2t-mono validation recipe missing in worktree",
)
def test_active_h2t_mono_landing_recipe_still_assembles(tmp_path):
    recipe_path = _h2t_mono_landing_recipe()
    profile_dir = recipe_path.parent.parent
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    out = tmp_path / "out"
    assembler.assemble_landing(recipe, profile_dir, out, base_dir=_real_base_dir())
    assert (out / "index.html").exists() and (out / "index.html").stat().st_size > 0
    assert (out / "profile.css").exists() and (out / "profile.css").stat().st_size > 0
