# h2t-mono

## Brand Intent
Ultra-minimal. Pure monospace, near-black bg, single red accent, zero decoration. Differentiation through spacing only — no brackets, no labels, no separators. CTA uses one filled + one ghost button. Extracted from SpecDesigner aesthetic (specdesigner.netlify.app).

## Color Tokens

### default (red)
- `--color-bg`: `#0d0d0d`
- `--color-text`: `#e0e0e0`
- `--color-text-dim`: `#666666`
- `--color-accent`: `#e8352b`
- `--color-border`: `#1a1a1a`

### white (inverted)
- `--color-bg`: `#f5f5f5`, `--color-text`: `#0d0d0d`, `--color-text-dim`: `#888888`
- `--color-accent`: `#e8352b`, `--color-border`: `#e0e0e0`

### blue
- `--color-bg`: `#0d0d0d`, `--color-text`: `#e0e0e0`, `--color-text-dim`: `#666666`
- `--color-accent`: `#2563eb`, `--color-border`: `#1a1a1a`

## Available Palettes
- `default` — red accent
- `white` — inverted light
- `blue` — blue accent

## Typography
- `--font`: JetBrains Mono, monospace

## Restrictions
- Zero decorative elements
- No border-radius
- All labels uppercase, body mixed-case

## R1 Source Of Truth

- Primary: `profiles/h2t-mono/sources/references.yaml`
- Live reference: `specdesigner.netlify.app`
- Reference screenshot: `sources/screenshots/reference-desktop.png`

## R1 Required Components

| Component | Visual Pattern |
|-----------|---------------|
| `two-column` | 1px background separator, label / title / code rows |
| `comparison-table` | Sparse borders, `.is-good` / `.is-bad` state classes |

## Forbidden Patterns

These patterns must NOT appear in h2t-mono components or validation recipe:

- HUD brackets or corner marks
- `hud-panel` class
- `box-shadow` (any)
- `text-shadow` (any)
- Rounded cards or pill shapes (`border-radius`)
- Generic shared blocks: `features-grid`, `pricing`, `testimonials`, `faq`, `logos`
