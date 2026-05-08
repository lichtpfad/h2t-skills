# h2t-creative Extension Protocol

## Purpose

h2t-creative must grow as a reusable visual publishing system. New blocks, layouts, formats, and interactive primitives can be created during real content work, but they must become formal library assets, not one-off HTML.

## Reuse Before Create

Before adding anything new, the agent must search:

- Existing semantic roles
- Existing components in the target profile
- Components in other profiles
- Existing deck layouts
- Existing landing primitives
- Existing design-system docs
- Existing negative evidence

If an existing primitive can serve the need with a variant, prefer a variant.

## New Block / Component Flow

1. State the missing capability.
2. Explain why existing primitives do not fit.
3. Define semantic purpose.
4. Define schema/fields.
5. Define desktop behavior.
6. Define mobile behavior.
7. Define grid/rhythm constraints.
8. Add manifest and tests.
9. Add visual QA checklist.
10. Add library index entry.
11. Use it in the recipe only after the contract exists.

Human approval is required when the new block changes user flow, introduces a new semantic role, or adds non-trivial interaction.

## New Layout Flow

Layouts are format-specific arrangements, such as deck slide layouts.

Required fields:

- Format
- Intended role
- Allowed content density
- Desktop/canvas dimensions
- Mobile policy if relevant
- Required/optional fields
- Positive and negative examples

## New Format Flow

Formats include:

- Landing
- Deck
- Report/appendix
- Microsite
- Instagram carousel
- LinkedIn document carousel
- Story format
- One-page PDF
- Interactive explainer
- Video/script storyboard

New format specs must define:

- Purpose
- Unit model: section, slide, card, frame, scene
- Canvas/aspect ratio
- Allowed roles
- Grid/rhythm contract
- Export target
- Media constraints
- QA gates

## Interactive Primitive Flow

Interactive primitives include WebGL, WebGPU, Three.js, canvas, data visualization, and animation.

Required contract:

- Semantic role
- Required data/assets
- Initialization API
- Destroy/cleanup API
- Static fallback
- Mobile fallback
- Performance budget
- Screenshot timing for QA
- Security restrictions

No arbitrary inline script is allowed as a shortcut around the component system.

## Governance Terms

- Role: semantic purpose, such as `hero`, `proof`, `comparison`, `cta`.
- Component: renderable implementation in a profile.
- Layout: format-specific structure, especially for decks and carousels.
- Variant: constrained visual/behavioral variant of an existing component.
- Format: output type with canvas/unit/export rules.

Agents may add low-risk variants with tests. Humans must approve new roles, new formats, interactive primitives, and blocks that alter page flow.

## New Profile Flow

When adding a new profile, use the `/style-create` wizard which emits a [Stitch DESIGN.md](https://github.com/google-labs-code/design.md)-conformant `DESIGN.md` (Apache 2.0 open standard, machine-readable design tokens via YAML frontmatter). Validate the result with `/style-validate`. Do not invent a new design-system file format. See `docs/superpowers/references/stitch-design-md-spec-reference.md` for the spec summary and how h2t-creative consumes it.
