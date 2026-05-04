"""R1 legacy fidelity contracts for h2t-graphs and h2t-mono."""
from pathlib import Path

import yaml

import assembler as asm


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PLUGIN_ROOT / "profiles"

R1_PROFILES = ("h2t-graphs", "h2t-mono")


def _profile_dir(profile: str) -> Path:
    return PROFILES_DIR / profile


def _read_validation_recipe(profile: str) -> dict:
    recipe_path = _profile_dir(profile) / "validation" / "recipe.yaml"
    return yaml.safe_load(recipe_path.read_text(encoding="utf-8"))


def _components(recipe: dict) -> list[str]:
    return [section["component"] for section in recipe["sections"]]


def _assemble_from_recipe(recipe: dict, out_dir: Path) -> None:
    profile_name = recipe["profile"]
    profile_dir = PROFILES_DIR / profile_name
    palette = recipe.get("palette", "default")
    asm.assemble_landing(recipe, profile_dir, out_dir, palette=palette)


# --- Source dossiers ---

def test_r1_source_dossiers_exist():
    for profile in R1_PROFILES:
        source_dir = _profile_dir(profile) / "sources"
        assert (source_dir / "references.yaml").exists(), \
            f"{profile}/sources/references.yaml missing"
        assert (source_dir / "screenshots" / "reference-desktop.png").exists(), \
            f"{profile}/sources/screenshots/reference-desktop.png missing"


def test_h2t_graphs_source_dossier_links_legacy_sources():
    refs = yaml.safe_load(
        (_profile_dir("h2t-graphs") / "sources" / "references.yaml").read_text(encoding="utf-8")
    )
    ids = {ref["id"] for ref in refs["references"]}
    assert "graphs-live" in ids
    assert "legacy-h2t-landing" in ids


# --- h2t-graphs component inventory ---

def test_h2t_graphs_golden_components_exist():
    required = {
        "nav", "hero", "hud-panel", "mermaid-wrap", "graph-canvas",
        "compare-grid", "feature-grid", "stack-row", "code-block", "footer",
    }
    profile_dir = _profile_dir("h2t-graphs")
    for component in required:
        assert (profile_dir / "components" / component).exists(), \
            f"h2t-graphs/components/{component} missing"


def test_h2t_graphs_validation_recipe_uses_golden_components():
    required = {
        "nav", "hero", "hud-panel", "mermaid-wrap", "graph-canvas",
        "compare-grid", "feature-grid", "stack-row", "code-block", "footer",
    }
    recipe = _read_validation_recipe("h2t-graphs")
    components = set(_components(recipe))
    assert required.issubset(components), \
        f"h2t-graphs recipe missing components: {required - components}"


# --- h2t-graphs assembly ---

def test_h2t_graphs_validation_recipe_assembles(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    css = (out_dir / "profile.css").read_text(encoding="utf-8")

    assert "<!doctype html>" in html.lower()
    assert len(css) > 500


# --- h2t-graphs token contracts ---

def test_h2t_graphs_palette_has_golden_tokens(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)
    css = (out_dir / "profile.css").read_text(encoding="utf-8")

    assert "--bg:" in css
    assert "#060609" in css
    assert "--surface:" in css
    assert "#0e0e16" in css
    assert "--accent:" in css
    assert "#e94560" in css
    assert "--border:" in css
    assert "rgba(233,69,96,0.12)" in css
    assert "--sans:" in css
    assert "Inter" in css
    assert "--mono:" in css
    assert "JetBrains Mono" in css
    assert "--grid:" in css
    assert "rgba(255,255,255,0.02)" in css


# --- h2t-graphs structural contracts ---

def test_h2t_graphs_nav_is_fixed(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)
    css = (out_dir / "profile.css").read_text(encoding="utf-8")
    assert "position: fixed" in css


def test_h2t_graphs_background_grid_is_white(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)
    css = (out_dir / "profile.css").read_text(encoding="utf-8")
    assert "rgba(255,255,255,0.02)" in css


def test_h2t_graphs_mermaid_injected(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "mermaid.min.js" in html


# --- h2t-graphs forbidden patterns ---

def test_h2t_graphs_forbidden_patterns_absent(tmp_path):
    recipe = _read_validation_recipe("h2t-graphs")
    out_dir = tmp_path / "h2t-graphs"
    _assemble_from_recipe(recipe, out_dir)
    css = (out_dir / "profile.css").read_text(encoding="utf-8")
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    combined = css + html

    assert "cursor: crosshair" not in combined, "forbidden: cursor: crosshair"
    assert "mask-image" not in combined, "forbidden: mask-image"
    assert "stats-bar" not in combined, "forbidden: stats-bar"
    assert "numbers-grid" not in combined, "forbidden: numbers-grid"
    assert ".layers" not in combined, "forbidden: .layers component"
    assert "position: sticky" not in css, "forbidden: position: sticky on nav"


# --- h2t-graphs section labels ---

def test_h2t_graphs_recipe_uses_golden_section_labels():
    recipe = _read_validation_recipe("h2t-graphs")
    tags = []
    for section in recipe["sections"]:
        content = section.get("content", {})
        tag = content.get("tag", "")
        if tag:
            tags.append(tag)
    golden_labels = {
        "how it works", "positioning", "architecture",
        "search", "provenance", "real-time", "integrations", "stack", "access",
    }
    found = {t for t in tags}
    assert golden_labels.issubset(found), \
        f"Missing golden labels: {golden_labels - found}"


# --- head_scripts injection ---

def test_profile_head_scripts_are_injected(tmp_path):
    profile_dir = _profile_dir("h2t-graphs")
    profile_yaml = profile_dir / "profile.yaml"
    original = profile_yaml.read_text(encoding="utf-8")
    marker_url = "https://cdn.example.test/demo.js"

    try:
        profile_yaml.write_text(
            original + "\n  - " + marker_url + "\n",
            encoding="utf-8",
        )
        recipe = {
            "type": "landing",
            "profile": "h2t-graphs",
            "palette": "default",
            "title": "Head Script Test",
            "sections": [
                {"component": "hero", "content": {"headline_html": "Script test"}},
            ],
        }
        out = tmp_path / "hs"
        asm.assemble_landing(recipe, profile_dir, out)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert f'<script src="{marker_url}"></script>' in html
    finally:
        profile_yaml.write_text(original, encoding="utf-8")


# --- h2t-mono minimal assembly (unchanged profile — update separately) ---

def test_h2t_mono_validation_recipe_assembles(tmp_path):
    recipe = _read_validation_recipe("h2t-mono")
    profile_name = recipe["profile"]
    profile_dir = PROFILES_DIR / profile_name
    out_dir = tmp_path / "h2t-mono"
    palette = recipe.get("palette", "default")
    asm.assemble_landing(recipe, profile_dir, out_dir, palette=palette)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    css = (out_dir / "profile.css").read_text(encoding="utf-8")

    assert "<!doctype html>" in html.lower()
    assert len(css) > 500
