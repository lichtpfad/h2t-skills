# h2t-creative Landing Wireframe Contract

## Purpose

This contract specifies the format and contents of the wireframe artefact a landing-page author must produce before any recipe, skin, or component implementation begins. It is the landing-specialised instantiation of the generic gate defined in `docs/protocols/h2t-creative/WIREFRAME_GATE.md`.

The contract closes a concrete gap surfaced by issue #88 / branch `codex/r2b-editorial-landing` (archived under `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/`): without a format-specific wireframe shape, "produce a wireframe" devolves into "extract primitives", and the result is a renderer pass / design fail. The fields below are the minimum a human reviewer needs to make an informed approval decision.

The contract does not prescribe visual style — that is the profile `DESIGN.md` and skin's job (see `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Profile / Skin Layer). The contract prescribes structure, intent, density, and responsive behaviour. A single approved wireframe drives recipe authoring, visual QA, and human review.

## When This Contract Applies

Mandatory for any output that produces a landing page, including:

- Standalone product, service, or editorial landings.
- Microsites that are functionally one or two landing pages.
- Hub pages and content indexes that share the landing structure (hero + sections + CTA).
- "Landing-companion" pages adjacent to a deck or report (e.g. download / signup adjacent to a publication).

Not required for:

- Decks and presentations (use the deck wireframe contract — to be added by analogy).
- Reports and appendices (use the report wireframe contract — likewise).
- Carousels, interactive explainers (likewise).

If the format is unclear, default to the strictest applicable contract.

## Inputs

Before drafting a wireframe, the author collects:

- **Intent statement** — one or two sentences naming the landing's primary purpose: explain, sell, teach, document, compare, pitch, or publish. This drives mode selection and CTA shape.
- **Audience** — who the page is for. Constrains density, technical depth, evidence weight.
- **Mode** — one of the canonical landing modes from `docs/architecture/h2t-creative/CORE_SYSTEM.md` and the semantic parser `KNOWN_MODES` set: `product`, `service`, `editorial`, `report`, `portfolio`, `deck-companion`. Mode pre-selects sensible block-sequence defaults.
- **Profile / style target** — which `profiles/<name>/` design system applies. The profile constrains palette, typography, density tolerance, and primitive availability. The author reads the profile's `DESIGN.md` Stitch frontmatter and Restrictions before choosing block density.
- **Source dossier** — the visual / textual / data sources the page draws from, each classified per `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Evidence Classification: target, primitive source, or negative.
- **Required CTA(s)** — what the page must persuade the reader to do. Determines CTA placement and copy intent.
- **Known constraints** — fixed deadlines, mandatory legal copy, brand restrictions, asset availability gaps.

## Required Wireframe Artefact

The wireframe artefact is one document containing all of the following fields. Missing fields are a review failure. Empty fields are explicit `(none)` rather than absent.

### Mode Declaration

State the mode from the `KNOWN_MODES` vocabulary. Pick one — the modes are mutually exclusive at this layer:

| Mode | Primary intent | Typical sequence |
|---|---|---|
| `product` | Sell or explain a product | hero, proof, features, process, comparison, evidence, cta |
| `service` | Persuade to engage a service | hero, proof, problem, solution, process, evidence, cta |
| `editorial` | Publish a long-form argument or release | hero, proof, features (or evidence-cards), comparison, evidence, cta |
| `report` | Surface findings of an analysis | hero (page-header), proof, evidence, comparison, cta-as-link |
| `portfolio` | Showcase work or precedent | hero, gallery, case_study, evidence, cta |
| `deck-companion` | Resource adjacent to a deck/talk | hero, proof, evidence, cta (typically download / signup) |

The "Typical sequence" is a starting hint, not a constraint. Real wireframes deviate when intent demands.

### Block Sequence

A numbered list of semantic block roles in the order they appear from top to bottom on desktop. Use the universal vocabulary from `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Semantic Layer (also encoded in the parser's `KNOWN_BLOCK_TYPES` set):

`nav`, `hero`, `proof`, `problem`, `solution`, `features`, `process`, `comparison`, `gallery`, `video`, `case_study`, `testimonials`, `pricing`, `faq`, `evidence`, `cta`, `footer`

Constraints (see also § Density Budget):

- 5–8 entries total per `COMPOSITION_RULES` density rules. Below 5, the page is rarely a landing; above 8, density discipline collapses.
- The first block after `nav` (or first overall if no nav) MUST be `hero`. The first screen has to communicate intent.
- At least one of `cta` or a CTA-equivalent block (e.g. `cta`-styled `evidence`) must appear. A landing without a CTA is a content page.
- `footer` is optional — many landings ship without one if the surrounding site provides chrome.

Format example:

```
1. `hero`           — first screen
2. `proof`
3. `features`
4. `process`
5. `comparison`
6. `evidence`
7. `cta`
```

### Per-Block Intent

For each block in the sequence, one or two sentences naming what that specific block must communicate to the specific audience. Not copy. Intent.

Bad: "Stats with three numbers about the product."
Good: "Establish credibility before features land — show that the product has been used at scale (count, retention, partner). Audience is procurement-focused, so prefer institutional metrics over user-testimonials feel."

Per-block intent is the test the recipe author writes against and the human reviewer measures the rendered page against in `VISUAL_QA.md` § Gate A.

### Per-Block Density Classification

Each block is one of: **dense**, **medium**, or **open**.

- **dense** — table-heavy, multi-column data, ≥ 4 cards per row, paragraphs > 3 lines. Comparison tables, deep evidence sections.
- **medium** — moderately structured: 3-card grids, stats blocks with labels, process steps, bordered CTAs.
- **open** — generous whitespace, single-column copy, single hero image, single headline + meta. Hero, single-card evidence, simple CTAs.

Density classification feeds the density budget below and the rhythm rule that dense sections must be followed by breathing room (`COMPOSITION_RULES` § Density Rules).

### Desktop Layout Sketch

A low-fidelity representation of the desktop view. Acceptable formats (see § Format Options):

- ASCII column diagram
- Markdown table with one row per block listing `column count × role`
- Hand sketch image embedded by relative link

Required content of the sketch, regardless of format:

- **Content max-width** — typically 1100 px for editorial, 1200 px for product. Profile may constrain.
- **Column model per block** — single, two-up, three-up, four-up. Cards-per-row.
- **Block ordering** — must agree with § Block Sequence above.
- **Notes for non-rectangular blocks** — galleries, hero-with-media, full-bleed quotes — call out the divergence from the dominant grid.

The sketch does not commit to specific copy or specific colors. It commits to layout structure.

### Mobile Representation Per Block

For each block, name its mobile representation explicitly. One of:

- **stack** — single column, contents flow top-to-bottom in source order.
- **collapse-to-1col** — a multi-column desktop block redraws as one column on mobile (cards, stats, features grids).
- **collapse-to-cards** — a desktop table redraws as stacked cards on mobile (the comparison-table dual-rep contract; rhythm spec § A.4).
- **hide** — block does not render below a stated breakpoint. Allowed only for non-essential nav, decorative dividers, or surplus chrome. Essential content must never `hide`.
- **media-fallback** — video, gallery, or interactive block uses a poster, static image, or text fallback on mobile.

Mobile is not passive resizing (`COMPOSITION_RULES` § Responsive Representation). Every multi-column desktop block needs an explicit mobile representation declared here.

### Source Classification Per Block

For each block, classify its content source per `CORE_SYSTEM.md` § Evidence Classification:

- **target** — the block IS the canonical thing. Original copy / data / hero image authored for this landing.
- **primitive source** — the block lifts visual or structural primitives from a prior approved evidence (e.g. an editorial appendix design system). Note the precedent.
- **negative** — explicitly NOT a target; included only as a "not this" negative example. Rare; usually doesn't appear in a landing wireframe at all.

A wireframe whose every block is "primitive source" is a **primitive showcase**, not a landing. That's the failure mode #88 fell into. The reviewer rejects such wireframes (see § Approval Criteria).

### Density Budget

A summary count derived from § Per-Block Density Classification:

- Total blocks: `<N>` (must be 5–8)
- Dense blocks: `<D>` (must be 0–2 per `COMPOSITION_RULES` § Density Rules)
- Dense-then-open ordering check: every dense block is followed by an open or medium block. State pass/fail.

The budget is a hard gate. A wireframe with 3 dense blocks fails review.

### Asset Inventory

Two lists:

- **Required assets** — every image, video, or interactive primitive the wireframe relies on. Each entry: id, role (hero_media / gallery / product_demo / ambient_system / poster / fallback), source (target / primitive / negative), URL or path.
- **Missing assets** — anything required but not yet available. Each entry: which block depends on it, what placeholder is acceptable, deadline for resolving.

A wireframe with `Required: hero_media; Missing: hero_media` ships only if the placeholder is explicitly approved by the human reviewer.

### Negative Examples

When a relevant failure mode exists in the project's negative-evidence record, name it here as "not this":

- "Not the appendix-clone direction from the #88 r2b attempt — see `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/failed-candidates/system-b-modular/`."
- "Not the primitive-showcase direction from the same attempt — see `failed-candidates/modular/`."

The point is to close off a known wrong path so the human reviewer doesn't have to re-derive that it's wrong. Negative examples are optional but valuable when they exist.

## Format Options

The wireframe artefact may be expressed in any of these forms, alone or combined:

- **Markdown document** with section headings matching the field list above. Preferred for git review.
- **ASCII column diagrams** for desktop layout. Useful for showing column splits.
- **Hand or low-fi tool sketch** (Excalidraw, Figma frame, paper photo) embedded by relative link from the markdown document.
- **Annotated screenshot** of an existing approved page that this landing structurally inherits from, with deltas called out.

The artefact MUST live in the repo at a stable path so the recipe author and reviewer can reference the same revision. Canonical path: `docs/wireframes/<YYYY-MM-DD>-<profile>-<page-slug>.md` and any embedded images alongside. The `docs/wireframes/` root is registered in `docs/architecture/h2t-creative/ROOT_GUIDE.md` § Canonical Architecture Docs (see Task 10 of the plan that produced this file).

The artefact MUST NOT be a high-fidelity mockup, a full design comp, a production-ready CSS draft, or a screenshot of a competitor's site without deltas.

## Forbidden In A Wireframe

Items that DO NOT belong at the wireframe stage and that signal scope creep into recipe / skin / implementation:

- **Production / final copy.** A representative draft headline, CTA label, table column labels, and one-line representative body per block IS allowed and recommended — abstract structure approves cleanly but breaks under real text, so a sample text load-bearing test belongs in the wireframe. Mark every such draft explicitly as `(non-final)` so a reader does not mistake it for locked copy. Final word-for-word copy is recipe stage.
- **Specific hex colors / specific font sizes.** Profile `DESIGN.md` and tokens.css own that.
- **Component implementation details** (HTML class names, manifest field names). Skin owns the role-to-component mapping.
- **Pixel-perfect layouts.** This is intentionally low-fidelity. Aim for "structure and intent decided", not "design comp finished".
- **One-off CSS overrides.** Implementation, not wireframe.
- **JavaScript / interactive state machines.** Wireframe names the interactive primitive role and its fallback; the rest is implementation.

A wireframe that violates these is rejected at review with a "scope creep — return to wireframe stage" verdict, not "approved with concerns".

## Approval Criteria

A wireframe is approved when ALL of the following hold. Each item is binary pass/fail.

1. **Mode declared and in vocabulary** (one of `KNOWN_MODES`).
2. **Block sequence is valid**: 5–8 entries; every entry in `KNOWN_BLOCK_TYPES`; first block after `nav` (or first overall) is `hero`; at least one CTA-bearing block.
3. **Per-block intent stated** for every block — not just "show stats" but what the stats argue and to whom.
4. **Per-block density classified** for every block.
5. **Desktop layout sketch present** in any acceptable format, with content max-width and column model declared.
6. **Mobile representation declared** for every multi-column desktop block.
7. **Source classification stated** for every block.
8. **Density budget within rules**: total 5–8; dense ≤ 2; dense never adjacent to dense.
9. **Asset inventory present** with explicit Missing list (or empty).
10. **Negative examples acknowledged** when project negative-evidence record contains a relevant failure mode.
11. **Forbidden-content scan passes** — no production copy, no hex colors, no component implementation details. Representative `(non-final)` draft copy is allowed; production-locked copy is not.
12. **Profile / style-target compatibility verified** against the profile's `DESIGN.md` Restrictions section.

The reviewer signs off only when every item passes. Any failure returns the wireframe to the author with a numbered list of failed items. The reviewer never approves "with conditions to fix later" — fix first, approve after.

## Outputs After Approval

<!-- §10 fills this in -->

## Worked Examples

<!-- §11 fills this in -->

### Positive Example — Editorial Landing

### Negative Example — Primitive Showcase (Why It Fails)

## Cross-References
