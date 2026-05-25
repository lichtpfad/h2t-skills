---
title: "h2t-creative Semantic Rendering Architecture"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-08"
milestone: ""
---
# h2t-creative Semantic Rendering Architecture

> **Status 2026-05-19:** superseded. This spec describes the semantic-CMS direction that produced the failed #119 editorial landing candidate. The human review found that the output had only fonts/colors, lacked a working design system, lacked meaningful semantic blocks, and was not a landing. Do not use this spec as an implementation plan. Treat it as negative evidence: concrete, human-approved visual output must precede reusable abstraction.

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

## 11. Core Block Library and Extension Protocol

The semantic layer is not a closed component list. It is an extensible block
library with strict guardrails. The system should cover common landing needs
with a core set, then grow safely when a real task needs a new block.

### 11.1 Core Block Set

These blocks are the minimum reusable surface for most landing work. A landing
mode decides priority; it does not create a separate incompatible component
family.

| Core block | Typical roles | Notes |
|---|---|---|
| `hero` | first screen, value proposition | May include media/visual role. |
| `proof` / `stats` | credibility, numbers, trust facts | Compact by default. |
| `features` | capability / differentiator grid | Cards or editorial feature rows. |
| `process` | how it works | Flow, timeline, stepper. |
| `comparison` | contrast alternatives | Compact table/grid; mobile cards by default. |
| `table` | data, packages, matrices, reports | Core, not forbidden; density depends on mode. |
| `media` / `gallery` | image/video/project evidence | Asset policy required. |
| `testimonial` | social proof | Optional unless mode requires it. |
| `pricing` / `offer` | commercial offer | Product/service modes. |
| `faq` | objections | Product/service modes. |
| `cta` | primary action | Required for true landing pages. |
| `footer` / `evidence` | legal, audit trail, sources | Profile/mode-specific. |

### 11.2 Landing Modes and Block Priority

One schema supports multiple landing intents. Modes assign priority to blocks.

Priority levels:

| Priority | Meaning |
|---|---|
| `P0 required` | Page fails the mode without it. |
| `P1 recommended` | Expected in most pages of this mode. |
| `P2 optional` | Include when content exists. |
| `P3 advanced` | Requires assets, heavier interaction, or explicit human approval. |
| `P4 report-only` | Valid in reports/appendices, not default landing flow. |

Initial modes:

| Mode | Use case |
|---|---|
| `product` | Commercial product / SaaS / tool. |
| `service` | Consulting, agency, course, school. |
| `editorial` | Explainer, manifesto, profile page, internal proof page. |
| `report` | Appendix, audit, research report. |
| `portfolio` | Art/project/case presentation. |
| `deck-companion` | Web page around a presentation/deck. |

Mode x block priority starts as a design contract, not runtime code:

| Block | product | service | editorial | report | portfolio | deck-companion |
|---|---|---|---|---|---|---|
| hero | P0 | P0 | P0 | P1 | P0 | P0 |
| problem | P1 | P1 | P2 | P2 | P3 | P2 |
| solution/features | P0 | P1 | P1 | P2 | P2 | P1 |
| proof/stats | P1 | P1 | P1 | P1 | P2 | P1 |
| process | P2 | P1 | P1 | P2 | P1 | P2 |
| comparison | P1 | P2 | P2 | P1 | P4 | P2 |
| table | P2 | P2 | P2 | P0 | P4 | P3 |
| gallery/media | P2 | P2 | P3 | P3 | P0 | P2 |
| video | P2 | P2 | P3 | P4 | P1 | P2 |
| pricing/offer | P1 | P2 | P4 | P4 | P4 | P4 |
| testimonials | P1 | P1 | P3 | P4 | P2 | P3 |
| faq | P1 | P1 | P3 | P4 | P4 | P3 |
| evidence/footer | P2 | P2 | P1 | P0 | P2 | P1 |
| cta | P0 | P0 | P1 | P4 | P1 | P1 |

### 11.3 Block Extension Protocol

When a task needs a block that does not exist, the agent must not improvise a
one-off component. It must extend the block library.

Required extension steps:

1. **Classify semantic role.** Decide whether the need is a new block or a
   variant of an existing block.
2. **Check existing blocks.** Reuse an existing block if it can express the
   intent without distorting semantics.
3. **Define slot contract.** Required/optional fields, array shapes, asset
   references, limits.
4. **Define style mapping.** How the current profile renders the block.
5. **Define desktop behavior.** Layout, density, max rows/items/text.
6. **Define mobile behavior.** Stack/cards/scroll/fallback; no hidden content.
7. **Define asset policy.** Required assets, fallback, no fake visual evidence.
8. **Write tests first.** Structural tests, output guards, forbidden patterns,
   mobile contract.
9. **Run visual QA.** Capture desktop/mobile and classify PASS/ISSUE/BLOCKER.
10. **Update registry/spec.** Add the block or variant to the library contract.

Example new block contract:

```yaml
block: timeline
semantic_role: process
slots:
  title: string
  intro: string?
  events:
    - date: string?
      title: string
      body: string
desktop:
  layout: vertical-spine
mobile:
  layout: stacked-cards
limits:
  max_events: 6
  max_words_per_event: 24
assets: none
forbidden:
  - horizontal scroll required for reading
  - hidden event bodies on mobile
```

### 11.4 Guardrails for New Blocks

Every new block or profile-specific renderer must specify:

- semantic role;
- slot contract;
- style mapping;
- desktop behavior;
- mobile behavior;
- asset/media policy;
- density limits;
- forbidden patterns;
- structural tests;
- visual QA evidence;
- registry/spec update.

Hard rules:

- no fake placeholders in visual gates;
- no mobile pass without opening screenshots;
- no table/comparison block without a declared mobile representation;
- no style-specific block that cannot be mapped back to a semantic role;
- no hidden essential content as a mobile strategy;
- no arbitrary JS injection from recipe content.
## 12. Migration Strategy

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

## 13. Applying This to #88

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

## 14. Acceptance Criteria

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

---

## 15. External References / Prior Art

> **Discoverable entry point:**
> `docs/superpowers/references/h2t-creative-semantic-rendering-prior-art.md`
> carries the same content in standalone form. Future agents should
> read THAT file first; this section §15 is the embedded copy that
> stays with the spec for self-contained reading. Keep the two
> in sync — see the maintenance note at the end of the references file.

This architecture sits in a well-explored design space. Before
committing to specific shapes (block schema, slot contracts, skin
mapping, render separation), we cross-checked our v0 vocabulary
against four mature reference systems via Context7 (verified
2026-05-08).

The conclusion is **adopt selected battle-tested patterns, do not
copy any system wholesale**. h2t-creative is a static
recipe → HTML assembler with no runtime DB, no localisation, no
asset CDN, no GraphQL — we lift concepts, not infrastructure.

### 15.1 Terminology mapping

User-facing terminology was already aligned with prior art when this
spec was drafted; Context7 verification confirmed the mapping below.

| External pattern | Concrete reference | h2t-creative term |
|---|---|---|
| Content type / Story | Contentful `ContentType` with list of `Fields`; Storyblok content-type block (`is_root: true`) | landing recipe |
| Block / Component | Storyblok `component` (with `schema` map); Gutenberg `block` registered via `block.json` | semantic block |
| Component / block schema | Storyblok `schema: {field: {type, pos}}`; Gutenberg `attributes: {field: {type}}`; Contentful Field with `Type` | slot contract |
| Fields | Contentful Fields (Text, Symbol, Asset, Link, Array, RichText, …) | slots |
| Theme / frontend renderer | Gutenberg `save` / `render_callback`; Contentful "structure separated from frontend" | profile skin |
| Visual editor preview | Storyblok preview field + visual editor; Gutenberg `edit` component | Agent Visual QA + screenshots |
| Component library | Storyblok components API; Gutenberg block library; Block Protocol blocks | core block registry + extension protocol (§11) |
| Reference between content types | Contentful `Link` field with `linkContentType: [...]` validation | block referencing another block (deferred to v1) |

### 15.2 What we adopt

1. **Edit / render separation principle (Gutenberg).**
   Gutenberg `registerBlockType({edit, save})` splits the editor
   experience from the persisted render output. v0 mirrors this with
   `recipe` (persisted, structural) → `skin → renderer` (presentation
   choice). The recipe author never authors HTML; the renderer never
   re-interprets intent. Source: developer.wordpress.org/block-editor
   /getting-started/fundamentals/registration-of-a-block.

2. **Schema-as-data (Storyblok + Gutenberg).**
   Both systems encode block field shape as a structured map, not as
   ad-hoc constructor signatures. v0 follows this — slot contracts
   live in `profiles/<p>/skins/<format>.yaml` as data, not Python.
   Storyblok shape (verified):
   ```json
   {"schema": {"bio": {"type": "richtext", "pos": 0}, "name": {"type": "text", "pos": 1}}}
   ```
   v0 skin file (this spec §8) follows the same key-value pattern,
   without the `pos` field — recipe-block ordering carries position.

3. **Field validation (Contentful).**
   Contentful per-field validators (`MimeTypeValidator`,
   `LinkContentTypeValidator`, regex, etc.) prove that validation is
   data, not code. v0-scope validation is shallow (required / optional,
   asset existence) but the architecture leaves room for richer
   validators in v1 by extending the slot-contract YAML schema with a
   `validations:` key. Source: contentful.com/developers/docs/net
   /tutorials/management-api.

4. **Reference fields for cross-block links (Contentful).**
   Contentful's `Link` field with `linkContentType: ["page"]`
   validation is the precedent for "this CTA block references a deck
   PR entry" — when we later need cross-recipe references. v0 does
   NOT implement this; the architecture preserves the option by
   keeping block content as a typed dict (block→block links remain
   addable as a `link` slot type).

5. **Distinguishing root from nestable (Storyblok).**
   Storyblok's `is_root` (top-level content type) vs `is_nestable`
   (block usable inside others) maps to v0's distinction between
   recipe-level `blocks:` and block content fields that may carry
   nested HTML. v0-scope keeps this implicit; the boundary is "only
   top-level recipe entries are blocks; nested HTML inside a slot is
   rendered HTML, not a block".

### 15.3 What we explicitly do NOT adopt

| Pattern | Why not |
|---|---|
| Runtime DB (Contentful Spaces, Storyblok content store) | h2t-creative recipes live in git; assembler is static. |
| Localisation (Contentful `Localized: bool`, Storyblok translation layer) | Out of scope for v0 (architecture §10). Add via slot-level `localizable: bool` if it becomes a requirement. |
| GraphQL / REST content delivery (Contentful CDA, Storyblok CDN) | We compile to flat HTML / CSS / JS files. No runtime API. |
| Asset CDN with image transformations (Storyblok image service, Contentful Images API) | Asset model (architecture §6) handles assets as static file references; transformations are out of scope. |
| Editor UI (Storyblok Visual Editor, Gutenberg admin) | h2t-creative authoring is YAML + the editorial-author skill; no GUI. Agent Visual QA gate IS our preview equivalent. |
| Versioning of content (Contentful entries with version history, Storyblok stories) | Git provides versioning; recipes are git-tracked. |
| Block Protocol's host-application contract | We don't have a host application; renderer IS the host. Pattern noted, not implemented. |

### 15.4 Concrete shape verifications from Context7

These confirmed v0's design choices were not made in isolation:

- Storyblok component is "self-contained reusable element with one or more field types, can be nested" — direct match for our semantic-block definition.
- Contentful Field has `Type` ∈ {Text, Symbol, Number, Asset, Link, Array, RichText, …} — superset of v0 slot types (text / html / asset / list); v0 deliberately starts narrow.
- Gutenberg `attributes: {fieldName: {type: "string|boolean|number"}}` — same shape as v0 slot definitions.
- Contentful Compose landing content type has reference fields like `section_bottom` linking to `component_text` — precedent for our future "landing has named slots that reference shared content blocks" evolution. NOT v0 scope.

### 15.5 Sources

User-supplied (curated):

- Storyblok content modeling — https://www.storyblok.com/docs/concepts/content-modeling
- Storyblok blocks — https://www.storyblok.com/docs/concepts/blocks
- Contentful content models — https://www.contentful.com/help/content-model-and-content-type/
- Contentful fields — https://www.contentful.com/help/fields/
- Portable Text — https://www.portabletext.org/
- Block Protocol spec — https://blockprotocol.org/spec

Context7-verified (2026-05-08):

- Storyblok components API — `/websites/storyblok` (1287 snippets, High reputation, score 69)
- Contentful developer docs — `/websites/contentful_developers` (7370 snippets, score 88.3)
- WordPress Block Editor (Gutenberg, substitute for direct Block Protocol library which is not in Context7) — `/websites/developer_wordpress_block-editor` (5246 snippets, score 71.35)
- Portable Text React — `/portabletext/react-portabletext` (resolved but not queried — 18 snippets, niche; user-supplied summary sufficient)

### 15.6 Verdict

The terminology and pattern set chosen in §3, §4, §5, §6, §8, §11 of
this spec are aligned with prior art. v0 does not need to wait for
further research before T1 starts. This appendix records the prior
art for the next maintainer who asks "why these names, why this
shape" — the answer is "Storyblok / Contentful / Gutenberg use
versions of these, and we adopted what fits a static-assembler
context".


