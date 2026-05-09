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

<!-- §6 fills this in -->

### Mode Declaration

### Block Sequence

### Per-Block Intent

### Per-Block Density Classification

### Desktop Layout Sketch

### Mobile Representation Per Block

### Source Classification Per Block

### Density Budget

### Asset Inventory

### Negative Examples

## Format Options

<!-- §7 fills this in -->

## Forbidden In A Wireframe

<!-- §8 fills this in -->

## Approval Criteria

<!-- §9 fills this in -->

## Outputs After Approval

<!-- §10 fills this in -->

## Worked Examples

<!-- §11 fills this in -->

### Positive Example — Editorial Landing

### Negative Example — Primitive Showcase (Why It Fails)

## Cross-References
