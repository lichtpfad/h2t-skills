---
title: "h2t-creative R1 Legacy Fidelity Implementation Plan"
status: "draft"
date: "2026-05-04"
milestone: ""
issue: ""
---
# h2t-creative R1 Legacy Fidelity Implementation Plan

> **For executor:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.
> Follow this plan exactly. Execute TDD: write/verify failing tests first, then implement.
> Do not bump minor. R1 is recovery work and remains patch/pre-live until human visual confirmation.

## Goal

Recover the first legacy-fidelity slice for `h2t-creative`:

- `h2t-graphs`: restore the HUD/graphs visual language from `graphs.lichtpfadstudio.com` and legacy `h2t:landing`.
- `h2t-mono`: restore the specdesigner visual language for two-column code comparison and comparison table.
- Establish the fixed extraction/recovery pipeline in code and source dossiers, so future profiles follow the same standard.

## Source Of Truth

Primary specs:

- `docs/superpowers/specs/2026-05-04-h2t-creative-recovery-audit.md`
- `docs/superpowers/specs/2026-05-04-h2t-creative-recovery-spec.md`

Reference screenshots:

- `docs/visual-regression/reference/graphs.lichtpfadstudio.com/desktop_20260504_000404.png`
- `docs/visual-regression/reference/specdesigner.netlify.app/desktop_20260504_000404.png`

Legacy/source files:

- `C:/dev/h2t-landings/graphs/index.html`
- `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/landing/SKILL.md`
- `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/deck/SKILL.md`

## Environment

Use the project venv if present. Do not install anything into system Python.

Preferred commands:

```powershell
source .venv/Scripts/activate
python -m pytest plugins/h2t-creative/tests/ -q
```

If activation is not available in the executor shell, use:

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ -q
```

If `.venv` is missing, stop and ask where to create it. Do not use `pip install` outside a venv.

## Non-Goals

- Do not create generic shared replacements for recovered aesthetics.
- Do not claim visual pass without comparing against committed reference screenshots.
- Do not bump `1.2.0` to a new minor. Minor is blocked until live/human confirmation.
- Do not recover `h2t-pfad`, `h2t-terminal`, or `h2t-editorial` in R1. They are R3 follow-ups.

## Task 1: Source Dossiers And R1 Contract Tests

Create a repeatable contract for recovered profiles: each R1 profile must have a source dossier and a validation recipe.

### 1.1 Write Failing Tests

Create `plugins/h2t-creative/tests/test_r1_legacy_fidelity.py`:

```python
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


def test_r1_source_dossiers_exist():
    for profile in R1_PROFILES:
        source_dir = _profile_dir(profile) / "sources"
        assert (source_dir / "references.yaml").exists()
        assert (source_dir / "screenshots" / "reference-desktop.png").exists()


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
        assert required_components.issubset(components)

        profile_dir = _profile_dir(profile)
        for component in required_components:
            assert (profile_dir / "components" / component).exists()


def test_r1_validation_recipes_assemble(tmp_path):
    for profile in R1_PROFILES:
        recipe = _read_validation_recipe(profile)
        out_dir = tmp_path / profile
        asm.assemble_landing(recipe, out_dir=out_dir)

        html = (out_dir / "index.html").read_text(encoding="utf-8")
        css = (out_dir / "profile.css").read_text(encoding="utf-8")

        assert "<!doctype html>" in html.lower()
        assert len(css) > 1000
```

Run the targeted tests and confirm they fail because dossiers/recipes/components do not exist:

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/test_r1_legacy_fidelity.py -q
```

Expected: failures for missing `sources/`, `validation/recipe.yaml`, and component directories.

### 1.2 Implement Source Dossiers

Create:

```text
plugins/h2t-creative/profiles/h2t-graphs/sources/references.yaml
plugins/h2t-creative/profiles/h2t-graphs/sources/legacy-notes.md
plugins/h2t-creative/profiles/h2t-graphs/sources/screenshots/reference-desktop.png
plugins/h2t-creative/profiles/h2t-mono/sources/references.yaml
plugins/h2t-creative/profiles/h2t-mono/sources/legacy-notes.md
plugins/h2t-creative/profiles/h2t-mono/sources/screenshots/reference-desktop.png
```

Copy screenshots from committed references:

```powershell
New-Item -ItemType Directory -Force plugins/h2t-creative/profiles/h2t-graphs/sources/screenshots
Copy-Item docs/visual-regression/reference/graphs.lichtpfadstudio.com/desktop_20260504_000404.png plugins/h2t-creative/profiles/h2t-graphs/sources/screenshots/reference-desktop.png
New-Item -ItemType Directory -Force plugins/h2t-creative/profiles/h2t-mono/sources/screenshots
Copy-Item docs/visual-regression/reference/specdesigner.netlify.app/desktop_20260504_000404.png plugins/h2t-creative/profiles/h2t-mono/sources/screenshots/reference-desktop.png
```

`h2t-graphs/sources/references.yaml`:

```yaml
profile: h2t-graphs
status: r1-recovery-source
references:
  - id: graphs-live
    type: live-site
    url: https://graphs.lichtpfadstudio.com/
    local_source: C:/dev/h2t-landings/graphs/index.html
    screenshot: screenshots/reference-desktop.png
  - id: legacy-h2t-landing
    type: legacy-skill
    path: C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/landing/SKILL.md
visual_invariants:
  - HUD surface panels with four corner brackets
  - JetBrains Mono body/labels and Inter display headings
  - 40px fixed grid background
  - segmented stats bar with glowing accent numbers
  - chip rows with bordered monospace labels
  - Mermaid/code/screenshot panels inside HUD frames
  - no rounded cards, no generic pricing/testimonial blocks
```

`h2t-mono/sources/references.yaml`:

```yaml
profile: h2t-mono
status: r1-recovery-source
references:
  - id: specdesigner-live
    type: live-site
    url: https://specdesigner.netlify.app/
    screenshot: screenshots/reference-desktop.png
visual_invariants:
  - near-black page
  - JetBrains Mono everywhere
  - single red accent
  - two-column code comparison
  - comparison table with sparse borders and colored states
  - zero radius, zero shadows, zero decorative HUD brackets
```

`legacy-notes.md` files should summarize the visual grammar and forbidden substitutions in 20-40 lines each.

### 1.3 Commit

```powershell
git add plugins/h2t-creative/tests/test_r1_legacy_fidelity.py plugins/h2t-creative/profiles/h2t-graphs/sources plugins/h2t-creative/profiles/h2t-mono/sources
git commit -m "test(h2t-creative): add R1 legacy fidelity contracts"
```

## Task 2: Profile Head Scripts For Mermaid

R1 graphs needs Mermaid support. Implement this as a profile-level capability, not as duplicated script tags in every component.

### 2.1 Write Failing Test

Append to `test_r1_legacy_fidelity.py`:

```python
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
                {"component": "hero", "props": {"headline": "Script test"}},
            ],
        }
        asm.assemble_landing(recipe, out_dir=tmp_path)
        html = (tmp_path / "index.html").read_text(encoding="utf-8")

        assert f'<script src="{marker_url}"></script>' in html
    finally:
        profile_yaml.write_text(original, encoding="utf-8")
```

Run targeted test. Expected: fail because `head_scripts` is ignored.

### 2.2 Implement In `assembler.py`

Add a function near `_build_font_links`:

```python
def _build_head_scripts(profile_dir: Path) -> str:
    config = _load_profile_config(profile_dir)
    scripts = config.get("head_scripts", [])
    if not scripts:
        return ""

    tags = []
    for src in scripts:
        tags.append(f'<script src="{src}"></script>')
    return "\n    ".join(tags)
```

Update landing and deck templates to include:

```python
head_scripts = _build_head_scripts(profile_dir)
```

And in `<head>` after `font_links`:

```html
    {head_scripts}
```

Then update `plugins/h2t-creative/profiles/h2t-graphs/profile.yaml`:

```yaml
head_scripts:
  - https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js
```

### 2.3 Verify And Commit

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/test_r1_legacy_fidelity.py -q
git add plugins/h2t-creative/assembler.py plugins/h2t-creative/profiles/h2t-graphs/profile.yaml plugins/h2t-creative/tests/test_r1_legacy_fidelity.py
git commit -m "feat(h2t-creative): support profile head scripts"
```

## Task 3: Recover `h2t-graphs` Rich Components

Add profile-specific components. Do not put these in `shared/components`.

### 3.1 Write Failing Graphs Component Tests

Append to `test_r1_legacy_fidelity.py`:

```python
def test_h2t_graphs_rich_components_render_legacy_classes(tmp_path):
    recipe = {
        "type": "landing",
        "profile": "h2t-graphs",
        "palette": "default",
        "title": "Graphs R1",
        "sections": [
            {"component": "hud-panel", "props": {"tag": "PIPELINE", "title": "HUD Panel", "body": "<p>Panel body</p>"}},
            {"component": "stats-bar", "props": {"stat1_value": "12", "stat1_label": "nodes", "stat2_value": "8", "stat2_label": "edges", "stat3_value": "3", "stat3_label": "layers"}},
            {"component": "numbers-grid", "props": {"cell1_value": "01", "cell1_label": "capture", "cell2_value": "02", "cell2_label": "parse", "cell3_value": "03", "cell3_label": "render", "cell4_value": "04", "cell4_label": "ship"}},
            {"component": "chip-stack", "props": {"chips_html": "<span class=\"chip hi\">Python</span><span class=\"chip\">Mermaid</span>"}},
            {"component": "mermaid-diagram", "props": {"label": "GRAPH", "diagram": "graph TD\\nA-->B"}},
            {"component": "screenshot-card", "props": {"image_src": "demo.png", "alt": "demo", "caption": "Reference capture"}},
            {"component": "code-block", "props": {"label": "CODE", "code": "h2t render --profile h2t-graphs"}},
            {"component": "cards-grid", "props": {"title": "Cards", "card1_title": "Extract", "card1_body": "Source first", "card2_title": "Map", "card2_body": "Tokens", "card3_title": "Render", "card3_body": "Components", "card4_title": "Gate", "card4_body": "Visual"}},
            {"component": "layers", "props": {"title": "Layers", "layer1_title": "Source", "layer1_body": "Reference", "layer2_title": "Tokens", "layer2_body": "Contract", "layer3_title": "Components", "layer3_body": "HUD"}},
            {"component": "comparison-table", "props": {"body_html": "<table><tr><th>Generic</th><th>Recovered</th></tr><tr><td>No HUD</td><td>HUD</td></tr></table>"}},
        ],
    }

    asm.assemble_landing(recipe, out_dir=tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    css = (tmp_path / "profile.css").read_text(encoding="utf-8")

    for class_name in [
        "hud-panel",
        "section-tag",
        "stats-bar",
        "num-grid",
        "chip-stack",
        "mermaid-wrap",
        "screenshot-card",
        "code-block",
        "cards-grid",
        "layer-stack",
        "compare-table",
    ]:
        assert class_name in html or class_name in css

    assert "text-shadow: 0 0 15px var(--color-accent-glow)" in css
    assert "cursor: crosshair" in css
    assert "border-radius" not in css
    assert "mermaid.min.js" in html
```

Run targeted test. Expected: fail because component dirs do not exist.

### 3.2 Implement Component Files

Create these directories under `plugins/h2t-creative/profiles/h2t-graphs/components/`:

```text
hud-panel/
stats-bar/
numbers-grid/
chip-stack/
mermaid-diagram/
screenshot-card/
code-block/
cards-grid/
layers/
comparison-table/
```

Each directory must contain `manifest.yaml`, `<component>.html`, and `<component>.css`.

Shared CSS invariants for all graphs components:

- Use `var(--color-surface)`, `var(--color-border)`, `var(--color-accent)`, `var(--color-accent-glow)`.
- Use `var(--font-mono)` for labels/body and `var(--font-sans)` for numeric/display moments.
- No `border-radius`.
- No `box-shadow` except text glow.
- HUD corner brackets implemented with pseudo-elements or explicit `.corner-br`.

Use this CSS pattern in components that need HUD panels:

```css
.hud-panel {
  position: relative;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: 2rem 2.5rem;
}

.hud-panel::before,
.hud-panel::after,
.hud-panel .corner-br::before,
.hud-panel .corner-br::after {
  content: "";
  position: absolute;
  width: var(--corner-size, 14px);
  height: var(--corner-size, 14px);
  border-color: var(--color-accent);
  border-style: solid;
}
```

Use this section tag pattern in `hud-panel`, `mermaid-diagram`, `code-block`, `cards-grid`, and `layers`:

```css
.section-tag {
  display: block;
  margin-bottom: 0.75rem;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
  font-size: 0.55rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
}

.section-tag::before {
  content: "// ";
  color: var(--color-accent);
}
```

Required component HTML shape:

`hud-panel/hud-panel.html`:

```html
<section class="hud-panel">
  <span class="corner-br"></span>
  {% if tag %}<span class="section-tag">{{ tag }}</span>{% endif %}
  {% if title %}<h2>{{ title }}</h2>{% endif %}
  <div class="hud-panel__body">{{ body | safe }}</div>
</section>
```

`stats-bar/stats-bar.html`:

```html
<section class="stats-bar" aria-label="Key metrics">
  <div class="stats-bar__item"><strong>{{ stat1_value }}</strong><span>{{ stat1_label }}</span></div>
  <div class="stats-bar__item"><strong>{{ stat2_value }}</strong><span>{{ stat2_label }}</span></div>
  <div class="stats-bar__item"><strong>{{ stat3_value }}</strong><span>{{ stat3_label }}</span></div>
</section>
```

`numbers-grid/numbers-grid.html`:

```html
<section class="num-grid">
  <div class="num-grid__cell"><strong>{{ cell1_value }}</strong><span>{{ cell1_label }}</span></div>
  <div class="num-grid__cell"><strong>{{ cell2_value }}</strong><span>{{ cell2_label }}</span></div>
  <div class="num-grid__cell"><strong>{{ cell3_value }}</strong><span>{{ cell3_label }}</span></div>
  <div class="num-grid__cell"><strong>{{ cell4_value }}</strong><span>{{ cell4_label }}</span></div>
</section>
```

`chip-stack/chip-stack.html`:

```html
<section class="chip-stack">{{ chips_html | safe }}</section>
```

`mermaid-diagram/mermaid-diagram.html`:

```html
<section class="hud-panel mermaid-wrap">
  <span class="corner-br"></span>
  {% if label %}<span class="section-tag">{{ label }}</span>{% endif %}
  <pre class="mermaid">{{ diagram }}</pre>
</section>
<script>
  if (window.mermaid && !window.__h2tMermaidInitialized) {
    window.__h2tMermaidInitialized = true;
    window.mermaid.initialize({ startOnLoad: true, theme: "dark" });
  }
</script>
```

`screenshot-card/screenshot-card.html`:

```html
<figure class="hud-panel screenshot-card">
  <span class="corner-br"></span>
  <img src="{{ image_src }}" alt="{{ alt }}">
  {% if caption %}<figcaption>{{ caption }}</figcaption>{% endif %}
</figure>
```

`code-block/code-block.html`:

```html
<section class="hud-panel code-block">
  <span class="corner-br"></span>
  {% if label %}<span class="section-tag">{{ label }}</span>{% endif %}
  <pre><code>{{ code }}</code></pre>
</section>
```

`cards-grid/cards-grid.html`:

```html
<section class="cards-grid">
  {% if title %}<span class="section-tag">{{ title }}</span>{% endif %}
  <article class="cards-grid__card"><h3>{{ card1_title }}</h3><p>{{ card1_body }}</p></article>
  <article class="cards-grid__card"><h3>{{ card2_title }}</h3><p>{{ card2_body }}</p></article>
  <article class="cards-grid__card"><h3>{{ card3_title }}</h3><p>{{ card3_body }}</p></article>
  <article class="cards-grid__card"><h3>{{ card4_title }}</h3><p>{{ card4_body }}</p></article>
</section>
```

`layers/layers.html`:

```html
<section class="layer-stack">
  {% if title %}<span class="section-tag">{{ title }}</span>{% endif %}
  <article class="layer-stack__item"><strong>01</strong><div><h3>{{ layer1_title }}</h3><p>{{ layer1_body }}</p></div></article>
  <article class="layer-stack__item"><strong>02</strong><div><h3>{{ layer2_title }}</h3><p>{{ layer2_body }}</p></div></article>
  <article class="layer-stack__item"><strong>03</strong><div><h3>{{ layer3_title }}</h3><p>{{ layer3_body }}</p></div></article>
</section>
```

`comparison-table/comparison-table.html`:

```html
<section class="hud-panel compare-table">
  <span class="corner-br"></span>
  {{ body_html | safe }}
</section>
```

Update `plugins/h2t-creative/profiles/h2t-graphs/tokens.css` or component CSS so the page-level graph invariants exist:

```css
body {
  cursor: crosshair;
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(var(--color-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-grid) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(to bottom, black, transparent 80%);
  z-index: 0;
}
```

If `--color-grid` is not defined in all graphs palettes, add it as an alias/value in those palette files.

### 3.3 Verify And Commit

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/test_r1_legacy_fidelity.py -q
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ -q
git add plugins/h2t-creative/profiles/h2t-graphs plugins/h2t-creative/tests/test_r1_legacy_fidelity.py
git commit -m "feat(h2t-creative): recover h2t-graphs rich HUD components"
```

## Task 4: `h2t-graphs` Validation Recipe And Design Guardrails

The validation recipe must show the real profile vocabulary, not generic shared blocks.

### 4.1 Write Failing Guardrail Test

Append:

```python
def test_h2t_graphs_validation_recipe_excludes_generic_shared_blocks():
    recipe = _read_validation_recipe("h2t-graphs")
    components = set(_components(recipe))

    forbidden = {"features-grid", "pricing", "testimonials", "faq", "logos"}
    assert components.isdisjoint(forbidden)
```

Expected: fail until validation recipe exists.

### 4.2 Implement Validation Recipe

Create `plugins/h2t-creative/profiles/h2t-graphs/validation/recipe.yaml`:

```yaml
type: landing
profile: h2t-graphs
palette: default
title: h2t-graphs R1 Fidelity
sections:
  - component: nav
    props:
      brand: H2T Graphs
      links:
        - label: Pipeline
          href: "#pipeline"
        - label: Diagrams
          href: "#diagrams"
        - label: Stack
          href: "#stack"
  - component: hero
    props:
      badge: GRAPH INTELLIGENCE
      headline: From raw signals to navigable knowledge graphs.
      subline: A HUD-style recovery page for validating the original graphs.lichtpfadstudio.com design system.
  - component: stats-bar
    props:
      stat1_value: "619"
      stat1_label: videos indexed
      stat2_value: "9"
      stat2_label: pipeline stages
      stat3_value: "28"
      stat3_label: courses mapped
  - component: hud-panel
    props:
      tag: PIPELINE
      title: Source-first extraction
      body: "<p>Every component is recovered from a source reference before it becomes reusable.</p>"
  - component: mermaid-diagram
    props:
      label: DAG
      diagram: |
        graph TD
          A[Source screenshots] --> B[Token map]
          B --> C[Profile components]
          C --> D[Visual gate]
  - component: numbers-grid
    props:
      cell1_value: "01"
      cell1_label: capture
      cell2_value: "02"
      cell2_label: extract
      cell3_value: "03"
      cell3_label: render
      cell4_value: "04"
      cell4_label: compare
  - component: chip-stack
    props:
      chips_html: '<span class="chip hi">JetBrains Mono</span><span class="chip">Inter</span><span class="chip">Mermaid</span><span class="chip">HUD panels</span>'
  - component: screenshot-card
    props:
      image_src: sources/screenshots/reference-desktop.png
      alt: graphs reference
      caption: Reference capture used as source of truth.
  - component: code-block
    props:
      label: CLI
      code: h2t creative render --profile h2t-graphs --recipe validation/recipe.yaml
  - component: cards-grid
    props:
      title: RECOVERY
      card1_title: Source
      card1_body: Live page and legacy skill are recorded before implementation.
      card2_title: Contract
      card2_body: Components expose stable semantic fields.
      card3_title: Render
      card3_body: Profile-specific CSS owns structure and visual treatment.
      card4_title: Gate
      card4_body: Human visual comparison blocks release.
  - component: layers
    props:
      title: LAYERS
      layer1_title: Reference
      layer1_body: screenshots and legacy CSS
      layer2_title: Tokens
      layer2_body: graph palette and typography
      layer3_title: Components
      layer3_body: HUD panels, diagrams, stats, chips
  - component: comparison-table
    props:
      body_html: "<table><tr><th>Generic</th><th>Recovered</th></tr><tr><td>shared blocks</td><td>profile-specific HUD system</td></tr><tr><td>token-only adaptation</td><td>source-derived component structure</td></tr></table>"
  - component: cta
    props:
      text: Validate visually
      href: "#"
  - component: footer
    props:
      text: h2t-graphs R1 recovery
```

Update `plugins/h2t-creative/profiles/h2t-graphs/DESIGN.md`:

- Add `R1 Source Of Truth` section.
- List source screenshot and legacy `h2t:landing`.
- Add required components list.
- Add forbidden substitutions: no generic pricing/testimonials/features-grid as validation evidence.

### 4.3 Verify And Commit

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/test_r1_legacy_fidelity.py -q
git add plugins/h2t-creative/profiles/h2t-graphs plugins/h2t-creative/tests/test_r1_legacy_fidelity.py
git commit -m "docs(h2t-creative): add h2t-graphs R1 validation recipe"
```

## Task 5: Recover `h2t-mono` Comparison Components

`h2t-mono` must match specdesigner: near-black, mono-only, red accent, two-column code comparison, sparse comparison table. It must not receive HUD brackets or generic shared layout.

### 5.1 Write Failing Tests

Append:

```python
def test_h2t_mono_r1_components_render_specdesigner_patterns(tmp_path):
    recipe = {
        "type": "landing",
        "profile": "h2t-mono",
        "palette": "default",
        "title": "Mono R1",
        "sections": [
            {
                "component": "two-column",
                "props": {
                    "left_label": "BEFORE",
                    "left_title": "Prompt soup",
                    "left_body": "<code>Write a page</code><code>Make it modern</code>",
                    "right_label": "AFTER",
                    "right_title": "Specification",
                    "right_body": "<code class=\"is-good\">Token contract</code><code class=\"is-warn\">Visual gate</code>",
                },
            },
            {
                "component": "comparison-table",
                "props": {
                    "body_html": "<table><tr><th>Capability</th><th>Generic</th><th>Recovered</th></tr><tr><td>Visual source</td><td class=\"is-bad\">missing</td><td class=\"is-good\">required</td></tr></table>"
                },
            },
        ],
    }

    asm.assemble_landing(recipe, out_dir=tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    css = (tmp_path / "profile.css").read_text(encoding="utf-8")

    assert "two-column" in html
    assert "mono-compare" in html
    assert "is-good" in html
    assert "is-bad" in html
    assert "JetBrains Mono" in css
    assert "border-radius" not in css
    assert "box-shadow" not in css
    assert "hud-panel" not in css
```

Expected: fail because components do not exist.

### 5.2 Implement Components

Create:

```text
plugins/h2t-creative/profiles/h2t-mono/components/two-column/
plugins/h2t-creative/profiles/h2t-mono/components/comparison-table/
```

`two-column/two-column.html`:

```html
<section class="two-column">
  <article class="two-column__pane">
    {% if left_label %}<span class="two-column__label">{{ left_label }}</span>{% endif %}
    <h2>{{ left_title }}</h2>
    <div class="two-column__body">{{ left_body | safe }}</div>
  </article>
  <article class="two-column__pane two-column__pane--accent">
    {% if right_label %}<span class="two-column__label">{{ right_label }}</span>{% endif %}
    <h2>{{ right_title }}</h2>
    <div class="two-column__body">{{ right_body | safe }}</div>
  </article>
</section>
```

`two-column/two-column.css`:

```css
.two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin: 4rem auto;
  max-width: 1120px;
  background: var(--color-border);
  border: 1px solid var(--color-border);
  font-family: var(--font);
}

.two-column__pane {
  min-height: 320px;
  padding: 2rem;
  background: var(--color-bg);
}

.two-column__pane--accent {
  background: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg));
}

.two-column__label {
  display: block;
  margin-bottom: 1.25rem;
  color: var(--color-accent);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.two-column h2 {
  margin: 0 0 1.5rem;
  color: var(--color-text);
  font-size: clamp(1.6rem, 3vw, 3rem);
  line-height: 1.05;
  letter-spacing: -0.06em;
}

.two-column__body {
  display: grid;
  gap: 0.6rem;
}

.two-column code {
  display: block;
  padding: 0.7rem 0;
  color: var(--color-text-dim);
  border-bottom: 1px solid var(--color-border);
  font-family: var(--font);
}

.two-column code.is-good {
  color: var(--color-accent);
}

.two-column code.is-warn {
  color: #d6a657;
}

@media (max-width: 760px) {
  .two-column {
    grid-template-columns: 1fr;
  }
}
```

`comparison-table/comparison-table.html`:

```html
<section class="mono-compare">
  {{ body_html | safe }}
</section>
```

`comparison-table/comparison-table.css`:

```css
.mono-compare {
  margin: 4rem auto;
  max-width: 1120px;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  font-family: var(--font);
}

.mono-compare table {
  width: 100%;
  border-collapse: collapse;
}

.mono-compare th,
.mono-compare td {
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-dim);
  text-align: left;
  vertical-align: top;
}

.mono-compare th {
  color: var(--color-text);
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.mono-compare td + td,
.mono-compare th + th {
  border-left: 1px solid var(--color-border);
}

.mono-compare .is-good {
  color: var(--color-accent);
}

.mono-compare .is-bad {
  color: var(--color-text-dim);
  text-decoration: line-through;
}
```

### 5.3 Validation Recipe And Design Guardrails

Create `plugins/h2t-creative/profiles/h2t-mono/validation/recipe.yaml`:

```yaml
type: landing
profile: h2t-mono
palette: default
title: h2t-mono R1 Fidelity
sections:
  - component: nav
    props:
      brand: Spec Designer
      links:
        - label: Compare
          href: "#compare"
        - label: Validate
          href: "#validate"
  - component: hero
    props:
      badge: SPEC FIRST
      headline: Stop prompting pages. Define systems.
      subline: A mono recovery page for validating the specdesigner visual language.
  - component: two-column
    props:
      left_label: BEFORE
      left_title: Prompt soup
      left_body: '<code>make it modern</code><code>add some cards</code><code>try a dark theme</code>'
      right_label: AFTER
      right_title: Fixed contract
      right_body: '<code class="is-good">source screenshot</code><code class="is-good">token contract</code><code class="is-warn">human visual gate</code>'
  - component: comparison-table
    props:
      body_html: '<table><tr><th>Capability</th><th>Generic</th><th>Recovered</th></tr><tr><td>Visual source</td><td class="is-bad">missing</td><td class="is-good">required</td></tr><tr><td>Profile grammar</td><td class="is-bad">token-only</td><td class="is-good">component-level</td></tr><tr><td>Release gate</td><td class="is-bad">self-pass</td><td class="is-good">human confirmed</td></tr></table>'
  - component: cta
    props:
      text: Validate source match
      href: "#"
      text_ghost: View contract
      href_ghost: "#"
  - component: footer
    props:
      text: h2t-mono R1 recovery
```

Update `plugins/h2t-creative/profiles/h2t-mono/DESIGN.md`:

- Add `R1 Source Of Truth` section.
- List specdesigner screenshot.
- Add required patterns: two-column comparison, comparison table.
- Add forbidden patterns: HUD brackets, glow panels, rounded cards, shadows, generic shared pricing/testimonials.

### 5.4 Verify And Commit

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/test_r1_legacy_fidelity.py -q
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ -q
git add plugins/h2t-creative/profiles/h2t-mono plugins/h2t-creative/tests/test_r1_legacy_fidelity.py
git commit -m "feat(h2t-creative): recover h2t-mono comparison components"
```

## Task 6: Visual Regression Pack For R1

Generate outputs and screenshots for human comparison. This task cannot self-pass.

### 6.1 Build Validation Pages

```powershell
.venv/Scripts/python.exe plugins/h2t-creative/assembler.py plugins/h2t-creative/profiles/h2t-graphs/validation/recipe.yaml --out dist/r1/h2t-graphs
.venv/Scripts/python.exe plugins/h2t-creative/assembler.py plugins/h2t-creative/profiles/h2t-mono/validation/recipe.yaml --out dist/r1/h2t-mono
```

Expected:

```text
Built landing -> dist/r1/h2t-graphs
Built landing -> dist/r1/h2t-mono
```

### 6.2 Capture Screenshots

Use the same screenshot workflow used for Phase 2b. Save:

```text
docs/visual-regression/2026-05-04-r1/h2t-graphs-desktop.png
docs/visual-regression/2026-05-04-r1/h2t-graphs-mobile.png
docs/visual-regression/2026-05-04-r1/h2t-mono-desktop.png
docs/visual-regression/2026-05-04-r1/h2t-mono-mobile.png
```

If browser automation is unavailable, stop and report that visual gate cannot be executed in this session.

### 6.3 Human Checklist

Create `docs/visual-regression/2026-05-04-r1/checklist.md`:

```markdown
# h2t-creative R1 Visual Gate

Status: PENDING HUMAN REVIEW

## h2t-graphs

Reference: `docs/visual-regression/reference/graphs.lichtpfadstudio.com/desktop_20260504_000404.png`
Candidate: `h2t-graphs-desktop.png`, `h2t-graphs-mobile.png`

- [ ] HUD panels use 4-corner bracket grammar.
- [ ] Grid background is visible but subtle.
- [ ] Stats bar is segmented, dense, and uses accent glow on numbers.
- [ ] Chips are monospace bordered labels, not pills/cards.
- [ ] Mermaid/code/screenshot blocks sit inside HUD frames.
- [ ] Typography matches Inter headings + JetBrains Mono labels/body.
- [ ] No generic shared pricing/testimonial/features-grid aesthetic is visible.

## h2t-mono

Reference: `docs/visual-regression/reference/specdesigner.netlify.app/desktop_20260504_000404.png`
Candidate: `h2t-mono-desktop.png`, `h2t-mono-mobile.png`

- [ ] Page is near-black, sparse, mono-only.
- [ ] Two-column comparison resembles specdesigner structure.
- [ ] Table uses sparse borders and colored status states.
- [ ] Red accent is restrained and singular.
- [ ] No HUD brackets, glow panels, rounded cards, or shadows.
- [ ] No generic shared pricing/testimonial/features-grid aesthetic is visible.

## Release Gate

- [ ] Human confirmed R1 visual match.

If any item is marked `[!]` or remains unchecked, do not bump minor and do not mark R1 complete.
```

### 6.4 Verify And Commit

```powershell
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ -q
git add dist/r1 docs/visual-regression/2026-05-04-r1
git commit -m "test(h2t-creative): add R1 visual regression pack"
```

If `dist/` is gitignored, do not force-add generated HTML unless the repository already tracks comparable outputs. Commit only screenshots/checklist.

## Task 7: Final Review

Run:

```powershell
git status --short
git log --oneline -5
.venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ -q
```

Review generated diffs:

```powershell
git show --stat --oneline HEAD~4..HEAD
git diff HEAD~4..HEAD -- plugins/h2t-creative/profiles/h2t-graphs plugins/h2t-creative/profiles/h2t-mono plugins/h2t-creative/assembler.py plugins/h2t-creative/tests/test_r1_legacy_fidelity.py
```

Do not report R1 as complete unless:

- All tests pass.
- Dossiers exist.
- Validation recipes assemble.
- Visual screenshots exist.
- Human checklist is created and explicitly pending or confirmed.

## Expected Commit Series

1. `test(h2t-creative): add R1 legacy fidelity contracts`
2. `feat(h2t-creative): support profile head scripts`
3. `feat(h2t-creative): recover h2t-graphs rich HUD components`
4. `docs(h2t-creative): add h2t-graphs R1 validation recipe`
5. `feat(h2t-creative): recover h2t-mono comparison components`
6. `test(h2t-creative): add R1 visual regression pack`

## Handoff Note

After execution, report:

- Test command and result.
- Screenshot paths.
- Whether human visual gate is pending or confirmed.
- Any components intentionally deferred to R2/R3.
- Version remains unchanged unless a separate explicit versioning decision is made.
