---
title: h2t-creative Semantic Rendering Architecture
status: draft
date: 2026-05-08
scope: h2t-creative landing/deck/dashboard composition layer
---

# h2t-creative Semantic Rendering Architecture

## 1. Why This Spec Exists

R1/R2 recovery proved that visual profile extraction can work, but landing
work exposed a missing layer in the protocol.

The current modular system can recover visual primitives: tokens, cards,
tables, stats, flow blocks, deck layouts, frame chrome. That is not enough for
landings. A landing can contain correct primitives in the wrong order, density,
or role and still look broken.

The missing layer is a CMS/theme-style separation:

```text
content schema -> semantic blocks -> presentation slots -> profile skin -> responsive rules -> renderer
```

The goal is to avoid a combinatorial explosion:

```text
style x block x desktop x mobile x format
```

Profiles should not each define an unrelated landing structure. They should map
shared semantic block roles to profile-owned visual primitives.

## 2. Terms

| Term | Meaning |
|---|---|
| Content schema | Style-independent block data: title, text, rows, media, actions. |
| Semantic block | A format role such as `hero`, `proof`, `features`, `process`, `comparison`, `gallery`, `cta`. |
| Presentation slot | Stable fields a semantic block exposes: `eyebrow`, `title`, `subtitle`, `items`, `rows`, `media`, `actions`. |
| Skin mapping | Profile/form-specific mapping from semantic block to renderer/component. |
| Primitive | CSS/HTML visual unit extracted from a golden source: `.ph`, `.stat`, `.bt`, `.flow`, HUD panel, terminal code block. |
| Renderer | Code path that turns a semantic block + skin mapping into existing component input. |
| Asset model | Typed media references and fallback policy for images, video, canvas, Three.js/WebGPU visuals. |

## 3. Required Protocol Change

For any landing work, the agent must not jump directly from style extraction to
component implementation.

Required order:

```text
T0 source inventory
T0.5 source arbitration
T0.6 format role classification
T0.7 style extraction contract
T0.8 landing composition contract
T1 implementation
```

### T0.6 — Format Role Classification

Every source must be classified before implementation:

| Source role | Meaning | Example |
|---|---|---|
| Fidelity target | Reproduce structure and style closely. | R2a terminal deck, R2b editorial deck. |
| Primitive source | Extract visual language and primitives, then compose a new format. | R2b editorial landing from Rejuve appendix pages. |
| Contract-only | Confirms brand/skill contract but is not a layout source. | Rejuve pitch deck for landing typography direction. |

Hard rule: a report/appendix/dashboard source is not automatically a landing
layout target.

### T0.8 — Landing Composition Contract

Before writing landing components or recipes, define:

- target reader;
- target action;
- block inventory;
- block order;
- density budget;
- table/comparison policy;
- asset/media policy;
- mobile policy;
- forbidden composition patterns.

This contract is separate from the style extraction document.

## 4. Universal Landing Block Roles

These roles are style-independent. They are the content layer that profiles map
to visual primitives.

| Block type | Purpose | Common slots |
|---|---|---|
| `nav` | orientation and anchors | brand, links, active item |
| `hero` | first-screen promise and context | eyebrow, title, subtitle, body, actions, media, proof_items |
| `proof` | compact credibility / KPI strip | title, items[] |
| `problem` | why the reader should care | title, body, items[] |
| `solution` | what changes | title, body, items[] |
| `features` | capabilities / differentiators | title, intro, items[] |
| `process` | how it works | title, steps[] |
| `comparison` | contrast with alternatives | title, intro, columns[], rows[], note |
| `gallery` | visual evidence / images | title, assets[], layout, captions |
| `video` | video embed or local video | title, src/embed_url, poster, caption |
| `case_study` | concrete example | title, body, result_metrics, media |
| `testimonials` | quotes | quotes[] |
| `pricing` | offer tiers | tiers[] |
| `faq` | objections | items[] |
| `evidence` | sources, audit trail, footnotes | links[], notes[] |
| `cta` | final action | label, title, body, primary_action, secondary_action |
| `footer` | service/legal bottom | links, legal |

Not every landing uses every role. A validation landing should be short enough
to read as a landing, not a primitive catalog.

## 5. Presentation Slot Contracts

### Hero

```yaml
type: hero
eyebrow: string?
title: string
subtitle: string?
body: string?
actions:
  - label: string
    href: string
    role: primary|secondary
media:
  asset: asset_id?
  role: hero_visual|ambient_system|product_shot
proof_items:
  - value: string
    label: string
```

### Comparison

```yaml
type: comparison
title: string
intro: string?
columns:
  - key: string
    label: string
rows:
  - label: string
    values:
      key: string
      value: string
    tone: default|accent|success|warning|danger?
note: string?
```

### Gallery / Video

```yaml
type: gallery
title: string?
assets:
  - asset: asset_id
    caption: string?
layout: grid|carousel|single
```

```yaml
type: video
title: string?
asset: asset_id
poster: asset_id
caption: string?
```

## 6. Asset Model

Media must be explicit. Fake visual placeholders are forbidden in visual gates.

```yaml
assets:
  - id: hero_video
    type: video
    src: assets/hero.mp4
    poster: assets/hero-poster.jpg
    alt: "Hero animation poster"
    role: hero
    required: false
    fallback: hero_poster

  - id: studio_gallery_01
    type: image
    src: assets/studio-01.jpg
    alt: "Studio view"
    role: gallery
```

Rules:

- `alt` is required for images.
- video requires a poster/fallback.
- missing required assets block visual QA.
- missing optional assets remove the media slot or use an approved fallback.
- neutral placeholders may be used only for structural smoke tests and must be
  excluded from visual gates.
- external embeds require an allowlist (`youtube`, `vimeo`, or explicit local
  mp4). Raw arbitrary script/embed injection is forbidden.

## 7. Complex Visuals: Canvas / Three.js / WebGPU

Semantic recipes do not request a concrete rendering engine. They request a
visual role and capability.

```yaml
type: hero
title: "Knowledge engine for agents"
visual:
  role: ambient_system
  content: graph_network
  mode: scripted
  required: false
  fallback: static
```

Profile skins decide how to render that role:

```yaml
visuals:
  ambient_system:
    renderer: graph-canvas
    script: profiles/h2t-graphs/fx/graph-canvas.js
    fallback_renderer: static-figure
```

Capability levels:

| Level | Meaning | Examples |
|---|---|---|
| `static` | image, SVG, diagram | editorial figure, product screenshot |
| `css` | CSS-only motion | scanlines, hover sweep, framed masks |
| `scripted` | JS canvas / Three.js / WebGPU | graph network, particle field, shader demo |

Rules:

- semantic recipe never imports JS directly;
- profile owns scripts under its `fx/` or renderer directory;
- every scripted visual has a static/no-motion fallback;
- mobile may use fallback if the scripted visual is too heavy;
- visual QA must verify scripted desktop and mobile fallback behavior.

## 8. Skin Mapping

Each profile/form provides a mapping from semantic block roles to profile
components/renderers.

Example for `h2t-editorial` landing:

```yaml
blocks:
  hero:
    component: page-header
    variant: editorial-compact
    field_map:
      title: title
      subtitle: meta
      eyebrow: label

  proof:
    component: stats
    field_map:
      items: stats

  features:
    component: card-grid
    field_map:
      items: cards

  process:
    component: flow
    field_map:
      steps: steps

  comparison:
    component: comparison-table
    mobile_representation: cards

  cta:
    component: editorial-cta
```

Example for `h2t-graphs` landing:

```yaml
blocks:
  hero:
    component: hud-hero
    visual_role: ambient_system

  proof:
    component: stats-bar

  features:
    component: hud-panel-grid

  process:
    component: diagram-flow

  comparison:
    component: compare-grid
    mobile_representation: stacked-panels

  cta:
    component: hud-cta
```

## 9. Responsive Strategy

Responsive behavior belongs to the skin, not the content schema.

Rules:

- desktop and mobile share the same semantic blocks;
- profile CSS owns breakpoint behavior;
- renderer can output dual representation when needed, e.g. desktop table +
  mobile cards;
- JS viewport branching is forbidden unless a scripted visual capability
  requires a documented fallback decision;
- mobile visual QA is mandatory for every landing.

Comparison/table policy:

- desktop may use compact tables;
- mobile must not rely on horizontal scroll as the primary UX unless the human
  explicitly accepts report-style density;
- preferred mobile representation is row cards with header labels;
- no content loss between desktop table and mobile cards.

## 10. Renderer v0 Scope

This is not a full CMS. v0 should be deliberately small.

Implement only:

- semantic recipe parser for `blocks`;
- skin mapping loader for `profiles/<profile>/skins/<format>.yaml`;
- field mapping from semantic slots to existing component inputs;
- fallback to existing component-based recipes;
- first block types: `hero`, `proof`, `features`, `process`, `comparison`,
  `cta`, `evidence`;
- asset validation for image/video/static/scripted roles.

Out of scope for v0:

- arbitrary custom JS injection;
- user-authored component templates in recipes;
- full page builder UI;
- cross-profile automatic visual parity;
- pricing/FAQ/gallery/testimonials if not needed for the pilot.

## 11. Migration Strategy

Legacy component recipes remain supported.

New/recovered landing recipes should use semantic blocks. Migration proceeds by
profile/form as recovery work touches it.

| Profile | Landing semantic migration |
|---|---|
| `h2t-editorial` | Pilot for #88. |
| `h2t-graphs` | Migrate when deck/landing extension work resumes. |
| `h2t-mono` | Migrate only when a canonical landing/deck source exists. |
| `h2t-terminal` | Deferred; no landing golden. |
| `h2t-pfad` | Dashboard first; landing deferred. |
| `h2t-default` | Generic fallback skin. |

## 12. Applying This to #88

Current #88 landing work recovered useful primitives from the Rejuve appendix
goldens, but the validation recipe drifted into a primitive showcase. That is
the exact failure this architecture prevents.

For #88, the next accepted path is:

1. keep extracted System B-Landing tokens and primitives;
2. treat `competitive-report` and `elpodium-decomposition` as primitive
   sources, not layout targets;
3. define semantic landing blocks:
   - `hero`;
   - `proof`;
   - `features`;
   - `process`;
   - `comparison`;
   - `evidence`;
   - `cta`;
4. map them to editorial primitives:
   - `hero -> page-header / editorial intro`;
   - `proof -> stats`;
   - `features -> card-grid`;
   - `process -> flow`;
   - `comparison -> compact comparison-table + mobile cards`;
   - `evidence -> section`;
   - `cta -> editorial-cta`;
5. build and capture only after the semantic composition contract is approved.

## 13. Acceptance Criteria

This spec is accepted when future h2t-creative landing work follows these
rules:

- the agent classifies sources as fidelity target vs primitive source before
  implementation;
- landing composition contract exists before component implementation;
- recipe content is semantic, not profile-component-specific, for new landing
  work;
- profile skins map semantic blocks to style primitives;
- visual assets have explicit asset/fallback policy;
- tables/comparison blocks define desktop and mobile representation;
- visual QA checks the rendered page, not component presence.

