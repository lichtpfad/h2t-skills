# h2t-creative Core System

## Layers

### 1. Base Layer

The base layer defines reset, grid, typography, and shared mechanics. It should encode Swiss/grid principles that are common across profiles.

The base layer is not a visual skin. It is the structural substrate.

### 2. Profile / Skin Layer

A profile defines visual language:

- Typography
- Color tokens and palettes
- Surfaces and borders
- Component style
- Motion and chrome
- Profile-specific constraints

Profile files live under `plugins/h2t-creative/profiles/<profile>/`.

Profile `DESIGN.md` files follow the [Stitch DESIGN.md open standard](https://github.com/google-labs-code/design.md) (Apache 2.0). The Stitch standard defines machine-readable design tokens via YAML frontmatter (colors, typography, spacing, rounded, components) plus markdown rationale. The existing multi-file CSS implementation (`tokens.css` + `palettes/*.css`) sits below the standard as the runtime layer. See `docs/superpowers/references/stitch-design-md-spec-reference.md`.

### 3. Component / Primitive Layer

Components are concrete renderable primitives:

- HTML template
- CSS
- `manifest.yaml`
- Required fields
- Optional variants
- Responsive behavior

Components are not semantic intent by themselves. A `stats` component can serve `proof`; a `section` component can serve `evidence`.

### 4. Semantic Layer

Semantic recipes use `blocks:` and declare intent:

- `hero`
- `proof`
- `features`
- `comparison`
- `process`
- `evidence`
- `cta`
- plus future roles

The semantic layer maps roles to components through a skin file:

`profiles/<profile>/skins/<format>.yaml`

### 5. Renderer / Assembler Layer

The runtime currently supports:

- Legacy `sections:` recipes
- Semantic `blocks:` recipes
- Semantic adapter that converts blocks to derived legacy sections
- Existing assembler output path

The current semantic renderer v0 is a technical proof that role -> skin -> component -> legacy renderer can work without breaking legacy recipes.

## Evidence Classification

### Successful Visual Evidence

- R1 h2t-graphs and h2t-mono landing recovery
- R2a h2t-terminal deck recovery
- R2b h2t-editorial deck recovery

### Technical Proof

- #119 semantic renderer v0 and editorial semantic pilot code path

### Negative Visual Evidence

- #88 editorial landing attempt
- #119 editorial semantic landing candidate screenshots before an approved wireframe

Negative visual evidence must be preserved as a warning, not copied as a target.

## Required Distinctions

- Renderer pass does not imply design pass.
- Component pass does not imply page composition pass.
- Source fidelity does not imply landing suitability.
- A profile skin does not replace a wireframe.
- Mobile adaptation is a separate representation, not a resize.
