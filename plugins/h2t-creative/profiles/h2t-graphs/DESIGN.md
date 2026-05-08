---
version: alpha
name: h2t-graphs
description: Bold typographic hierarchy with mono labels. Data-rich product landing aesthetic from lichtpfad graphs landing page. Inter for headlines (700-800), JetBrains Mono for nav/labels/captions.
colors:
  primary: "#e94560"
  on-surface: "#a0a0b8"
  on-surface-hi: "#d0d0e0"
  on-surface-dim: "#3a3a50"
  surface: "#060609"
  surface-low: "#0a0a10"
  surface-card: "#0e0e16"
  data-green: "#00ff88"
  data-blue: "#4a9eff"
  data-amber: "#ffb800"
typography:
  headline:
    fontFamily: Inter
    fontWeight: 800
  body:
    fontFamily: JetBrains Mono
---

<!-- Frontmatter conforms to the Stitch DESIGN.md open standard
     (Apache 2.0, https://github.com/google-labs-code/design.md).
     Carries the *default* (red) palette only; the blue and green
     palettes live in palettes/{blue,green}.css and remain part of
     the runtime CSS implementation layer beneath this spec. The
     `--color-accent-glow` and `--color-border` rgba values stay in
     CSS — Stitch Color type is hex SRGB only. The body sections
     below preserve the existing R1 component contract and coexist
     with the standard. -->

# h2t-graphs

## Brand Intent
Bold typographic hierarchy with mono labels. Data-rich product landing aesthetic — extracted from lichtpfad graphs landing page. Inter for headlines (700–800 weight), JetBrains Mono for nav/labels/captions.

## Color Tokens

### default (red)
- `--color-bg`: `#060609`
- `--color-bg2`: `#0a0a10`
- `--color-surface`: `#0e0e16`
- `--color-accent`: `#e94560`
- `--color-accent-glow`: `rgba(233,69,96,0.4)`
- `--color-green`: `#00ff88`
- `--color-blue`: `#4a9eff`
- `--color-amber`: `#ffb800`
- `--color-text`: `#a0a0b8`
- `--color-text-hi`: `#d0d0e0`
- `--color-text-dim`: `#3a3a50`
- `--color-border`: `rgba(233,69,96,0.12)`

### blue
Swap accent: `--color-accent: #4a9eff`, `--color-accent-glow: rgba(74,158,255,0.4)`, `--color-border: rgba(74,158,255,0.12)`

### green
Swap accent: `--color-accent: #00ff88`, `--color-accent-glow: rgba(0,255,136,0.4)`, `--color-border: rgba(0,255,136,0.12)`

## Available Palettes
- `default` — red accent
- `blue` — blue accent
- `green` — green accent

## Typography
- `--font-sans`: Inter, system-ui
- `--font-mono`: JetBrains Mono, monospace

## Restrictions
- Headlines only in Inter; all other text in JetBrains Mono
- Corner bracket decorations for badges and nav
- All spacing via CSS tokens only

## R1 Source Of Truth

- Primary: `profiles/h2t-graphs/sources/references.yaml`
- Live reference: `graphs.lichtpfadstudio.com`
- Local source: `C:/dev/h2t-landings/graphs/index.html`
- Legacy skill: `h2t:landing` v2.14.1 SKILL.md

## R1 Required Components

These components must be profile-specific. Shared variants are forbidden as validation evidence:

| Component | Visual Pattern |
|-----------|---------------|
| `hud-panel` | L-bracket corners, `--color-surface` bg, `--color-border` |
| `stats-bar` | Segmented cells, Inter 800, `text-shadow: 0 0 15px var(--color-accent-glow)` |
| `numbers-grid` | 4-cell grid, `--color-surface` per cell, 1px border |
| `chip-stack` | Monospace bordered labels, `.chip.hi` = accent border |
| `mermaid-diagram` | HUD panel + Mermaid dark theme |
| `screenshot-card` | HUD panel wrapping img, no image filters |
| `code-block` | HUD panel + pre/code |
| `cards-grid` | Surface cells, 1px grid separator, section-tag |
| `layers` | Numbered steps, accent glow on numbers |
| `comparison-table` | HUD panel + table, 1px column borders |

## Forbidden Substitutions

The following shared components MUST NOT appear in h2t-graphs validation recipe:

- `features-grid`
- `pricing`
- `testimonials`
- `faq`
- `logos`
