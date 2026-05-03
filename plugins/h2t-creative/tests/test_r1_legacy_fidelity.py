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


# --- Task 1: Source dossiers ---

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


def test_r1_validation_recipes_exist_and_use_profile_specific_components():
    expected = {
        "h2t-graphs": {
            "hud-panel",
            "stats-bar",
            "numbers-grid",
            "chip-stack",
            "mermaid-diagram",
            "screenshot-card",
            "code-block",
            "cards-grid",
            "layers",
            "comparison-table",
        },
        "h2t-mono": {"two-column", "comparison-table"},
    }

    for profile, required_components in expected.items():
        recipe = _read_validation_recipe(profile)
        components = set(_components(recipe))
        assert required_components.issubset(components), \
            f"{profile}: missing components {required_components - components}"

        profile_dir = _profile_dir(profile)
        for component in required_components:
            assert (profile_dir / "components" / component).exists(), \
                f"{profile}/components/{component} missing"


def test_r1_validation_recipes_assemble(tmp_path):
    for profile in R1_PROFILES:
        recipe = _read_validation_recipe(profile)
        out_dir = tmp_path / profile
        _assemble_from_recipe(recipe, out_dir)

        html = (out_dir / "index.html").read_text(encoding="utf-8")
        css = (out_dir / "profile.css").read_text(encoding="utf-8")

        assert "<!doctype html>" in html.lower()
        assert len(css) > 1000


# --- Task 2: head_scripts ---

def test_profile_head_scripts_are_injected(tmp_path):
    profile_dir = _profile_dir("h2t-graphs")
    profile_yaml = profile_dir / "profile.yaml"
    original = profile_yaml.read_text(encoding="utf-8")
    marker_url = "https://cdn.example.test/demo.js"

    try:
        profile_yaml.write_text(
            original + "\nhead_scripts:\n  - " + marker_url + "\n",
            encoding="utf-8",
        )
        recipe = {
            "type": "landing",
            "profile": "h2t-graphs",
            "palette": "default",
            "title": "Head Script Test",
            "sections": [
                {"component": "hero", "content": {"headline": "Script test"}},
            ],
        }
        out = tmp_path / "hs"
        asm.assemble_landing(recipe, profile_dir, out)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert f'<script src="{marker_url}"></script>' in html
    finally:
        profile_yaml.write_text(original, encoding="utf-8")


# --- Task 3: h2t-graphs rich components ---

def test_h2t_graphs_rich_components_render_legacy_classes(tmp_path):
    recipe = {
        "type": "landing",
        "profile": "h2t-graphs",
        "palette": "default",
        "title": "Graphs R1",
        "sections": [
            {"component": "hud-panel", "content": {"tag": "PIPELINE", "title": "HUD Panel", "body": "<p>body</p>"}},
            {"component": "stats-bar", "content": {"stat1_value": "12", "stat1_label": "nodes", "stat2_value": "8", "stat2_label": "edges", "stat3_value": "3", "stat3_label": "layers"}},
            {"component": "numbers-grid", "content": {"cell1_value": "01", "cell1_label": "capture", "cell2_value": "02", "cell2_label": "parse", "cell3_value": "03", "cell3_label": "render", "cell4_value": "04", "cell4_label": "ship"}},
            {"component": "chip-stack", "content": {"chips_html": "<span class=\"chip\">Python</span>"}},
            {"component": "mermaid-diagram", "content": {"label": "GRAPH", "diagram": "graph TD\nA-->B"}},
            {"component": "screenshot-card", "content": {"image_src": "demo.png", "alt": "demo", "caption": "Ref"}},
            {"component": "code-block", "content": {"label": "CODE", "code": "h2t render"}},
            {"component": "cards-grid", "content": {"title": "Cards", "card1_title": "A", "card1_body": "a", "card2_title": "B", "card2_body": "b", "card3_title": "C", "card3_body": "c", "card4_title": "D", "card4_body": "d"}},
            {"component": "layers", "content": {"title": "Layers", "layer1_title": "S", "layer1_body": "ref", "layer2_title": "T", "layer2_body": "tok", "layer3_title": "C", "layer3_body": "comp"}},
            {"component": "comparison-table", "content": {"body_html": "<table><tr><th>A</th><th>B</th></tr></table>"}},
        ],
    }

    profile_dir = _profile_dir("h2t-graphs")
    out = tmp_path / "graphs"
    asm.assemble_landing(recipe, profile_dir, out)
    html = (out / "index.html").read_text(encoding="utf-8")
    css = (out / "profile.css").read_text(encoding="utf-8")

    for class_name in [
        "hud-panel", "section-tag", "stats-bar", "num-grid",
        "chip-stack", "mermaid-wrap", "screenshot-card",
        "code-block", "cards-grid", "layer-stack", "compare-table",
    ]:
        assert class_name in html or class_name in css, \
            f"Expected class '{class_name}' in HTML or CSS"

    assert "text-shadow: 0 0 15px var(--color-accent-glow)" in css
    assert "cursor: crosshair" in css
    assert "border-radius" not in css
    assert "mermaid.min.js" in html


# --- Task 4: h2t-graphs validation recipe guardrails ---

def test_h2t_graphs_validation_recipe_excludes_generic_shared_blocks():
    recipe = _read_validation_recipe("h2t-graphs")
    components = set(_components(recipe))
    forbidden = {"features-grid", "pricing", "testimonials", "faq", "logos"}
    assert components.isdisjoint(forbidden), \
        f"h2t-graphs validation recipe uses generic blocks: {components & forbidden}"


# --- Task 5: h2t-mono comparison components ---

def test_h2t_mono_r1_components_render_specdesigner_patterns(tmp_path):
    recipe = {
        "type": "landing",
        "profile": "h2t-mono",
        "palette": "default",
        "title": "Mono R1",
        "sections": [
            {
                "component": "two-column",
                "content": {
                    "left_label": "BEFORE",
                    "left_title": "Prompt soup",
                    "left_body": "<code>make it modern</code>",
                    "right_label": "AFTER",
                    "right_title": "Specification",
                    "right_body": '<code class="is-good">Token contract</code>',
                },
            },
            {
                "component": "comparison-table",
                "content": {
                    "body_html": '<table><tr><th>A</th><th>B</th></tr><tr><td class="is-bad">x</td><td class="is-good">y</td></tr></table>'
                },
            },
        ],
    }

    profile_dir = _profile_dir("h2t-mono")
    out = tmp_path / "mono"
    asm.assemble_landing(recipe, profile_dir, out)
    html = (out / "index.html").read_text(encoding="utf-8")
    css = (out / "profile.css").read_text(encoding="utf-8")

    assert "two-column" in html
    assert "mono-compare" in html
    assert "is-good" in html
    assert "is-bad" in html
    assert "JetBrains Mono" in css
    assert "border-radius" not in css
    assert "box-shadow" not in css
    assert "hud-panel" not in css
