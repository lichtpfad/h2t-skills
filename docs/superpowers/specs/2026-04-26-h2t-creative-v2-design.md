---
title: "h2t-creative v2 Design Spec"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-04-26"
milestone: ""
---
# h2t-creative v2 Design Spec

**Date:** 2026-04-26
**Status:** Draft — pending approval
**Scope:** Landing pages + Decks. Instagram carousels: OUT OF SCOPE (future h2t-social plugin).

---

## 1. Architecture Overview

Four-layer system: immutable base → swappable profile → assembler → skills.

```
base/           ← Layer 1: CSS Grid foundation, immutable
profiles/       ← Layer 2: per-brand design system
assembler.py    ← Layer 3: combines layers → dist/
skills/         ← Layer 4: Claude-facing skill wrappers
```

**Key principles:**
- Content works without JS (progressive enhancement for fx/)
- Swiss grid via CSS Grid (not Flexbox for primary layout)
- Multi-file dist/ output → deploys to GitHub Pages or own hosting
- Playwright QA mandatory step before delivery

---

## 2. Layer 1 — Base (immutable)

Path: `plugins/h2t-creative/base/`

| File | Responsibility |
|------|---------------|
| `reset.css` | Modern CSS reset |
| `grid.css` | 12-column CSS Grid, mobile-first, fluid gutters |
| `typography.css` | Fluid scale with `clamp()`, no fixed px |
| `animations.css` | Transition + keyframe primitives |

**grid.css contract:**
```css
.grid          /* 12-column container */
.col-N         /* span N columns (1-12) */
.col-sm-N      /* responsive variants */
.section       /* section wrapper with vertical rhythm */
```

Base files are **never edited by profiles or assembler** — only extended.

---

## 3. Layer 2 — Profile (modular)

Path: `plugins/h2t-creative/profiles/{name}/`

```
profiles/h2t-default/
  DESIGN.md          ← AI context: brand intent, usage rules, restrictions
  tokens.css         ← CSS custom properties (colors, spacing, radius, z-index)
  components/
    nav.html + nav.css
    hero.html + hero.css
    section.html + section.css
    cta.html + cta.css
    footer.html + footer.css
  fx/                ← optional, progressive enhancement
    background.js    ← Three.js / WebGL scene
    *.glsl           ← shader files
```

**DESIGN.md schema (required fields):**
```markdown
# {Profile Name}

## Brand Intent
One paragraph — what aesthetic/emotion this profile targets.

## Color Tokens
- `--color-bg`: ...
- `--color-fg`: ...
- `--color-accent`: ...

## Typography
- `--font-display`: ...
- `--font-body`: ...

## Restrictions
- Do NOT use drop shadows
- Maintain 8px grid for spacing

## Usage Examples
When to use this profile, reference screenshots.
```

**tokens.css contract:** All values via `--` custom properties. Components reference only tokens, never hardcoded values.

**Component HTML + manifest contract:**

Each component directory contains three files:
```
components/hero/
  hero.html        ← template with {{ placeholder }} tokens
  hero.css         ← styles referencing CSS custom properties only
  manifest.yaml    ← field schema
```

`manifest.yaml` schema:
```yaml
component: hero
fields:
  headline:
    type: text       # text | html | url | int
    required: true
  subline:
    type: text
    required: false
    default: ""
  bg_image:
    type: url
    required: false
```

**Interpolation rules:**
- Placeholders in HTML: `{{ field_name }}` — HTML-escaped by default
- Raw HTML content: `{{ field_name | safe }}` — explicit opt-in, only for `type: html` fields
- Unknown placeholder in HTML with no matching recipe field → assembler hard-errors
- Missing required field in recipe → assembler hard-errors with field name
- Missing optional field → substituted with `default` value from manifest

Assembler validation sequence:
1. Load component manifest
2. Check all recipe `content` keys exist in manifest (no unknown fields)
3. Check all `required: true` fields are present in recipe content
4. Substitute and HTML-escape

**fx/ contract:**
- `background.js` exports `init(canvas)` and `destroy()`
- Assembler injects canvas element and calls `init()` after DOM ready
- If fx/ absent: assembler skips entirely, no JS in output

---

## 4. Layer 3 — Assembler

Path: `plugins/h2t-creative/assembler.py`

```bash
python assembler.py \
  --profile h2t-default \
  --type landing|deck \
  --recipe recipe.yaml \
  --out ./dist
```

**recipe.yaml — landing schema:**
```yaml
type: landing
profile: h2t-default
title: "Landing Page Title"
sections:
  - component: hero
    content:
      headline: "..."
      subline: "..."
  - component: section
    content:
      title: "..."
      body: "..."
  - component: cta
    content:
      text: "..."
      href: "..."
```

**recipe.yaml — deck schema** (separate key `slides:`, not `sections:`):
```yaml
type: deck
profile: h2t-default
title: "Deck Title"
slides:
  - title: "Slide 1 Title"
    layout: title-only   # title-only | title-body | title-media | blank
    content:
      headline: "..."
      body: "..."
  - title: "Slide 2 Title"
    layout: title-body
    content:
      headline: "..."
      body: "..."
      note: "Speaker note (not rendered, injected as HTML comment)"
```

Deck slide layouts are built-in to the assembler (not profile components) because slide structure is fixed and type-specific. Profile contributes styling only (via profile.css). Available layouts: `title-only`, `title-body`, `title-media`, `blank`.

Assembler hard-errors if `type: landing` recipe contains `slides:` or `type: deck` recipe contains `sections:`.

**Output — landing:**
```
dist/
  index.html    ← assembled HTML, inlined base + profile CSS references
  base.css      ← Layer 1 (copied, not modified)
  profile.css   ← tokens.css + all component CSS, concatenated
  fx.js         ← optional, only if fx/ present
```

**Output — deck:**
```
dist/
  index.html    ← slide wrapper with keyboard nav + slide menu
  base.css
  profile.css
  fx.js         ← optional
```

**Deck HTML contract:**
- Each `<section class="slide">` is one slide
- Keyboard: `←/→` + `Space` navigation
- Slide menu: fixed bar `Slide 1 | Slide 2 | ...` with active indicator
- URL hash updates on navigation (`#slide-1`, `#slide-2`)

**Assembler behavior:**
- Validates recipe against profile's component inventory
- Errors loudly on missing component or unknown field
- `--dry-run` prints would_create list without writing

---

## 5. Layer 4 — Skills

### `h2t-creative:style-create`
Wizard to scaffold a new profile:
1. Ask profile name + brand intent
2. Generate DESIGN.md draft (Claude fills values)
3. Generate tokens.css from brand description
4. Create component stubs
5. Optionally scaffold fx/ with Three.js boilerplate

### `h2t-creative:style-validate`
Checks profile for completeness:
- All required DESIGN.md fields present
- tokens.css defines all required `--` variables
- All components exist (nav, hero, section, cta, footer)
- fx/ present → background.js exports `init()` and `destroy()`

### `h2t-creative:landing`
Full pipeline:
1. Read DESIGN.md profile as context
2. Collaborate with user on recipe.yaml content
3. Run assembler.py
4. Playwright QA: 375px + 1440px screenshots
5. Claude reviews screenshots for layout issues
6. Iterate until approved

### `h2t-creative:deck`
Full pipeline:
1. Read DESIGN.md profile as context
2. Collaborate with user on recipe.yaml content (slides: schema)
3. Run assembler.py `--type deck`
4. Playwright QA: screenshot per slide at 1440px + keyboard nav smoke test
5. Iterate

---

## 6. Playwright QA Pipeline

Required for both landing and deck delivery.

**Runtime:** `h2t-tools:playwright-agent` — this is the official Microsoft Playwright MCP plugin installed from the Claude plugin marketplace (not part of h2t-skills repo). It is invoked via the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`. Confirmed installed in the user's Claude Code environment.

**Dependency status:** External plugin (Claude plugin store). If not installed, skill prints install instructions and halts. Skills must not assume it is present — check via `Agent` availability at skill entry point.

**Checks — landing:**
- 375px viewport (mobile): text not clipped, no horizontal overflow
- 1440px viewport (desktop): grid intact, no element collisions

**Checks — deck:**
- 1440px screenshot per slide (deck is desktop-primary)
- Keyboard `→` advances slides (smoke test: first 3 slides)
- Menu bar links navigate to correct slides

**Acceptance criteria:**
- Zero layout overflow at both viewports (landing) / 1440px (deck)
- Readable text (font-size ≥ 14px effective)
- CTA links present and clickable (landing)
- fx/ if present: no JS console errors

**Failure behavior:** assembler.py output is not committed until QA passes.

---

## 7. Three.js / WebGL Integration

**Approach:** Progressive enhancement, bundled inline.

- `fx/background.js` uses Three.js via CDN import or bundled (profile author's choice)
- Assembler detects fx/ presence → adds `<canvas id="bg-canvas">` + script tag
- `init(canvas)` called after `DOMContentLoaded`
- `destroy()` called on page unload or slide change (deck)

**Performance guardrails:**
- Canvas positioned `fixed`, `z-index: -1` (never blocks content)
- `requestAnimationFrame` loop, paused when `document.hidden`
- Assembler warns if fx/background.js > 50KB (excluding Three.js)

**Content independence:** All text, CTAs, navigation work with JS disabled (CSS-only fallback).

---

## 8. Repository Layout

```
plugins/h2t-creative/
  .claude-plugin/
    plugin.json          ← manifest (existing location, unchanged)
  base/                  ← NEW: Layer 1
    reset.css
    grid.css
    typography.css
    animations.css
  profiles/              ← NEW: Layer 2
    h2t-default/
      DESIGN.md
      tokens.css
      components/
        hero/hero.html + hero.css + manifest.yaml
        nav/nav.html + nav.css + manifest.yaml
        section/section.html + section.css + manifest.yaml
        cta/cta.html + cta.css + manifest.yaml
        footer/footer.html + footer.css + manifest.yaml
      fx/
  assembler.py           ← NEW: Layer 3
  skills/                ← Layer 4
    style-create/SKILL.md   ← NEW
    style-validate/SKILL.md ← NEW
    landing/SKILL.md        ← REWRITTEN (replaces commands/landing.md)
    deck/SKILL.md           ← REWRITTEN (replaces commands/deck.md)
  commands/
    landing.md           ← thin wrapper: invokes h2t-creative:landing skill
    deck.md              ← thin wrapper: invokes h2t-creative:deck skill
    style-create.md      ← NEW: slash command for profile wizard
    design.md            ← DEPRECATED: kept as alias, body says "use /style-create"
```

---

## 9. Migration from v1

**Current v1 state:** 3 commands (`/design`, `/landing`, `/deck`) with monolithic SKILL.md per command. No assembler, no profile system.

| v1 | v2 | Action |
|----|-----|--------|
| `commands/design.md` | `skills/style-create/` | Deprecated — `commands/design.md` becomes a one-liner redirecting to style-create |
| `commands/landing.md` | `skills/landing/` | Rewritten as thin wrapper (1-line invocation of new skill) |
| `commands/deck.md` | `skills/deck/` | Rewritten as thin wrapper |
| `skills/design/SKILL.md` | `skills/style-create/SKILL.md` | Rename + rewrite |
| `skills/landing/SKILL.md` | `skills/landing/SKILL.md` | Full rewrite (assembler-aware) |
| `skills/deck/SKILL.md` | `skills/deck/SKILL.md` | Full rewrite (deck-schema-aware) |
| `.claude-plugin/plugin.json` | `.claude-plugin/plugin.json` | Path unchanged; patch bumps during implementation (1.0.x); minor bump only after live confirmation |

**No breaking changes for the user:** `/landing` and `/deck` commands remain. `/design` stays as an alias with deprecation notice pointing to `/style-create` (which now has `commands/style-create.md`).

---

## 10. Out of Scope

- Instagram carousels (future: h2t-social plugin)
- CMS / dynamic data sources
- Build pipeline / bundler (Vite, webpack) — stdlib assembler only
- Authentication, forms processing

---

## 11. Open Questions (resolved)

| Question | Decision |
|----------|----------|
| Flexbox vs Grid | CSS Grid for primary layout, Flexbox allowed inside components for alignment |
| Monolith vs modular components | Modular: each component = `.html` + `.css` pair |
| Three.js loading | CDN import or local — profile author chooses |
| Hosting | GitHub Pages or own server, multi-file dist (no embed constraints) |
| Deck navigation | Keyboard `←/→/Space` + fixed slide menu bar |
