# h2t-creative v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Shell:** All commands use **bash** (Git Bash on Windows). Claude Code on this machine runs bash (`Shell: bash` in env). Use `C:/...` paths with forward slashes. `/tmp` is available in Git Bash.

**Goal:** Replace monolithic h2t-creative v1 skills with a four-layer system (base CSS → modular profiles → Python assembler → skill wrappers) that produces deployable multi-file landing pages and decks with Playwright QA.

**Architecture:** Immutable base CSS (Swiss 12-column grid) + swappable profile directories (DESIGN.md + tokens + component templates + optional fx/) assembled by a stdlib Python script into dist/. Skills wrap the assembler and invoke h2t-tools:playwright-agent for visual QA.

**Tech Stack:** Python 3.11 stdlib (pathlib, html, re, argparse) + PyYAML (already in `~/.h2t/venv`), CSS custom properties, vanilla JS for deck navigation, optional Three.js via CDN.

---

## File Map

**Create:**
- `plugins/h2t-creative/base/reset.css`
- `plugins/h2t-creative/base/grid.css`
- `plugins/h2t-creative/base/typography.css`
- `plugins/h2t-creative/base/animations.css`
- `plugins/h2t-creative/profiles/h2t-default/DESIGN.md`
- `plugins/h2t-creative/profiles/h2t-default/tokens.css`
- `plugins/h2t-creative/profiles/h2t-default/components/nav/nav.html`
- `plugins/h2t-creative/profiles/h2t-default/components/nav/nav.css`
- `plugins/h2t-creative/profiles/h2t-default/components/nav/manifest.yaml`
- `plugins/h2t-creative/profiles/h2t-default/components/hero/hero.html`
- `plugins/h2t-creative/profiles/h2t-default/components/hero/hero.css`
- `plugins/h2t-creative/profiles/h2t-default/components/hero/manifest.yaml`
- `plugins/h2t-creative/profiles/h2t-default/components/section/section.html`
- `plugins/h2t-creative/profiles/h2t-default/components/section/section.css`
- `plugins/h2t-creative/profiles/h2t-default/components/section/manifest.yaml`
- `plugins/h2t-creative/profiles/h2t-default/components/cta/cta.html`
- `plugins/h2t-creative/profiles/h2t-default/components/cta/cta.css`
- `plugins/h2t-creative/profiles/h2t-default/components/cta/manifest.yaml`
- `plugins/h2t-creative/profiles/h2t-default/components/footer/footer.html`
- `plugins/h2t-creative/profiles/h2t-default/components/footer/footer.css`
- `plugins/h2t-creative/profiles/h2t-default/components/footer/manifest.yaml`
- `plugins/h2t-creative/assembler.py`
- `tests/h2t_creative/__init__.py`
- `tests/h2t_creative/test_assembler.py`
- `plugins/h2t-creative/skills/style-create/SKILL.md`
- `plugins/h2t-creative/skills/style-validate/SKILL.md`
- `plugins/h2t-creative/skills/landing/SKILL.md`
- `plugins/h2t-creative/skills/deck/SKILL.md`
- `plugins/h2t-creative/commands/style-create.md`

**Modify:**
- `plugins/h2t-creative/skills/design/SKILL.md` → deprecation notice
- `plugins/h2t-creative/commands/design.md` → alias to /style-create
- `plugins/h2t-creative/commands/landing.md` → thin wrapper (already correct pattern)
- `plugins/h2t-creative/commands/deck.md` → thin wrapper (already correct pattern)
- `plugins/h2t-creative/.claude-plugin/plugin.json` → add new skills, patch bump

---

## Task 1: Base CSS — Layer 1

**Files:**
- Create: `plugins/h2t-creative/base/reset.css`
- Create: `plugins/h2t-creative/base/grid.css`
- Create: `plugins/h2t-creative/base/typography.css`
- Create: `plugins/h2t-creative/base/animations.css`

- [ ] **Step 1: Create reset.css**

```css
/* plugins/h2t-creative/base/reset.css */
*, *::before, *::after { box-sizing: border-box; }
* { margin: 0; padding: 0; }
img, picture, video, canvas, svg { display: block; max-width: 100%; }
input, button, textarea, select { font: inherit; }
p, h1, h2, h3, h4, h5, h6 { overflow-wrap: break-word; }
```

- [ ] **Step 2: Create grid.css**

```css
/* plugins/h2t-creative/base/grid.css */
:root {
  --grid-cols: 12;
  --grid-gap: clamp(1rem, 2vw, 2rem);
  --grid-padding: clamp(1rem, 4vw, 4rem);
}

.grid {
  display: grid;
  grid-template-columns: repeat(var(--grid-cols), 1fr);
  gap: var(--grid-gap);
  max-width: 1440px;
  margin-inline: auto;
  padding-inline: var(--grid-padding);
}

.col-1  { grid-column: span 1; }
.col-2  { grid-column: span 2; }
.col-3  { grid-column: span 3; }
.col-4  { grid-column: span 4; }
.col-5  { grid-column: span 5; }
.col-6  { grid-column: span 6; }
.col-7  { grid-column: span 7; }
.col-8  { grid-column: span 8; }
.col-9  { grid-column: span 9; }
.col-10 { grid-column: span 10; }
.col-11 { grid-column: span 11; }
.col-12 { grid-column: span 12; }

.section {
  padding-block: clamp(3rem, 6vw, 6rem);
}

@media (max-width: 768px) {
  .col-sm-12 { grid-column: span 12; }
  .col-sm-6  { grid-column: span 6; }
  .col-sm-4  { grid-column: span 4; }
}
```

- [ ] **Step 3: Create typography.css**

```css
/* plugins/h2t-creative/base/typography.css */
:root {
  --font-size-base: clamp(1rem, 0.875rem + 0.333vw, 1.125rem);
  --font-size-h1: clamp(2.5rem, 1.5rem + 2.667vw, 4rem);
  --font-size-h2: clamp(2rem, 1.25rem + 2vw, 3rem);
  --font-size-h3: clamp(1.5rem, 1rem + 1.333vw, 2rem);
  --line-height-body: 1.6;
  --line-height-heading: 1.1;
}

body {
  font-size: var(--font-size-base);
  line-height: var(--line-height-body);
  -webkit-font-smoothing: antialiased;
}

h1 { font-size: var(--font-size-h1); line-height: var(--line-height-heading); }
h2 { font-size: var(--font-size-h2); line-height: var(--line-height-heading); }
h3 { font-size: var(--font-size-h3); line-height: var(--line-height-heading); }
```

- [ ] **Step 4: Create animations.css**

```css
/* plugins/h2t-creative/base/animations.css */
:root {
  --duration-fast: 150ms;
  --duration-base: 300ms;
  --duration-slow: 600ms;
  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/base/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add Layer 1 base CSS (Swiss grid, typography, animations)"
```

---

## Task 2: h2t-default Profile — DESIGN.md + tokens.css

**Files:**
- Create: `plugins/h2t-creative/profiles/h2t-default/DESIGN.md`
- Create: `plugins/h2t-creative/profiles/h2t-default/tokens.css`

- [ ] **Step 1: Create DESIGN.md**

```markdown
# h2t-default

## Brand Intent
Clean, editorial Swiss-grid aesthetic. High contrast, geometric precision, generous whitespace.
Suited for technical product landing pages and educational course presentations.

## Color Tokens
- `--color-bg`: #ffffff
- `--color-fg`: #0a0a0a
- `--color-accent`: #1a1aff
- `--color-accent-hover`: #0000cc
- `--color-muted`: #6b7280
- `--color-surface`: #f5f5f5
- `--color-border`: #e5e7eb

## Typography
- `--font-display`: system-ui, sans-serif
- `--font-body`: system-ui, sans-serif

## Restrictions
- Do NOT use drop shadows or gradients
- Maintain 8px spacing grid (use --space-* tokens only)
- Links must meet WCAG AA contrast ratio

## Usage Examples
Use for: Hou2Touch course landing pages, workshop announcements, tool documentation pages.
```

- [ ] **Step 2: Create tokens.css**

```css
/* plugins/h2t-creative/profiles/h2t-default/tokens.css */
:root {
  --color-bg: #ffffff;
  --color-fg: #0a0a0a;
  --color-accent: #1a1aff;
  --color-accent-hover: #0000cc;
  --color-muted: #6b7280;
  --color-surface: #f5f5f5;
  --color-border: #e5e7eb;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;

  --font-display: system-ui, sans-serif;
  --font-body: system-ui, sans-serif;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  background-color: var(--color-bg);
  color: var(--color-fg);
  font-family: var(--font-body);
}
```

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-default/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-default profile scaffold (DESIGN.md + tokens)"
```

---

## Task 3: Component Templates (5 components)

**Files:** `plugins/h2t-creative/profiles/h2t-default/components/{nav,hero,section,cta,footer}/`

- [ ] **Step 1: Create nav component**

`components/nav/manifest.yaml`:
```yaml
component: nav
fields:
  brand_name:
    type: text
    required: true
  home_href:
    type: url
    required: false
    default: "/"
```

`components/nav/nav.html`:
```html
<nav class="section nav">
  <div class="grid">
    <div class="col-4 col-sm-12">
      <a href="{{ home_href }}" class="nav__brand">{{ brand_name }}</a>
    </div>
  </div>
</nav>
```

`components/nav/nav.css`:
```css
.nav { padding-block: var(--space-md); border-bottom: 1px solid var(--color-border); }
.nav__brand { font-family: var(--font-display); font-weight: 700; color: var(--color-fg); text-decoration: none; }
```

- [ ] **Step 2: Create hero component**

`components/hero/manifest.yaml`:
```yaml
component: hero
fields:
  headline:
    type: text
    required: true
  subline:
    type: text
    required: false
    default: ""
```

`components/hero/hero.html`:
```html
<section class="section hero">
  <div class="grid">
    <div class="col-8 col-sm-12">
      <h1 class="hero__headline">{{ headline }}</h1>
      <p class="hero__subline">{{ subline }}</p>
    </div>
  </div>
</section>
```

`components/hero/hero.css`:
```css
.hero { background-color: var(--color-surface); }
.hero__headline { font-family: var(--font-display); color: var(--color-fg); margin-bottom: var(--space-md); }
.hero__subline { font-size: 1.25rem; color: var(--color-muted); max-width: 60ch; }
```

- [ ] **Step 3: Create section component**

`components/section/manifest.yaml`:
```yaml
component: section
fields:
  title:
    type: text
    required: true
  body:
    type: html
    required: true
```

`components/section/section.html`:
```html
<section class="section content">
  <div class="grid">
    <div class="col-10 col-sm-12">
      <h2 class="content__title">{{ title }}</h2>
      <div class="content__body">{{ body | safe }}</div>
    </div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content__title { font-family: var(--font-display); margin-bottom: var(--space-lg); }
.content__body { max-width: 72ch; color: var(--color-fg); }
.content__body p + p { margin-top: var(--space-md); }
```

- [ ] **Step 4: Create cta component**

`components/cta/manifest.yaml`:
```yaml
component: cta
fields:
  text:
    type: text
    required: true
  href:
    type: url
    required: true
```

`components/cta/cta.html`:
```html
<section class="section cta">
  <div class="grid">
    <div class="col-6 col-sm-12">
      <a href="{{ href }}" class="cta__button">{{ text }}</a>
    </div>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta { text-align: center; }
.cta__button {
  display: inline-block;
  background-color: var(--color-accent);
  color: #ffffff;
  padding: var(--space-md) var(--space-xl);
  border-radius: var(--radius-md);
  text-decoration: none;
  font-weight: 700;
  transition: background-color var(--duration-fast) var(--easing-default);
}
.cta__button:hover { background-color: var(--color-accent-hover); }
```

- [ ] **Step 5: Create footer component**

`components/footer/manifest.yaml`:
```yaml
component: footer
fields:
  copy:
    type: text
    required: true
```

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="grid">
    <div class="col-12">
      <p class="footer__copy">{{ copy }}</p>
    </div>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { border-top: 1px solid var(--color-border); }
.footer__copy { color: var(--color-muted); font-size: 0.875rem; }
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-default profile — 5 component templates with manifests"
```

---

## Task 4: Assembler Core — interpolate + validate

**Files:**
- Create: `plugins/h2t-creative/assembler.py` (interpolate + validate only)
- Create: `tests/h2t_creative/__init__.py`
- Create: `tests/h2t_creative/test_assembler.py` (core tests only)

- [ ] **Step 1: Write failing tests for interpolate and validate**

Create `tests/h2t_creative/__init__.py` (empty).

Create `tests/h2t_creative/test_assembler.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "h2t-creative"))

import pytest
import assembler


def test_interpolate_substitutes_field():
    result = assembler.interpolate("Hello {{ name }}", {"name": "World"})
    assert result == "Hello World"


def test_interpolate_html_escapes_by_default():
    result = assembler.interpolate("{{ val }}", {"val": "<script>alert(1)</script>"})
    assert result == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_interpolate_safe_skips_escape():
    result = assembler.interpolate("{{ val | safe }}", {"val": "<b>bold</b>"})
    assert result == "<b>bold</b>"


def test_interpolate_unknown_placeholder_raises():
    with pytest.raises(ValueError, match="unknown_field"):
        assembler.interpolate("{{ unknown_field }}", {})


def test_validate_section_content_unknown_field_raises():
    manifest = {"component": "hero", "fields": {"headline": {"type": "text", "required": True}}}
    section = {"component": "hero", "content": {"headline": "Hi", "extra": "bad"}}
    with pytest.raises(ValueError, match="unknown field 'extra'"):
        assembler.validate_section_content(section, manifest)


def test_validate_section_content_missing_required_raises():
    manifest = {"component": "hero", "fields": {"headline": {"type": "text", "required": True}}}
    section = {"component": "hero", "content": {}}
    with pytest.raises(ValueError, match="required field 'headline'"):
        assembler.validate_section_content(section, manifest)


def test_validate_section_content_optional_field_passes():
    manifest = {
        "component": "hero",
        "fields": {
            "headline": {"type": "text", "required": True},
            "subline": {"type": "text", "required": False, "default": ""},
        },
    }
    section = {"component": "hero", "content": {"headline": "Hi"}}
    assembler.validate_section_content(section, manifest)  # must not raise
```

- [ ] **Step 2: Run tests — expect ImportError (assembler.py not yet created)**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected: `ModuleNotFoundError: No module named 'assembler'`

- [ ] **Step 3: Create assembler.py with interpolate + validate**

```python
#!/usr/bin/env python3
"""h2t-creative assembler: base + profile + recipe → dist/"""
import argparse
import html
import re
import shutil
import sys
import yaml
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent
BASE_DIR = PLUGIN_ROOT / "base"
PROFILES_DIR = PLUGIN_ROOT / "profiles"
REQUIRED_COMPONENTS = ["nav", "hero", "section", "cta", "footer"]
DECK_LAYOUTS = {"title-only", "title-body", "title-media", "blank"}
FX_SIZE_WARN_BYTES = 50 * 1024

_PLACEHOLDER_RE = re.compile(r'\{\{\s*(\w+)(?:\s*\|\s*safe)?\s*\}\}')
_SAFE_PLACEHOLDER_RE = re.compile(r'\{\{\s*(\w+)\s*\|\s*safe\s*\}\}')


def interpolate(template: str, fields: dict) -> str:
    """Substitute {{ field }} (HTML-escaped) and {{ field | safe }} (raw)."""
    safe_fields = set(_SAFE_PLACEHOLDER_RE.findall(template))

    def replacer(m):
        field_name = m.group(1)
        if field_name not in fields:
            raise ValueError(
                f"Template placeholder '{{{{ {field_name} }}}}' has no matching recipe field"
            )
        value = str(fields[field_name])
        return value if field_name in safe_fields else html.escape(value)

    return _PLACEHOLDER_RE.sub(replacer, template)


def validate_section_content(section: dict, manifest: dict) -> None:
    """Validate recipe section content keys against component manifest."""
    component_name = manifest.get("component", "?")
    content = section.get("content", {})
    manifest_fields = manifest.get("fields", {})

    for key in content:
        if key not in manifest_fields:
            raise ValueError(
                f"Component '{component_name}': unknown field '{key}' in recipe content"
            )
    for field, schema in manifest_fields.items():
        if schema.get("required", False) and field not in content:
            raise ValueError(
                f"Component '{component_name}': required field '{field}' missing from recipe"
            )


def load_recipe(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_manifest(component_dir: Path) -> dict:
    with open(component_dir / "manifest.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected:
```
tests/h2t_creative/test_assembler.py::test_interpolate_substitutes_field PASSED
tests/h2t_creative/test_assembler.py::test_interpolate_html_escapes_by_default PASSED
tests/h2t_creative/test_assembler.py::test_interpolate_safe_skips_escape PASSED
tests/h2t_creative/test_assembler.py::test_interpolate_unknown_placeholder_raises PASSED
tests/h2t_creative/test_assembler.py::test_validate_section_content_unknown_field_raises PASSED
tests/h2t_creative/test_assembler.py::test_validate_section_content_missing_required_raises PASSED
tests/h2t_creative/test_assembler.py::test_validate_section_content_optional_field_passes PASSED
7 passed
```

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/assembler.py tests/h2t_creative/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): assembler core — interpolate + manifest validation with tests"
```

---

## Task 5: Landing Assembly Pipeline

**Files:**
- Modify: `plugins/h2t-creative/assembler.py` (add landing functions)
- Modify: `tests/h2t_creative/test_assembler.py` (add landing tests)

- [ ] **Step 1: Add landing tests**

Append to `tests/h2t_creative/test_assembler.py`:

```python
import os
import tempfile


def _make_minimal_profile(tmp_path: Path) -> Path:
    """Creates a minimal profile with hero component for testing."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "reset.css").write_text("/* reset */")
    (base_dir / "grid.css").write_text("/* grid */")
    (base_dir / "typography.css").write_text("/* type */")
    (base_dir / "animations.css").write_text("/* anim */")

    profile_dir = tmp_path / "profiles" / "test-profile"
    (profile_dir / "components" / "hero").mkdir(parents=True)
    (profile_dir / "tokens.css").write_text(":root { --color-bg: #fff; }")
    (profile_dir / "components" / "hero" / "manifest.yaml").write_text(
        "component: hero\nfields:\n  headline:\n    type: text\n    required: true\n  subline:\n    type: text\n    required: false\n    default: ''\n"
    )
    (profile_dir / "components" / "hero" / "hero.html").write_text(
        '<section class="hero"><h1>{{ headline }}</h1><p>{{ subline }}</p></section>'
    )
    (profile_dir / "components" / "hero" / "hero.css").write_text(".hero { color: red; }")
    return profile_dir, base_dir


def test_assemble_landing_creates_dist_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "Test Page",
        "sections": [{"component": "hero", "content": {"headline": "Hello"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "base.css").exists()
    assert (out_dir / "profile.css").exists()
    assert "fx.js" not in [f.name for f in out_dir.iterdir()]


def test_assemble_landing_interpolates_content(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "My Page",
        "sections": [{"component": "hero", "content": {"headline": "Welcome <World>"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    html_content = (out_dir / "index.html").read_text()
    assert "Welcome &lt;World&gt;" in html_content
    assert "My Page" in html_content


def test_assemble_landing_profile_css_contains_tokens_and_component(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "landing",
        "profile": "test-profile",
        "title": "T",
        "sections": [{"component": "hero", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    profile_css = (out_dir / "profile.css").read_text()
    assert "--color-bg" in profile_css
    assert ".hero" in profile_css


def test_assemble_landing_no_fx_if_fx_dir_absent(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert "bg-canvas" not in content
    assert not (out_dir / "fx.js").exists()
```

- [ ] **Step 2: Run tests — expect new tests to fail (function not yet implemented)**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v -k "landing"
```

Expected: `AttributeError: module 'assembler' has no attribute 'assemble_landing'`

- [ ] **Step 3: Add landing assembly to assembler.py**

Append to `plugins/h2t-creative/assembler.py`:

```python
_HTML_LANDING = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="profile.css">
</head>
<body>
{body}
{fx_canvas}
{fx_script}
</body>
</html>
"""

_FX_SCRIPT = (
    '<script>var c=document.getElementById("bg-canvas");'
    'import("./fx.js").then(function(m){{m.init(c);'
    'window.addEventListener("unload",function(){{m.destroy();}});}});</script>'
)


def _has_fx(profile_dir: Path) -> bool:
    fx_js = profile_dir / "fx" / "background.js"
    if not fx_js.exists():
        return False
    size = fx_js.stat().st_size
    if size > FX_SIZE_WARN_BYTES:
        print(f"WARNING: fx/background.js is {size // 1024}KB (>{FX_SIZE_WARN_BYTES // 1024}KB threshold)", file=sys.stderr)
    return True


def _build_section_html(section: dict, profile_dir: Path) -> str:
    component_name = section["component"]
    component_dir = profile_dir / "components" / component_name
    if not component_dir.exists():
        raise ValueError(f"Component '{component_name}' not found in profile at {component_dir}")
    manifest = load_manifest(component_dir)
    validate_section_content(section, manifest)
    template = (component_dir / f"{component_name}.html").read_text(encoding="utf-8")
    content = dict(section.get("content", {}))
    for field, schema in manifest.get("fields", {}).items():
        if field not in content and "default" in schema:
            content[field] = schema["default"]
    return interpolate(template, content)


def _build_profile_css(profile_dir: Path, sections: list) -> str:
    parts = [(profile_dir / "tokens.css").read_text(encoding="utf-8")]
    seen: set = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
            seen.add(name)
    return "\n".join(parts)


def _build_base_css(base_dir: Path) -> str:
    return "\n".join(
        (base_dir / f).read_text(encoding="utf-8")
        for f in ["reset.css", "grid.css", "typography.css", "animations.css"]
        if (base_dir / f).exists()
    )


def assemble_landing(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
) -> None:
    if base_dir is None:
        base_dir = BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    sections = recipe.get("sections", [])
    body = "\n".join(_build_section_html(s, profile_dir) for s in sections)
    has_fx = _has_fx(profile_dir)
    fx_canvas = '<canvas id="bg-canvas"></canvas>' if has_fx else ""
    fx_script = _FX_SCRIPT if has_fx else ""
    index_html = _HTML_LANDING.format(
        title=html.escape(str(recipe.get("title", ""))),
        body=body,
        fx_canvas=fx_canvas,
        fx_script=fx_script,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    (out_dir / "base.css").write_text(_build_base_css(base_dir), encoding="utf-8")
    (out_dir / "profile.css").write_text(_build_profile_css(profile_dir, sections), encoding="utf-8")
    if has_fx:
        shutil.copy(profile_dir / "fx" / "background.js", out_dir / "fx.js")
```

- [ ] **Step 4: Run all tests — expect all pass**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/assembler.py tests/h2t_creative/test_assembler.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): assembler landing pipeline with tests"
```

---

## Task 6: Deck Assembly Pipeline

**Files:**
- Modify: `plugins/h2t-creative/assembler.py` (add deck functions)
- Modify: `tests/h2t_creative/test_assembler.py` (add deck tests)

- [ ] **Step 1: Add deck tests**

Append to `tests/h2t_creative/test_assembler.py`:

```python
def test_assemble_deck_creates_dist_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "My Deck",
        "slides": [
            {"title": "Intro", "layout": "title-only", "content": {"headline": "Start"}},
            {"title": "Content", "layout": "title-body", "content": {"headline": "Details", "body": "text"}},
        ],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "base.css").exists()
    assert (out_dir / "profile.css").exists()


def test_assemble_deck_contains_slides_and_menu(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "Deck",
        "slides": [
            {"title": "One", "layout": "title-only", "content": {"headline": "Slide One"}},
            {"title": "Two", "layout": "title-only", "content": {"headline": "Slide Two"}},
        ],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert 'class="slide"' in content
    assert "slide-menu" in content
    assert "#slide-1" in content
    assert "#slide-2" in content
    assert "Slide One" in content
    assert "ArrowRight" in content


def test_assemble_deck_speaker_note_as_html_comment(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "D",
        "slides": [{"title": "S1", "layout": "title-only", "content": {
            "headline": "Hi", "note": "Remember to pause here"
        }}],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
    content = (out_dir / "index.html").read_text()
    assert "<!-- SPEAKER NOTE:" in content
    assert "Remember to pause here" in content


def test_schema_cross_contamination_landing_with_slides_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "slides": []}
    out_dir = tmp_path / "dist"
    with pytest.raises(SystemExit):
        assembler.main_assemble("landing", recipe, profile_dir, out_dir, base_dir=base_dir)


def test_schema_cross_contamination_deck_with_sections_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "deck", "title": "T", "sections": []}
    out_dir = tmp_path / "dist"
    with pytest.raises(SystemExit):
        assembler.main_assemble("deck", recipe, profile_dir, out_dir, base_dir=base_dir)


def test_deck_unknown_layout_raises(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {
        "type": "deck",
        "title": "D",
        "slides": [{"title": "S", "layout": "bad-layout", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    with pytest.raises(ValueError, match="Unknown deck layout"):
        assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
```

- [ ] **Step 2: Run new tests — expect AttributeError**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v -k "deck or contamination"
```

Expected: `AttributeError: module 'assembler' has no attribute 'assemble_deck'`

- [ ] **Step 3: Add deck assembly to assembler.py**

Append to `plugins/h2t-creative/assembler.py`:

```python
_DECK_LAYOUT_HTML = {
    "title-only": '<div class="slide-inner"><h1 class="slide-headline">{{ headline }}</h1></div>',
    "title-body": (
        '<div class="slide-inner">'
        '<h1 class="slide-headline">{{ headline }}</h1>'
        '<div class="slide-body">{{ body | safe }}</div>'
        '</div>'
    ),
    "title-media": (
        '<div class="slide-inner slide-inner--media">'
        '<h1 class="slide-headline">{{ headline }}</h1>'
        '<div class="slide-media"><img src="{{ media_url }}" alt="{{ headline }}"></div>'
        '</div>'
    ),
    "blank": '<div class="slide-inner"></div>',
}

_DECK_NAV_JS = """\
(function(){
  var slides=document.querySelectorAll('.slide');
  var links=document.querySelectorAll('.slide-menu a');
  var cur=0;
  function show(i){
    slides.forEach(function(s,j){s.classList.toggle('slide--active',j===i);});
    links.forEach(function(a,j){a.classList.toggle('slide-menu__link--active',j===i);});
    window.location.hash='slide-'+(i+1); cur=i;
  }
  document.addEventListener('keydown',function(e){
    if(e.key==='ArrowRight'||e.key===' '){if(cur<slides.length-1)show(cur+1);}
    if(e.key==='ArrowLeft'){if(cur>0)show(cur-1);}
  });
  links.forEach(function(a,i){a.addEventListener('click',function(e){e.preventDefault();show(i);});});
  var h=window.location.hash;
  show(h?Math.max(0,Math.min(parseInt(h.replace('#slide-',''))-1,slides.length-1)):0);
})();"""

_HTML_DECK = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="profile.css">
</head>
<body class="deck">
<nav class="slide-menu">
{menu_links}
</nav>
<main class="slides">
{slides_html}
</main>
{fx_canvas}
<script>
{nav_js}
</script>
{fx_script}
</body>
</html>
"""


def _build_deck_slide_html(slide: dict) -> str:
    layout = slide.get("layout", "title-body")
    if layout not in DECK_LAYOUTS:
        raise ValueError(f"Unknown deck layout: '{layout}'. Valid: {sorted(DECK_LAYOUTS)}")
    template = _DECK_LAYOUT_HTML[layout]
    content = dict(slide.get("content", {}))
    note = content.pop("note", None)
    inner = interpolate(template, content) if template else ""
    note_comment = f"\n<!-- SPEAKER NOTE: {html.escape(str(note))} -->" if note else ""
    return f'<section class="slide">{inner}{note_comment}\n</section>'


def assemble_deck(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
) -> None:
    if base_dir is None:
        base_dir = BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_data = recipe.get("slides", [])
    slides_html = "\n".join(_build_deck_slide_html(s) for s in slides_data)
    menu_links = "\n".join(
        f'  <a href="#slide-{i+1}" class="slide-menu__link">'
        f'{html.escape(str(s.get("title", f"Slide {i+1}")))}</a>'
        for i, s in enumerate(slides_data)
    )
    has_fx = _has_fx(profile_dir)
    fx_canvas = '<canvas id="bg-canvas"></canvas>' if has_fx else ""
    fx_script = (
        '<script>var c=document.getElementById("bg-canvas");'
        'import("./fx.js").then(function(m){m.init(c);});</script>'
    ) if has_fx else ""
    index_html = _HTML_DECK.format(
        title=html.escape(str(recipe.get("title", ""))),
        menu_links=menu_links,
        slides_html=slides_html,
        fx_canvas=fx_canvas,
        nav_js=_DECK_NAV_JS,
        fx_script=fx_script,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    (out_dir / "base.css").write_text(_build_base_css(base_dir), encoding="utf-8")
    (out_dir / "profile.css").write_text(
        (profile_dir / "tokens.css").read_text(encoding="utf-8"), encoding="utf-8"
    )
    if has_fx:
        shutil.copy(profile_dir / "fx" / "background.js", out_dir / "fx.js")


def main_assemble(
    output_type: str,
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
) -> None:
    if output_type == "landing" and "slides" in recipe:
        print("ERROR: type=landing recipe must not contain 'slides:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "deck" and "sections" in recipe:
        print("ERROR: type=deck recipe must not contain 'sections:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "landing":
        assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)
    else:
        assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir)
```

- [ ] **Step 4: Run all tests — expect all pass**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/assembler.py tests/h2t_creative/test_assembler.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): assembler deck pipeline + schema cross-contamination guard"
```

---

## Task 7: fx/ Support, dry-run, and CLI main()

**Files:**
- Modify: `plugins/h2t-creative/assembler.py` (add CLI main())
- Modify: `tests/h2t_creative/test_assembler.py` (add fx + dry-run tests)

- [ ] **Step 1: Add fx and dry-run tests**

Append to `tests/h2t_creative/test_assembler.py`:

```python
def test_fx_present_injects_canvas(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    fx_dir = profile_dir / "fx"
    fx_dir.mkdir()
    (fx_dir / "background.js").write_text("export function init(c){} export function destroy(){}")
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir)

    content = (out_dir / "index.html").read_text()
    assert 'id="bg-canvas"' in content
    assert (out_dir / "fx.js").exists()


def test_dry_run_does_not_write_files(tmp_path):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": [
        {"component": "hero", "content": {"headline": "Hi"}}
    ]}
    out_dir = tmp_path / "dist"
    assembler.dry_run(recipe, "landing", profile_dir, out_dir)

    assert not out_dir.exists()


def test_dry_run_prints_would_create(tmp_path, capsys):
    profile_dir, base_dir = _make_minimal_profile(tmp_path)
    recipe = {"type": "landing", "title": "T", "sections": []}
    out_dir = tmp_path / "dist"
    assembler.dry_run(recipe, "landing", profile_dir, out_dir)

    captured = capsys.readouterr()
    assert "index.html" in captured.out
    assert "base.css" in captured.out
    assert "profile.css" in captured.out
```

- [ ] **Step 2: Run new tests — expect AttributeError**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v -k "fx or dry_run"
```

Expected: `AttributeError: module 'assembler' has no attribute 'dry_run'`

- [ ] **Step 3: Add dry_run() and main() to assembler.py**

Append to `plugins/h2t-creative/assembler.py`:

```python
def dry_run(recipe: dict, output_type: str, profile_dir: Path, out_dir: Path) -> None:
    would_create = [
        str(out_dir / "index.html"),
        str(out_dir / "base.css"),
        str(out_dir / "profile.css"),
    ]
    if _has_fx(profile_dir):
        would_create.append(str(out_dir / "fx.js"))
    print(f"DRY RUN — would create ({len(would_create)} files):")
    for path in would_create:
        print(f"  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="h2t-creative assembler")
    parser.add_argument("--profile", required=True, help="Profile name under profiles/")
    parser.add_argument("--type", required=True, choices=["landing", "deck"])
    parser.add_argument("--recipe", required=True, help="Path to recipe.yaml")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    recipe = load_recipe(Path(args.recipe))
    profile_dir = PROFILES_DIR / args.profile
    if not profile_dir.exists():
        print(f"ERROR: profile '{args.profile}' not found at {profile_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)

    if args.dry_run:
        dry_run(recipe, args.type, profile_dir, out_dir)
        return

    main_assemble(args.type, recipe, profile_dir, out_dir)
    print(f"Built {args.type} -> {out_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests — expect all pass**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected: 20 passed

- [ ] **Step 5: Smoke test CLI with real profile**

Write recipe file and run assembler from the repo root:

```bash
python -c "
import textwrap, pathlib
pathlib.Path('/tmp/test_recipe.yaml').write_text(textwrap.dedent('''
type: landing
profile: h2t-default
title: Test Landing
sections:
  - component: nav
    content:
      brand_name: H2T
  - component: hero
    content:
      headline: Assembler works
      subline: Swiss grid in production
  - component: cta
    content:
      text: Get started
      href: https://hou2touch.ru
  - component: footer
    content:
      copy: \"2026 Hou2Touch\"
''').lstrip())
"
~/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-creative/assembler.py \
  --profile h2t-default --type landing \
  --recipe /tmp/test_recipe.yaml --out /tmp/test_dist
```

Expected: `Built landing -> /tmp/test_dist`

```bash
python -c "import os; print(os.listdir('/tmp/test_dist'))"
```

Expected: `['base.css', 'index.html', 'profile.css']` (order may vary)

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/assembler.py tests/h2t_creative/test_assembler.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): assembler fx/ support, dry-run, CLI main()"
```

---

## Task 8: Skills SKILL.md Files

**Files:**
- Create: `plugins/h2t-creative/skills/style-create/SKILL.md`
- Create: `plugins/h2t-creative/skills/style-validate/SKILL.md`
- Modify: `plugins/h2t-creative/skills/landing/SKILL.md`
- Modify: `plugins/h2t-creative/skills/deck/SKILL.md`

- [ ] **Step 1: Create style-create/SKILL.md**

```markdown
---
name: style-create
description: "Wizard to scaffold a new h2t-creative design profile directory. Creates DESIGN.md, tokens.css, 5 component templates (nav, hero, section, cta, footer) with manifest.yaml files. Optionally adds fx/ with Three.js boilerplate. Triggers: 'create profile', 'new design style', 'scaffold profile', 'style-create', 'h2t-creative:style-create'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: style-create

Scaffold a new visual profile for h2t-creative.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
PROFILES_DIR="$PLUGIN_ROOT/profiles"
```

## Wizard Steps

1. Ask: "Profile name?" (slug, e.g. `h2t-dark`, `workshop-2026`)
2. Ask: "Brand intent in 1-2 sentences? (aesthetic, mood, use case)"
3. Ask: "Primary color palette? (bg, fg, accent hex values, or describe)"
4. Ask: "Add Three.js/WebGL fx/ background? (y/n)"

Wait for all answers before proceeding.

## Scaffold

Create `$PROFILES_DIR/<name>/`:

```
DESIGN.md          ← generated from answers
tokens.css         ← CSS custom properties from palette answers
components/
  nav/nav.html + nav.css + manifest.yaml
  hero/hero.html + hero.css + manifest.yaml
  section/section.html + section.css + manifest.yaml
  cta/cta.html + cta.css + manifest.yaml
  footer/footer.html + footer.css + manifest.yaml
fx/                ← only if user said yes
  background.js    ← Three.js boilerplate stub
```

## Component Stubs

Copy component HTML/CSS from `h2t-default` profile as starting point, then update colors/fonts to match the new palette from tokens.css.

## fx/ Boilerplate (if requested)

```javascript
// fx/background.js
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js';

let renderer, scene, camera, animId;

export function init(canvas) {
  renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
  camera.position.z = 2;
  // TODO: add your geometry here
  animate();
}

function animate() {
  animId = requestAnimationFrame(animate);
  renderer.render(scene, camera);
}

export function destroy() {
  cancelAnimationFrame(animId);
  renderer.dispose();
}
```

## After Scaffold

Run: `h2t-creative:style-validate <name>` to confirm the profile is complete.
```

- [ ] **Step 2: Create style-validate/SKILL.md**

```markdown
---
name: style-validate
description: "Validates a h2t-creative profile directory for completeness. Checks DESIGN.md required sections, tokens.css required variables, all 5 components exist with manifest.yaml, fx/ exports contract if present. Triggers: 'validate profile', 'check style', 'style-validate', 'h2t-creative:style-validate'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: style-validate

Validate a profile directory for completeness before use.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
PROFILES_DIR="$PLUGIN_ROOT/profiles"
```

## Usage

Invoke with profile name: `h2t-creative:style-validate h2t-default`

## Checks

### 1. DESIGN.md required sections
Read `$PROFILES_DIR/<name>/DESIGN.md`. Must contain headings:
- `## Brand Intent`
- `## Color Tokens`
- `## Typography`
- `## Restrictions`

### 2. tokens.css required variables
Read `$PROFILES_DIR/<name>/tokens.css`. Must define:
`--color-bg`, `--color-fg`, `--color-accent`, `--font-display`, `--font-body`

### 3. Components inventory
The following must exist as directories with all three files:
- `components/nav/nav.html`, `nav.css`, `manifest.yaml`
- `components/hero/hero.html`, `hero.css`, `manifest.yaml`
- `components/section/section.html`, `section.css`, `manifest.yaml`
- `components/cta/cta.html`, `cta.css`, `manifest.yaml`
- `components/footer/footer.html`, `footer.css`, `manifest.yaml`

### 4. fx/ contract (only if fx/ directory exists)
Read `fx/background.js`. Must contain:
- `export function init(` — exported init function
- `export function destroy(` — exported destroy function

## Output

Report PASS/FAIL per check. On any failure: print the exact missing item and exit with non-zero.

Example:
```
✓ DESIGN.md — all required sections present
✓ tokens.css — all required variables defined
✓ components/nav — complete
✓ components/hero — complete
✗ components/section — missing section.css
```
```

- [ ] **Step 3: Rewrite skills/landing/SKILL.md**

```markdown
---
name: landing
description: "Generates a multi-file landing page using the h2t-creative assembler pipeline. Reads DESIGN.md profile as context, collaborates on recipe.yaml content, runs assembler.py, then performs Playwright QA at 375px and 1440px. Triggers: 'landing', 'create landing', 'landing page', 'h2t-creative:landing'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: landing

Generate a landing page via the assembler pipeline with mandatory Playwright QA.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
ASSEMBLER="$PLUGIN_ROOT/assembler.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Step 1: Choose profile

List available profiles:
```bash
ls "$PLUGIN_ROOT/profiles/"
```

Read `$PLUGIN_ROOT/profiles/<name>/DESIGN.md` as context before proceeding.

If no profile exists: offer to run `h2t-creative:style-create` first.

## Step 2: Build recipe.yaml

Collaborate with user on content. Schema:

```yaml
type: landing
profile: <profile-name>
title: "Page Title"
sections:
  - component: nav
    content:
      brand_name: "Brand"
  - component: hero
    content:
      headline: "Main headline"
      subline: "Supporting text"
  - component: section
    content:
      title: "Section Title"
      body: "<p>HTML content allowed here</p>"
  - component: cta
    content:
      text: "Call to action"
      href: "https://example.com"
  - component: footer
    content:
      copy: "© 2026 Brand"
```

Save as `recipe.yaml` in user's working directory (or a temp dir if unspecified).

## Step 3: Run assembler

```bash
$H2T_PYTHON "$ASSEMBLER" --profile <name> --type landing --recipe recipe.yaml --out ./dist
```

On error: print the assembler's stderr and stop.

## Step 4: Playwright QA

**Dependency check:** Verify `h2t-tools:playwright-agent` is available. If not:
> "ERROR: h2t-tools:playwright-agent plugin is required for delivery but is not installed.
> Install it from the Claude plugin store (search 'Playwright' by Microsoft), then retry.
> Delivery halted — dist/ is not ready until QA passes."
> **Stop here. Do not deliver dist/.**

If available, use the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`:

1. Open `dist/index.html` at 375px viewport → screenshot
2. Open `dist/index.html` at 1440px viewport → screenshot
3. Check for: text clipping, horizontal overflow, element collisions

## Step 5: Review and iterate

Examine screenshots. If issues found: adjust recipe.yaml and repeat from Step 3.

Deliver `dist/` only when QA passes.
```

- [ ] **Step 4: Rewrite skills/deck/SKILL.md**

```markdown
---
name: deck
description: "Generates a multi-file HTML presentation deck using the h2t-creative assembler pipeline. Keyboard navigation (←/→/Space), fixed slide menu, optional fx/. Performs Playwright QA per slide at 1440px. Triggers: 'deck', 'create presentation', 'make slides', 'презентация', 'h2t-creative:deck'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: deck

Generate a presentation deck via the assembler pipeline.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
ASSEMBLER="$PLUGIN_ROOT/assembler.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Step 1: Choose profile

```bash
ls "$PLUGIN_ROOT/profiles/"
```

Read `DESIGN.md` as context.

## Step 2: Build recipe.yaml

Deck schema uses `slides:` key (NOT `sections:`):

```yaml
type: deck
profile: <profile-name>
title: "Deck Title"
slides:
  - title: "Slide 1"
    layout: title-only
    content:
      headline: "Opening"
  - title: "Slide 2"
    layout: title-body
    content:
      headline: "Details"
      body: "<p>Body text or HTML.</p>"
      note: "Speaker note — not rendered, saved as HTML comment"
  - title: "Slide 3"
    layout: title-media
    content:
      headline: "Visual"
      media_url: "https://example.com/image.png"
  - title: "Blank"
    layout: blank
    content: {}
```

Available layouts: `title-only`, `title-body`, `title-media`, `blank`.

## Step 3: Run assembler

```bash
$H2T_PYTHON "$ASSEMBLER" --profile <name> --type deck --recipe recipe.yaml --out ./dist
```

## Step 4: Playwright QA

**Dependency check:** Verify `h2t-tools:playwright-agent` is available. If not:
> "ERROR: h2t-tools:playwright-agent plugin is required for delivery but is not installed.
> Install it from the Claude plugin store (search 'Playwright' by Microsoft), then retry.
> Delivery halted — dist/ is not ready until QA passes."
> **Stop here. Do not deliver dist/.**

If available, use the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`:

1. Screenshot slide 1 at 1440px viewport
2. Press `→` key → screenshot slide 2 (keyboard nav smoke test)
3. Click menu link for slide 3 → screenshot

## Step 5: Review and iterate

Deliver `dist/` only when QA passes.
```

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/skills/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): skills SKILL.md — style-create, style-validate, landing v2, deck v2"
```

---

## Task 9: Commands Migration + plugin.json

**Files:**
- Create: `plugins/h2t-creative/commands/style-create.md`
- Modify: `plugins/h2t-creative/commands/design.md`
- Modify: `plugins/h2t-creative/.claude-plugin/plugin.json`

(Note: `commands/landing.md` and `commands/deck.md` already follow the correct thin-wrapper pattern — no changes needed.)

- [ ] **Step 1: Create commands/style-create.md**

```markdown
---
description: "Style-Create: scaffold a new h2t-creative visual profile. Creates DESIGN.md, tokens.css, 5 component templates. Triggers: 'create profile', 'new design style', 'scaffold profile', 'style-create'."
---

Use the h2t-creative:style-create skill.
```

- [ ] **Step 2: Update commands/design.md (deprecation)**

Replace content of `plugins/h2t-creative/commands/design.md` with:

```markdown
---
description: "Design (deprecated): use /style-create instead. Redirects to h2t-creative:style-create for new design profile wizard."
---

> ⚠️ `/design` is deprecated. Use `/style-create` for the new profile wizard.

Use the h2t-creative:style-create skill.
```

- [ ] **Step 3: Update .claude-plugin/plugin.json**

Read current file first, then replace with:

```json
{
  "name": "h2t-creative",
  "description": "H2T Creative v2 — modular landing pages and decks: Swiss grid base, swappable profiles, Python assembler, Playwright QA.",
  "version": "1.0.1",
  "author": {
    "name": "lichtpfad"
  },
  "skills": [
    "style-create",
    "style-validate",
    "landing",
    "deck",
    "design"
  ]
}
```

- [ ] **Step 4: Run full test suite one final time**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/ -v
```

Expected: 20 passed, 0 failed

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-creative/commands/ plugins/h2t-creative/.claude-plugin/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): commands migration + plugin.json update (v1.0.1)"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec section | Covered by task |
|---|---|
| Layer 1 base CSS | Task 1 |
| Layer 2 profile (DESIGN.md, tokens, components, manifest) | Tasks 2-3 |
| Layer 3 assembler: interpolation + validation | Task 4 |
| Layer 3 assembler: landing output | Task 5 |
| Layer 3 assembler: deck output + slide layouts | Task 6 |
| Layer 3 assembler: fx/ + dry-run + CLI | Task 7 |
| Layer 4 skills (style-create, style-validate, landing, deck) | Task 8 |
| Commands migration + plugin.json | Task 9 |
| Playwright QA pipeline (described in skills) | Task 8 steps 3-4 |
| Migration story (design deprecated, landing/deck wrappers) | Task 9 |
| Semver: patch during impl, minor after live confirmation | Task 9 step 3 (1.0.1) |

**All spec requirements covered.** Three.js/WebGL integration is handled by fx/ support in Task 7 (assembler detects and copies background.js) + style-create boilerplate in Task 8 step 1.
