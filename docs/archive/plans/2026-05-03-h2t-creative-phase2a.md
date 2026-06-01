---
title: "h2t-creative Phase 2a Implementation Plan"
status: "draft"
date: "2026-05-03"
milestone: ""
---
# h2t-creative Phase 2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Smoke-test all 6 profiles × palettes, add shared-component fallback to assembler, create 6 shared landing components, provide 5 recipe templates.

**Architecture:** `plugins/h2t-creative/shared/components/<name>/` lives alongside `profiles/`. Assembler gets `_resolve_component_dir` that checks profile first, then shared. `_build_profile_css` loads shared CSS before profile CSS (cascade: tokens → palette → shared → profile override).

**Tech Stack:** Python 3.11 stdlib, pytest, HTML/CSS, YAML.

---

## File Map

**Create:**
- `plugins/h2t-creative/tests/__init__.py` — empty, marks package for pytest
- `plugins/h2t-creative/tests/conftest.py` — adds plugin root to sys.path
- `plugins/h2t-creative/tests/test_smoke.py` — 6 profiles × palettes smoke tests
- `plugins/h2t-creative/shared/components/features-grid/manifest.yaml`
- `plugins/h2t-creative/shared/components/features-grid/features-grid.html`
- `plugins/h2t-creative/shared/components/features-grid/features-grid.css`
- `plugins/h2t-creative/shared/components/stats/manifest.yaml`
- `plugins/h2t-creative/shared/components/stats/stats.html`
- `plugins/h2t-creative/shared/components/stats/stats.css`
- `plugins/h2t-creative/shared/components/testimonials/manifest.yaml`
- `plugins/h2t-creative/shared/components/testimonials/testimonials.html`
- `plugins/h2t-creative/shared/components/testimonials/testimonials.css`
- `plugins/h2t-creative/shared/components/pricing/manifest.yaml`
- `plugins/h2t-creative/shared/components/pricing/pricing.html`
- `plugins/h2t-creative/shared/components/pricing/pricing.css`
- `plugins/h2t-creative/shared/components/faq/manifest.yaml`
- `plugins/h2t-creative/shared/components/faq/faq.html`
- `plugins/h2t-creative/shared/components/faq/faq.css`
- `plugins/h2t-creative/shared/components/logos/manifest.yaml`
- `plugins/h2t-creative/shared/components/logos/logos.html`
- `plugins/h2t-creative/shared/components/logos/logos.css`
- `plugins/h2t-creative/recipes/landing-course.yaml`
- `plugins/h2t-creative/recipes/landing-product.yaml`
- `plugins/h2t-creative/recipes/landing-minimal.yaml`
- `plugins/h2t-creative/recipes/deck-pitch.yaml`
- `plugins/h2t-creative/recipes/deck-edu.yaml`

**Modify:**
- `plugins/h2t-creative/assembler.py` — add `SHARED_DIR`, `_resolve_component_dir`, update `_build_section_html` and `_build_profile_css`
- `plugins/h2t-creative/.claude-plugin/plugin.json` — bump to 1.1.0
- `.claude-plugin/marketplace.json` — bump h2t-creative entry to 1.1.0

---

## Task 1: Smoke baseline tests

**Files:**
- Create: `plugins/h2t-creative/tests/__init__.py`
- Create: `plugins/h2t-creative/tests/conftest.py`
- Create: `plugins/h2t-creative/tests/test_smoke.py`

- [ ] **Step 1.1: Create tests package**

```
plugins/h2t-creative/tests/__init__.py  (empty file)
```

Run: `echo $null > plugins\h2t-creative\tests\__init__.py` (PowerShell)

- [ ] **Step 1.2: Create conftest.py**

```python
# plugins/h2t-creative/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 1.3: Write test_smoke.py**

```python
# plugins/h2t-creative/tests/test_smoke.py
"""Smoke tests: every profile × palette assembles without error."""
import pytest
from pathlib import Path

import assembler as asm

PROFILES = {
    "h2t-default":   ["default"],
    "h2t-editorial": ["default", "night", "warm"],
    "h2t-graphs":    ["default", "blue", "green"],
    "h2t-mono":      ["default", "blue", "white"],
    "h2t-pfad":      ["default"],
    "h2t-terminal":  ["default", "amber", "cyan"],
}

_LANDING_RECIPE = {
    "title": "Smoke Test",
    "sections": [
        {"component": "hero", "content": {"headline": "Title", "subline": "Sub"}},
        {"component": "cta",  "content": {"text": "Go", "href": "https://example.com"}},
    ],
}

_DECK_RECIPE = {
    "title": "Smoke Deck",
    "slides": [
        {"layout": "title-only",  "content": {"headline": "Slide 1"}},
        {"layout": "title-body",  "content": {"headline": "Slide 2", "body": "<p>body</p>"}},
    ],
}

@pytest.mark.parametrize("profile,palette", [
    (p, pal) for p, pals in PROFILES.items() for pal in pals
])
def test_landing_smoke(tmp_path, profile, palette):
    profile_dir = asm.PROFILES_DIR / profile
    out = tmp_path / "out"
    asm.assemble_landing(_LANDING_RECIPE, profile_dir, out, palette=palette)
    assert (out / "index.html").exists()
    assert (out / "base.css").exists()
    assert (out / "profile.css").exists()

@pytest.mark.parametrize("profile", list(PROFILES.keys()))
def test_deck_smoke(tmp_path, profile):
    profile_dir = asm.PROFILES_DIR / profile
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, profile_dir, out)
    assert (out / "index.html").exists()
    assert (out / "profile.css").exists()
```

- [ ] **Step 1.4: Run tests — verify they pass**

Run from `C:/dev/h2t-skills`:
```
py -3.11 -m pytest plugins/h2t-creative/tests/ -v
```

Expected: all tests PASS (14 landing + 6 deck = 20 tests).

If any FAIL: profiles or palettes missing. Fix the profile/palette before proceeding.

- [ ] **Step 1.5: Commit**

```
git add plugins/h2t-creative/tests/
git commit -m "test(h2t-creative): smoke tests for all 6 profiles × palettes"
```

---

## Task 2: Assembler shared-component fallback

**Files:**
- Modify: `plugins/h2t-creative/assembler.py` (lines 11-12, 105-118, 137-145)

- [ ] **Step 2.1: Add SHARED_DIR constant (non-logic, safe first step)**

In `plugins/h2t-creative/assembler.py`, after line 12 (`PROFILES_DIR = PLUGIN_ROOT / "profiles"`):

```python
SHARED_DIR = PLUGIN_ROOT / "shared"
```

This is just a path constant — nothing in the assembler uses it yet. Adding it first makes `asm.SHARED_DIR` available in the test.

- [ ] **Step 2.2: Write failing test for shared fallback**

Add to `plugins/h2t-creative/tests/test_smoke.py` (append at the bottom):

```python
def test_shared_component_fallback(tmp_path):
    """Component from shared/ is used when not in profile."""
    comp_dir = asm.SHARED_DIR / "components" / "_test_shared_comp"
    comp_dir.mkdir(parents=True, exist_ok=True)
    try:
        (comp_dir / "manifest.yaml").write_text(
            "component: _test_shared_comp\nfields:\n  msg:\n    type: text\n    required: true\n",
            encoding="utf-8",
        )
        (comp_dir / "_test_shared_comp.html").write_text(
            "<div class='test'>{{ msg }}</div>", encoding="utf-8"
        )
        (comp_dir / "_test_shared_comp.css").write_text(".test {}", encoding="utf-8")

        recipe = {
            "title": "Shared Test",
            "sections": [
                {"component": "_test_shared_comp", "content": {"msg": "hello"}},
            ],
        }
        out = tmp_path / "out"
        asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", out)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "hello" in html
    finally:
        import shutil
        shutil.rmtree(comp_dir)
```

- [ ] **Step 2.3: Run — verify new test FAILS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_component_fallback -v
```

Expected: FAIL with `ValueError: Component '_test_shared_comp' not found`
(Not `AttributeError` — `SHARED_DIR` exists now, but the assembler doesn't use it yet.)

- [ ] **Step 2.4: Add `_resolve_component_dir` function**

In `assembler.py`, insert after `def load_manifest` (after line 63):

```python
def _resolve_component_dir(component_name: str, profile_dir: Path, shared_dir: Path = SHARED_DIR) -> Path:
    profile_comp = profile_dir / "components" / component_name
    if profile_comp.exists():
        return profile_comp
    shared_comp = shared_dir / "components" / component_name
    if shared_comp.exists():
        return shared_comp
    raise ValueError(
        f"Component '{component_name}' not found in profile '{profile_dir.name}' or shared/"
    )
```

- [ ] **Step 2.5: Update `_build_section_html` to use `_resolve_component_dir`**

Replace in `_build_section_html` (current lines 106-109):

```python
    # OLD:
    component_dir = profile_dir / "components" / component_name
    if not component_dir.exists():
        raise ValueError(f"Component '{component_name}' not found in profile at {component_dir}")
```

with:

```python
    # NEW:
    component_dir = _resolve_component_dir(component_name, profile_dir)
```

- [ ] **Step 2.6: Update `_build_profile_css` for shared CSS cascade**

Replace the `seen` loop in `_build_profile_css` (current lines 137-145):

```python
    # OLD:
    seen: set = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
            seen.add(name)
```

with:

```python
    # NEW — cascade: shared base CSS first, then profile override
    seen: set = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            shared_css = SHARED_DIR / "components" / name / f"{name}.css"
            if shared_css.exists():
                parts.append(shared_css.read_text(encoding="utf-8"))
            profile_css = profile_dir / "components" / name / f"{name}.css"
            if profile_css.exists():
                parts.append(profile_css.read_text(encoding="utf-8"))
            seen.add(name)
```

- [ ] **Step 2.7: Write CSS cascade test**

Append to `test_smoke.py`:

```python
def test_css_cascade_order(tmp_path):
    """Shared CSS appears strictly BEFORE profile override CSS in profile.css."""
    import shutil

    shared_comp = asm.SHARED_DIR / "components" / "_test_cascade_comp"
    profile_comp = asm.PROFILES_DIR / "h2t-default" / "components" / "_test_cascade_comp"
    manifest_text = (
        "component: _test_cascade_comp\n"
        "fields:\n  x:\n    type: text\n    required: false\n    default: ''\n"
    )
    html_text = "<div>{{ x }}</div>"

    shared_comp.mkdir(parents=True, exist_ok=True)
    profile_comp.mkdir(parents=True, exist_ok=True)
    try:
        for d, marker in [(shared_comp, "SHARED_MARKER"), (profile_comp, "PROFILE_MARKER")]:
            (d / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
            (d / "_test_cascade_comp.html").write_text(html_text, encoding="utf-8")
            (d / "_test_cascade_comp.css").write_text(f"/* {marker} */", encoding="utf-8")

        recipe = {
            "title": "Cascade Test",
            "sections": [{"component": "_test_cascade_comp", "content": {}}],
        }
        out = tmp_path / "out"
        asm.assemble_landing(recipe, asm.PROFILES_DIR / "h2t-default", out)
        css = (out / "profile.css").read_text(encoding="utf-8")
        assert "SHARED_MARKER" in css, "shared CSS missing from profile.css"
        assert "PROFILE_MARKER" in css, "profile override CSS missing from profile.css"
        assert css.index("SHARED_MARKER") < css.index("PROFILE_MARKER"), (
            "shared CSS must appear before profile override CSS"
        )
    finally:
        shutil.rmtree(shared_comp)
        shutil.rmtree(profile_comp)
```

- [ ] **Step 2.8: Run — verify cascade test passes**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_css_cascade_order -v
```

Expected: PASS (shared CSS is loaded by `_build_profile_css`)

- [ ] **Step 2.9: Run all tests — verify all pass**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -v
```

Expected: all 22 tests PASS (20 smoke + 1 fallback + 1 cascade).

- [ ] **Step 2.10: Commit**

```
git add plugins/h2t-creative/assembler.py plugins/h2t-creative/tests/test_smoke.py
git commit -m "feat(h2t-creative): assembler shared-component fallback + CSS cascade"
```

---

## Task 3: Shared component `features-grid`

3-column feature cards. Each card: emoji icon + title + body text.

**Files:**
- Create: `plugins/h2t-creative/shared/components/features-grid/manifest.yaml`
- Create: `plugins/h2t-creative/shared/components/features-grid/features-grid.html`
- Create: `plugins/h2t-creative/shared/components/features-grid/features-grid.css`

- [ ] **Step 3.1: Write failing test**

Add to `test_smoke.py`:

```python
def test_shared_features_grid(tmp_path):
    recipe = {
        "title": "FG Test",
        "sections": [{
            "component": "features-grid",
            "content": {
                "item1_icon": "🔥", "item1_title": "A", "item1_body": "Body A",
                "item2_icon": "⚡", "item2_title": "B", "item2_body": "Body B",
                "item3_icon": "🎯", "item3_title": "C", "item3_body": "Body C",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Body A" in html
    assert "Body C" in html
```

- [ ] **Step 3.2: Run — verify FAILS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_features_grid -v
```

Expected: FAIL with `ValueError: Component 'features-grid' not found`

- [ ] **Step 3.3: Create manifest.yaml**

```yaml
# plugins/h2t-creative/shared/components/features-grid/manifest.yaml
component: features-grid
fields:
  title:
    type: text
    required: false
    default: ""
  item1_icon:
    type: text
    required: true
  item1_title:
    type: text
    required: true
  item1_body:
    type: text
    required: true
  item2_icon:
    type: text
    required: true
  item2_title:
    type: text
    required: true
  item2_body:
    type: text
    required: true
  item3_icon:
    type: text
    required: true
  item3_title:
    type: text
    required: true
  item3_body:
    type: text
    required: true
```

- [ ] **Step 3.4: Create features-grid.html**

```html
<!-- plugins/h2t-creative/shared/components/features-grid/features-grid.html -->
<section class="section features-grid">
  <div class="grid">
    <div class="col-12">
      <h2 class="features-grid__heading">{{ title }}</h2>
    </div>
    <div class="col-4 col-sm-12 features-grid__item">
      <span class="features-grid__icon">{{ item1_icon }}</span>
      <h3 class="features-grid__title">{{ item1_title }}</h3>
      <p class="features-grid__body">{{ item1_body }}</p>
    </div>
    <div class="col-4 col-sm-12 features-grid__item">
      <span class="features-grid__icon">{{ item2_icon }}</span>
      <h3 class="features-grid__title">{{ item2_title }}</h3>
      <p class="features-grid__body">{{ item2_body }}</p>
    </div>
    <div class="col-4 col-sm-12 features-grid__item">
      <span class="features-grid__icon">{{ item3_icon }}</span>
      <h3 class="features-grid__title">{{ item3_title }}</h3>
      <p class="features-grid__body">{{ item3_body }}</p>
    </div>
  </div>
</section>
```

- [ ] **Step 3.5: Create features-grid.css**

```css
/* plugins/h2t-creative/shared/components/features-grid/features-grid.css */
.features-grid__heading:empty { display: none; }
.features-grid__heading { font-family: var(--font-display); margin-bottom: var(--space-lg); }
.features-grid__item { display: flex; flex-direction: column; gap: var(--space-sm); }
.features-grid__icon { font-size: 2rem; line-height: 1; }
.features-grid__title { font-family: var(--font-display); color: var(--color-fg); margin: 0; }
.features-grid__body { color: var(--color-muted); margin: 0; }
```

- [ ] **Step 3.6: Run — verify test passes**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_features_grid -v
```

Expected: PASS

- [ ] **Step 3.7: Commit**

```
git add plugins/h2t-creative/shared/
git add plugins/h2t-creative/tests/test_smoke.py
git commit -m "feat(h2t-creative): shared features-grid component"
```

---

## Task 4: Shared components `stats` and `testimonials`

**Files:**
- Create: `plugins/h2t-creative/shared/components/stats/` (3 files)
- Create: `plugins/h2t-creative/shared/components/testimonials/` (3 files)

- [ ] **Step 4.1: Write failing tests**

Append to `test_smoke.py`:

```python
def test_shared_stats(tmp_path):
    recipe = {
        "title": "Stats Test",
        "sections": [{
            "component": "stats",
            "content": {
                "stat1_value": "120+", "stat1_label": "Lessons",
                "stat2_value": "12h",  "stat2_label": "Runtime",
                "stat3_value": "2500+","stat3_label": "Students",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "120+" in html
    assert "Students" in html


def test_shared_testimonials(tmp_path):
    recipe = {
        "title": "Testimonials Test",
        "sections": [{
            "component": "testimonials",
            "content": {
                "quote": "Best course ever.",
                "author": "Jane Smith",
                "role": "Motion Designer",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Best course ever." in html
    assert "Jane Smith" in html
```

- [ ] **Step 4.2: Run — verify both FAIL**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_stats plugins/h2t-creative/tests/test_smoke.py::test_shared_testimonials -v
```

Expected: both FAIL with `ValueError: Component '...' not found`

- [ ] **Step 4.3: Create stats component**

`shared/components/stats/manifest.yaml`:
```yaml
component: stats
fields:
  stat1_value:
    type: text
    required: true
  stat1_label:
    type: text
    required: true
  stat2_value:
    type: text
    required: true
  stat2_label:
    type: text
    required: true
  stat3_value:
    type: text
    required: true
  stat3_label:
    type: text
    required: true
```

`shared/components/stats/stats.html`:
```html
<section class="section stats">
  <div class="grid">
    <div class="col-4 col-sm-12 stats__item">
      <span class="stats__value">{{ stat1_value }}</span>
      <span class="stats__label">{{ stat1_label }}</span>
    </div>
    <div class="col-4 col-sm-12 stats__item">
      <span class="stats__value">{{ stat2_value }}</span>
      <span class="stats__label">{{ stat2_label }}</span>
    </div>
    <div class="col-4 col-sm-12 stats__item">
      <span class="stats__value">{{ stat3_value }}</span>
      <span class="stats__label">{{ stat3_label }}</span>
    </div>
  </div>
</section>
```

`shared/components/stats/stats.css`:
```css
.stats { text-align: center; }
.stats__item { display: flex; flex-direction: column; gap: var(--space-xs); }
.stats__value { font-family: var(--font-display); font-size: 2.5rem; font-weight: 700; color: var(--color-accent); }
.stats__label { font-size: 0.875rem; color: var(--color-muted); text-transform: uppercase; letter-spacing: 0.05em; }
```

- [ ] **Step 4.4: Create testimonials component**

`shared/components/testimonials/manifest.yaml`:
```yaml
component: testimonials
fields:
  quote:
    type: text
    required: true
  author:
    type: text
    required: true
  role:
    type: text
    required: false
    default: ""
```

`shared/components/testimonials/testimonials.html`:
```html
<section class="section testimonials">
  <div class="grid">
    <div class="col-8 col-sm-12">
      <blockquote class="testimonials__quote">{{ quote }}</blockquote>
      <cite class="testimonials__cite">
        <span class="testimonials__author">{{ author }}</span>
        <span class="testimonials__role">{{ role }}</span>
      </cite>
    </div>
  </div>
</section>
```

`shared/components/testimonials/testimonials.css`:
```css
.testimonials__quote { font-size: 1.25rem; color: var(--color-fg); border-left: 4px solid var(--color-accent); padding-left: var(--space-lg); margin: 0 0 var(--space-md); font-style: italic; }
.testimonials__cite { display: flex; flex-direction: column; gap: var(--space-xs); padding-left: var(--space-lg); font-style: normal; }
.testimonials__author { font-weight: 700; color: var(--color-fg); }
.testimonials__role:empty { display: none; }
.testimonials__role { color: var(--color-muted); font-size: 0.875rem; }
```

- [ ] **Step 4.5: Run — verify both pass**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_stats plugins/h2t-creative/tests/test_smoke.py::test_shared_testimonials -v
```

Expected: both PASS

- [ ] **Step 4.6: Commit**

```
git add plugins/h2t-creative/shared/ plugins/h2t-creative/tests/test_smoke.py
git commit -m "feat(h2t-creative): shared stats + testimonials components"
```

---

## Task 5: Shared components `pricing`, `faq`, `logos`

**Files:**
- Create: `plugins/h2t-creative/shared/components/pricing/` (3 files)
- Create: `plugins/h2t-creative/shared/components/faq/` (3 files)
- Create: `plugins/h2t-creative/shared/components/logos/` (3 files)

- [ ] **Step 5.1: Write failing tests**

Append to `test_smoke.py`:

```python
def test_shared_pricing(tmp_path):
    recipe = {
        "title": "Pricing Test",
        "sections": [{
            "component": "pricing",
            "content": {
                "plan_name": "Full Access",
                "price": "$149",
                "period": "one-time",
                "features": "<li>Lifetime access</li><li>All updates</li>",
                "cta_text": "Enrol Now",
                "cta_href": "https://example.com/checkout",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "$149" in html
    assert "Enrol Now" in html


def test_shared_faq(tmp_path):
    recipe = {
        "title": "FAQ Test",
        "sections": [{
            "component": "faq",
            "content": {
                "title": "FAQ",
                "body": "<div><dt>Q?</dt><dd>A.</dd></div>",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Q?" in html


def test_shared_logos(tmp_path):
    recipe = {
        "title": "Logos Test",
        "sections": [{
            "component": "logos",
            "content": {
                "logos": "<span>Acme</span><span>Corp</span>",
            },
        }],
    }
    profile_dir = asm.PROFILES_DIR / "h2t-default"
    asm.assemble_landing(recipe, profile_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Acme" in html
```

- [ ] **Step 5.2: Run — verify all three FAIL**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_pricing plugins/h2t-creative/tests/test_smoke.py::test_shared_faq plugins/h2t-creative/tests/test_smoke.py::test_shared_logos -v
```

Expected: all three FAIL

- [ ] **Step 5.3: Create pricing component**

`shared/components/pricing/manifest.yaml`:
```yaml
component: pricing
fields:
  plan_name:
    type: text
    required: true
  price:
    type: text
    required: true
  period:
    type: text
    required: false
    default: ""
  features:
    type: html
    required: false
    default: ""
  cta_text:
    type: text
    required: true
  cta_href:
    type: url
    required: true
```

`shared/components/pricing/pricing.html`:
```html
<section class="section pricing">
  <div class="grid">
    <div class="col-6 col-sm-12 pricing__card">
      <h2 class="pricing__plan">{{ plan_name }}</h2>
      <div class="pricing__price-row">
        <span class="pricing__price">{{ price }}</span>
        <span class="pricing__period">{{ period }}</span>
      </div>
      <ul class="pricing__features">{{ features | safe }}</ul>
      <a href="{{ cta_href }}" class="pricing__cta">{{ cta_text }}</a>
    </div>
  </div>
</section>
```

`shared/components/pricing/pricing.css`:
```css
.pricing__card { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-xl); display: flex; flex-direction: column; gap: var(--space-md); }
.pricing__plan { font-family: var(--font-display); margin: 0; }
.pricing__price-row { display: flex; align-items: baseline; gap: var(--space-sm); }
.pricing__price { font-size: 2.5rem; font-weight: 700; color: var(--color-accent); }
.pricing__period { color: var(--color-muted); font-size: 0.875rem; }
.pricing__features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-sm); color: var(--color-muted); }
.pricing__features li::before { content: "✓ "; color: var(--color-accent); }
.pricing__cta { display: inline-block; background-color: var(--color-accent); color: #fff; padding: var(--space-md) var(--space-xl); border-radius: var(--radius-md); text-decoration: none; font-weight: 700; text-align: center; }
.pricing__cta:hover { background-color: var(--color-accent-hover); }
```

- [ ] **Step 5.4: Create faq component**

`shared/components/faq/manifest.yaml`:
```yaml
component: faq
fields:
  title:
    type: text
    required: false
    default: ""
  body:
    type: html
    required: true
```

`shared/components/faq/faq.html`:
```html
<section class="section faq">
  <div class="grid">
    <div class="col-8 col-sm-12">
      <h2 class="faq__title">{{ title }}</h2>
      <dl class="faq__list">{{ body | safe }}</dl>
    </div>
  </div>
</section>
```

`shared/components/faq/faq.css`:
```css
.faq__title:empty { display: none; }
.faq__title { font-family: var(--font-display); margin-bottom: var(--space-lg); }
.faq__list { display: flex; flex-direction: column; gap: var(--space-lg); }
.faq__list dt { font-weight: 700; color: var(--color-fg); margin-bottom: var(--space-xs); }
.faq__list dd { color: var(--color-muted); margin-left: 0; }
```

- [ ] **Step 5.5: Create logos component**

`shared/components/logos/manifest.yaml`:
```yaml
component: logos
fields:
  title:
    type: text
    required: false
    default: ""
  logos:
    type: html
    required: true
```

`shared/components/logos/logos.html`:
```html
<section class="section logos">
  <div class="grid">
    <div class="col-12">
      <p class="logos__title">{{ title }}</p>
      <div class="logos__strip">{{ logos | safe }}</div>
    </div>
  </div>
</section>
```

`shared/components/logos/logos.css`:
```css
.logos__title:empty { display: none; }
.logos__title { text-align: center; font-size: 0.875rem; color: var(--color-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-md); }
.logos__strip { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: var(--space-xl); color: var(--color-muted); }
```

- [ ] **Step 5.6: Run — verify all three pass**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_smoke.py::test_shared_pricing plugins/h2t-creative/tests/test_smoke.py::test_shared_faq plugins/h2t-creative/tests/test_smoke.py::test_shared_logos -v
```

Expected: all three PASS

- [ ] **Step 5.7: Commit**

```
git add plugins/h2t-creative/shared/ plugins/h2t-creative/tests/test_smoke.py
git commit -m "feat(h2t-creative): shared pricing + faq + logos components"
```

---

## Task 6: Recipe templates

5 reference recipes in `plugins/h2t-creative/recipes/`.

**Files:** All new.

- [ ] **Step 6.1: Create landing-course.yaml**

```yaml
# plugins/h2t-creative/recipes/landing-course.yaml
# Full course landing page: nav → hero → features → stats → testimonials → pricing → faq → footer
type: landing
profile: h2t-default
palette: default
title: "Course Title — Your Subtitle"

sections:
  - component: nav
    content:
      brand_name: "Brand"
      home_href: "/"

  - component: hero
    content:
      headline: "Learn Something Powerful"
      subline: "A short description of who this is for and what they will achieve."

  - component: features-grid
    content:
      title: "What You'll Learn"
      item1_icon: "📐"
      item1_title: "Foundations"
      item1_body: "Core principles explained from first principles."
      item2_icon: "⚡"
      item2_title: "Workflow"
      item2_body: "Production-ready techniques you can apply immediately."
      item3_icon: "🎯"
      item3_title: "Projects"
      item3_body: "Hands-on projects to build your portfolio."

  - component: stats
    content:
      stat1_value: "120+"
      stat1_label: "Video Lessons"
      stat2_value: "12h"
      stat2_label: "Total Runtime"
      stat3_value: "2500+"
      stat3_label: "Students"

  - component: testimonials
    content:
      quote: "This course completely changed how I work. Worth every cent."
      author: "Jane Smith"
      role: "Motion Designer, Berlin"

  - component: pricing
    content:
      plan_name: "Full Access"
      price: "$149"
      period: "one-time"
      features: "<li>Lifetime access</li><li>All future updates</li><li>Community forum</li>"
      cta_text: "Enrol Now"
      cta_href: "https://example.com/checkout"

  - component: faq
    content:
      title: "Frequently Asked Questions"
      body: |
        <div><dt>How long do I have access?</dt><dd>Forever — all updates included.</dd></div>
        <div><dt>What software do I need?</dt><dd>Houdini FX 20.x or later (free apprentice edition works).</dd></div>
        <div><dt>Is there a money-back guarantee?</dt><dd>Yes — 14 days, no questions asked.</dd></div>

  - component: footer
    content:
      copy: "© 2026 Brand. All rights reserved."
```

- [ ] **Step 6.2: Create landing-product.yaml**

```yaml
# plugins/h2t-creative/recipes/landing-product.yaml
# Product / tool landing page: nav → hero → features → logos → pricing → footer
type: landing
profile: h2t-default
palette: default
title: "Product Name — Tagline"

sections:
  - component: nav
    content:
      brand_name: "Product"
      home_href: "/"

  - component: hero
    content:
      headline: "The Tool That Does X"
      subline: "Built for professionals who need Y without the Z overhead."

  - component: features-grid
    content:
      item1_icon: "🚀"
      item1_title: "Fast"
      item1_body: "Ships in seconds, not minutes."
      item2_icon: "🔒"
      item2_title: "Reliable"
      item2_body: "Zero-downtime architecture."
      item3_icon: "🧩"
      item3_title: "Extensible"
      item3_body: "Plugin system for custom workflows."

  - component: logos
    content:
      title: "Trusted by teams at"
      logos: "<span>Acme Corp</span><span>Studio XY</span><span>Lab 42</span>"

  - component: pricing
    content:
      plan_name: "Pro"
      price: "$29"
      period: "/ month"
      features: "<li>Unlimited projects</li><li>Priority support</li><li>API access</li>"
      cta_text: "Start Free Trial"
      cta_href: "https://example.com/signup"

  - component: footer
    content:
      copy: "© 2026 Product Inc."
```

- [ ] **Step 6.3: Create landing-minimal.yaml**

```yaml
# plugins/h2t-creative/recipes/landing-minimal.yaml
# Minimal landing: nav → hero → cta → footer (fastest to scaffold)
type: landing
profile: h2t-default
palette: default
title: "Name — Tagline"

sections:
  - component: nav
    content:
      brand_name: "Brand"

  - component: hero
    content:
      headline: "Headline"
      subline: "Subline."

  - component: cta
    content:
      text: "Get Started"
      href: "https://example.com"

  - component: footer
    content:
      copy: "© 2026 Brand."
```

- [ ] **Step 6.4: Create deck-pitch.yaml**

```yaml
# plugins/h2t-creative/recipes/deck-pitch.yaml
# Pitch deck: title → problem → solution → market → traction → team → ask
type: deck
profile: h2t-default
palette: default
title: "Company Name — Pitch Deck"

slides:
  - layout: title-only
    title: "Cover"
    content:
      headline: "Company Name"

  - layout: title-body
    title: "Problem"
    content:
      headline: "The Problem"
      body: "<p>Describe the pain point clearly. One paragraph, no jargon.</p>"

  - layout: title-body
    title: "Solution"
    content:
      headline: "Our Solution"
      body: "<p>One sentence. Then 3 bullets: how it works, why it's unique, what it replaces.</p>"

  - layout: title-body
    title: "Market"
    content:
      headline: "Market Size"
      body: "<p>TAM / SAM / SOM with credible sources.</p>"

  - layout: title-body
    title: "Traction"
    content:
      headline: "Traction"
      body: "<p>Key metrics, logos of customers, growth numbers.</p>"

  - layout: title-body
    title: "Team"
    content:
      headline: "Team"
      body: "<p>Founders with relevant credentials in 2–3 lines each.</p>"

  - layout: title-body
    title: "Ask"
    content:
      headline: "The Ask"
      body: "<p>Amount, use of funds breakdown (3–4 lines).</p>"
```

- [ ] **Step 6.5: Create deck-edu.yaml**

```yaml
# plugins/h2t-creative/recipes/deck-edu.yaml
# Educational lesson deck: agenda → concepts → demo → summary → Q&A
type: deck
profile: h2t-default
palette: default
title: "Lesson Title"

slides:
  - layout: title-only
    title: "Title"
    content:
      headline: "Lesson Title"

  - layout: title-body
    title: "Agenda"
    content:
      headline: "Today's Agenda"
      body: "<ol><li>Concept A</li><li>Concept B</li><li>Hands-on demo</li><li>Q&A</li></ol>"

  - layout: title-body
    title: "Concept A"
    content:
      headline: "Concept A"
      body: "<p>Explain the concept. Use analogies. Keep to one idea per slide.</p>"

  - layout: title-body
    title: "Concept B"
    content:
      headline: "Concept B"
      body: "<p>Second concept. Connect it to Concept A.</p>"

  - layout: title-body
    title: "Demo"
    content:
      headline: "Hands-On Demo"
      body: "<p>Step-by-step instructions for the demo. Reference files: <code>demo/scene.hip</code>.</p>"

  - layout: title-body
    title: "Summary"
    content:
      headline: "Key Takeaways"
      body: "<ul><li>Takeaway from Concept A</li><li>Takeaway from Concept B</li><li>When to use this technique</li></ul>"

  - layout: title-only
    title: "Q&A"
    content:
      headline: "Questions?"
```

- [ ] **Step 6.6: Verify recipes assemble without error**

Run each recipe through the assembler to confirm no field mismatches:

```
py -3.11 plugins/h2t-creative/assembler.py --profile h2t-default --type landing --recipe plugins/h2t-creative/recipes/landing-course.yaml --out /tmp/h2t-test/course
py -3.11 plugins/h2t-creative/assembler.py --profile h2t-default --type landing --recipe plugins/h2t-creative/recipes/landing-product.yaml --out /tmp/h2t-test/product
py -3.11 plugins/h2t-creative/assembler.py --profile h2t-default --type landing --recipe plugins/h2t-creative/recipes/landing-minimal.yaml --out /tmp/h2t-test/minimal
py -3.11 plugins/h2t-creative/assembler.py --profile h2t-default --type deck --recipe plugins/h2t-creative/recipes/deck-pitch.yaml --out /tmp/h2t-test/pitch
py -3.11 plugins/h2t-creative/assembler.py --profile h2t-default --type deck --recipe plugins/h2t-creative/recipes/deck-edu.yaml --out /tmp/h2t-test/edu
```

Expected: `Built landing -> ...` for landing recipes, `Built deck -> ...` for deck recipes. No errors.

On Windows, use `$env:TEMP` as output: `--out "$env:TEMP\h2t-test\course"` etc.

- [ ] **Step 6.7: Commit**

```
git add plugins/h2t-creative/recipes/
git commit -m "feat(h2t-creative): recipe templates — landing-course, landing-product, landing-minimal, deck-pitch, deck-edu"
```

---

## Task 7: Full test run + version bump

**Files:**
- Modify: `plugins/h2t-creative/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 7.1: Run full test suite**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -v
```

Expected: all 28 tests PASS:
- 14 landing smoke (h2t-default×1, editorial×3, graphs×3, mono×3, pfad×1, terminal×3)
- 6 deck smoke (1 per profile)
- 1 test_shared_component_fallback
- 1 test_css_cascade_order
- 6 shared component tests (features-grid, stats, testimonials, pricing, faq, logos)

If any test fails, fix before proceeding.

- [ ] **Step 7.2: Bump plugin to 1.1.0**

```
py -3.11 scripts/bump_plugin.py h2t-creative 1.1.0
```

Expected output:
```
✓ h2t-creative: 1.0.x → 1.1.0
  updated: plugins/h2t-creative/.claude-plugin/plugin.json
  updated: .claude-plugin/marketplace.json
```

- [ ] **Step 7.3: Final commit**

```
git add plugins/h2t-creative/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(h2t-creative): bump to v1.1.0 — Phase 2a complete"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Smoke tests for all 6 profiles × all palettes → Task 1
- [x] Shared component fallback in assembler → Task 2
- [x] 6 shared landing components (features-grid, stats, testimonials, pricing, faq, logos) → Tasks 3–5
- [x] 5 recipe templates (landing-course, landing-product, landing-minimal, deck-pitch, deck-edu) → Task 6
- [x] Version bump → Task 7

**Placeholder scan:** No TBD, no "implement later", no "similar to Task N". All code blocks are complete.

**Type consistency:**
- `_resolve_component_dir(component_name: str, profile_dir: Path, shared_dir: Path)` — used consistently in Task 2
- `SHARED_DIR` constant — added in Step 2.1 before any test references `asm.SHARED_DIR`; used in `_resolve_component_dir` and `_build_profile_css`
- All component manifest field names match HTML template placeholders exactly
- `bump_plugin.py` modifies both `plugin.json` and `marketplace.json` — both files in git add (Task 7 Step 7.3)
