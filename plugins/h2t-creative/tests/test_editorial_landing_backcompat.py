"""§T9 — backward-compat regression for the semantic landing path
(#119).

Goal: prove the semantic renderer added in #118 does NOT change the
behaviour of legacy `sections:`-format landing recipes already shipped
in the plugin (h2t-graphs, h2t-mono).

Invariants pinned here:

§1  Recipe-format partition. Active legacy landing recipes use
    `sections:`; the editorial pilot uses `blocks:`. A recipe never
    mixes the two formats.

§2  Routing pin. `assemble_landing` invokes the semantic adapter
    (`build_legacy_recipe_from_semantic`) ONLY for recipes that
    declare `blocks:`. Legacy recipes must never touch it.

§3  Byte-identity (strong form). With the semantic adapter
    monkey-patched to raise on call, every legacy landing recipe
    still assembles and produces the SAME bytes as a normal run.
    This is the strongest available no-regression statement: if any
    semantic code accidentally crept into the legacy path, this test
    fails immediately.

§4  Determinism. Two consecutive assemblies of the same recipe (legacy
    OR semantic) produce byte-identical index.html / base.css /
    profile.css. Pins that semantic path itself is deterministic.

§5  SKILL.md command examples are unchanged. `skills/landing/SKILL.md`
    still documents the legacy CLI invocation
    (`--profile <name> --type landing --recipe recipe.yaml --out ./dist`)
    and never tells authors that `blocks:` is required.

Out of scope (per user T9 scope):
- visual capture / screenshots / Agent QA       → T10
- new components, CSS, recipe edits             → none allowed unless
                                                   a regression test
                                                   exposes a real bug
- duplicating semantic_branch convergence tests → already covered
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import assembler
import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _profiles_dir() -> Path:
    return PLUGIN_ROOT / "profiles"


def _base_dir() -> Path:
    return PLUGIN_ROOT / "base"


def _legacy_landing_recipes() -> list[tuple[str, Path]]:
    """Return (profile_name, recipe_path) for every active legacy
    landing recipe in the plugin. Skipped at the test layer when a
    recipe is missing — the worktree may be a partial checkout."""
    candidates = [
        ("h2t-graphs", _profiles_dir() / "h2t-graphs" / "validation" / "recipe.yaml"),
        ("h2t-mono", _profiles_dir() / "h2t-mono" / "validation" / "recipe.yaml"),
    ]
    return [(name, path) for name, path in candidates if path.exists()]


def _editorial_recipe_path() -> Path:
    return _profiles_dir() / "h2t-editorial" / "validation" / "recipe.yaml"


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_outputs(out_dir: Path) -> dict[str, bytes]:
    """Read the three legacy-output files as bytes for byte-identity
    comparisons."""
    return {
        name: (out_dir / name).read_bytes()
        for name in ("index.html", "base.css", "profile.css")
    }


# ---------------------------------------------------------------------------
# §1 Recipe-format partition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profile,recipe_path",
    _legacy_landing_recipes(),
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_legacy_landing_recipe_uses_sections_not_blocks(profile, recipe_path):
    """Active legacy recipes (h2t-graphs, h2t-mono) must keep the
    `sections:` shape — never silently migrate them to `blocks:`. The
    editorial pilot is the only profile authorised to use the
    semantic format in v0."""
    recipe = _read_yaml(recipe_path)
    assert "sections" in recipe, (
        f"{profile} legacy recipe missing top-level `sections:` — has "
        f"it been accidentally migrated to semantic format?"
    )
    assert "blocks" not in recipe, (
        f"{profile} legacy recipe declares `blocks:` — that flips it "
        f"to the semantic path. Per #119 scope only h2t-editorial "
        f"runs through the semantic renderer in v0."
    )


def test_h2t_editorial_pilot_uses_blocks_not_sections():
    """Mirror invariant: the editorial pilot recipe is the v0
    semantic exemplar and must NOT carry `sections:`."""
    recipe_path = _editorial_recipe_path()
    if not recipe_path.exists():
        pytest.skip("editorial pilot recipe missing in worktree")
    recipe = _read_yaml(recipe_path)
    assert "blocks" in recipe
    assert "sections" not in recipe


# ---------------------------------------------------------------------------
# §2 Routing pin
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profile,recipe_path",
    _legacy_landing_recipes(),
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_legacy_recipe_does_not_invoke_semantic_adapter(profile, recipe_path, tmp_path):
    """The semantic adapter must NEVER be called when assembling a
    legacy `sections:` recipe. Patching the import inside
    `assembler.assemble_landing` would miss the actual import path
    (the function does a deferred import from `renderer.adapter`),
    so we patch the resolved symbol there."""
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent
    out = tmp_path / f"{profile}-legacy-routing"
    with patch(
        "renderer.adapter.build_legacy_recipe_from_semantic",
        side_effect=AssertionError(
            f"semantic adapter wrongly invoked for legacy {profile} recipe"
        ),
    ) as mock_adapter:
        assembler.assemble_landing(
            recipe, profile_dir, out, base_dir=_base_dir(), palette="default"
        )
        assert mock_adapter.call_count == 0, (
            f"semantic adapter was called {mock_adapter.call_count} "
            f"times during a pure legacy assembly — routing leak"
        )
    assert (out / "index.html").exists()


def test_semantic_editorial_recipe_invokes_semantic_adapter(tmp_path):
    """Mirror routing pin: the editorial recipe MUST go through the
    adapter. If it doesn't, the legacy path would reject it (no
    `sections:` key, empty body)."""
    recipe_path = _editorial_recipe_path()
    if not recipe_path.exists():
        pytest.skip("editorial pilot recipe missing in worktree")
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent
    out = tmp_path / "editorial-semantic-routing"

    # Wrap the real adapter so we can assert it was called once with
    # the recipe + profile_dir, and the legacy emit code still runs.
    from renderer import adapter as adapter_module
    real = adapter_module.build_legacy_recipe_from_semantic
    with patch.object(
        adapter_module,
        "build_legacy_recipe_from_semantic",
        wraps=real,
    ) as mock_adapter:
        assembler.assemble_landing(
            recipe, profile_dir, out, base_dir=_base_dir(), palette="default"
        )
        assert mock_adapter.call_count == 1, (
            f"semantic adapter should be called exactly once for the "
            f"editorial recipe, got {mock_adapter.call_count}"
        )
    assert (out / "index.html").exists()


# ---------------------------------------------------------------------------
# §3 Byte-identity: legacy output unchanged when adapter is disabled
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profile,recipe_path",
    _legacy_landing_recipes(),
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_legacy_output_byte_identical_with_adapter_disabled(
    profile, recipe_path, tmp_path
):
    """Strongest no-regression statement available: assemble the
    legacy recipe normally vs. with the semantic adapter patched to
    raise. The bytes must match exactly. If a semantic code path has
    leaked into the legacy path, the patched run will throw or the
    bytes will differ."""
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent

    out_normal = tmp_path / f"{profile}-normal"
    assembler.assemble_landing(
        recipe, profile_dir, out_normal, base_dir=_base_dir(), palette="default"
    )
    normal_bytes = _read_outputs(out_normal)

    out_patched = tmp_path / f"{profile}-adapter-disabled"
    with patch(
        "renderer.adapter.build_legacy_recipe_from_semantic",
        side_effect=AssertionError(
            "semantic adapter must not run for legacy recipe"
        ),
    ):
        assembler.assemble_landing(
            recipe,
            profile_dir,
            out_patched,
            base_dir=_base_dir(),
            palette="default",
        )
    patched_bytes = _read_outputs(out_patched)

    for name in ("index.html", "base.css", "profile.css"):
        assert normal_bytes[name] == patched_bytes[name], (
            f"{profile}/{name} differs between normal and "
            f"adapter-disabled runs — semantic code is leaking into "
            f"the legacy path"
        )


# ---------------------------------------------------------------------------
# §4 Determinism — same input → same bytes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profile,recipe_path",
    _legacy_landing_recipes(),
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_legacy_assembly_is_deterministic(profile, recipe_path, tmp_path):
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent
    out_a = tmp_path / f"{profile}-a"
    out_b = tmp_path / f"{profile}-b"
    for out in (out_a, out_b):
        assembler.assemble_landing(
            recipe, profile_dir, out, base_dir=_base_dir(), palette="default"
        )
    a, b = _read_outputs(out_a), _read_outputs(out_b)
    assert a == b, (
        f"{profile} legacy assembly is non-deterministic across two "
        f"runs — likely a dict-order bug in the new code path"
    )


def test_semantic_editorial_assembly_is_deterministic(tmp_path):
    recipe_path = _editorial_recipe_path()
    if not recipe_path.exists():
        pytest.skip("editorial pilot recipe missing in worktree")
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent
    out_a = tmp_path / "editorial-a"
    out_b = tmp_path / "editorial-b"
    for out in (out_a, out_b):
        assembler.assemble_landing(
            recipe, profile_dir, out, base_dir=_base_dir(), palette="default"
        )
    a, b = _read_outputs(out_a), _read_outputs(out_b)
    assert a == b, (
        "editorial semantic assembly is non-deterministic across two "
        "runs — likely a dict-order bug in semantic_parser / adapter / "
        "field_mapper"
    )


# ---------------------------------------------------------------------------
# §5 SKILL.md command examples unchanged
# ---------------------------------------------------------------------------

def _landing_skill_md() -> Path:
    return PLUGIN_ROOT / "skills" / "landing" / "SKILL.md"


def test_landing_skill_md_command_pattern_unchanged():
    """The skill that authors run reads SKILL.md as its instruction
    sheet. The command line documented there is the contract surface
    legacy authors rely on; it must keep working unchanged."""
    body = _landing_skill_md().read_text(encoding="utf-8")
    expected_cmd = (
        '$H2T_PYTHON "$ASSEMBLER" --profile <name> --type landing '
        "--recipe recipe.yaml --out ./dist"
    )
    assert expected_cmd in body, (
        "SKILL.md no longer contains the canonical landing assembler "
        "invocation. If this changed, the legacy author workflow is "
        "broken."
    )


def test_landing_skill_md_does_not_force_semantic_format():
    """Authors running `landing` should not be forced into the
    `blocks:` format. Until each profile is migrated individually,
    legacy `sections:` recipes remain first-class (G-B guardrail)."""
    body = _landing_skill_md().read_text(encoding="utf-8").lower()
    forbidden_phrases = (
        "must use blocks:",
        "blocks: is required",
        "semantic format is required",
    )
    for phrase in forbidden_phrases:
        assert phrase not in body, (
            f"SKILL.md contains {phrase!r} — backward-compat is "
            f"broken; legacy `sections:` authors lose first-class "
            f"support."
        )


# ---------------------------------------------------------------------------
# §6 Live-recipe smoke (extends test_assembler_semantic_branch.py)
# ---------------------------------------------------------------------------
# `test_assembler_semantic_branch.py` already runs h2t-graphs / h2t-mono
# smoke under skipif. Now that the recipes are guaranteed-present in
# this worktree, pin a non-skipped variant so a missing recipe is a
# hard failure rather than a silent skip.

@pytest.mark.parametrize(
    "profile,recipe_path",
    _legacy_landing_recipes(),
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_legacy_recipe_assembles_to_nonempty_outputs(profile, recipe_path, tmp_path):
    recipe = _read_yaml(recipe_path)
    profile_dir = recipe_path.parent.parent
    out = tmp_path / f"{profile}-smoke"
    assembler.assemble_landing(
        recipe, profile_dir, out, base_dir=_base_dir(), palette="default"
    )
    for name in ("index.html", "base.css", "profile.css"):
        assert (out / name).exists(), (
            f"{profile} legacy assembly missing {name}"
        )
        assert (out / name).stat().st_size > 0, (
            f"{profile} legacy assembly produced empty {name}"
        )


def test_at_least_two_legacy_landing_recipes_present():
    """Sanity-pin: this worktree must contain BOTH h2t-graphs and
    h2t-mono validation recipes. If either is missing, the regression
    suite has no legacy ground truth to compare against — that's a
    setup error, not a passable skip."""
    recipes = _legacy_landing_recipes()
    found = {name for name, _ in recipes}
    expected = {"h2t-graphs", "h2t-mono"}
    missing = expected - found
    assert not missing, (
        f"backward-compat regression requires legacy landing recipes "
        f"for {sorted(expected)}; missing: {sorted(missing)}"
    )
