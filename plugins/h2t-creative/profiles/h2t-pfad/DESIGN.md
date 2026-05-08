---
version: alpha
name: h2t-pfad
description: Elegant tactical dashboard aesthetic — small monospace, red accent. Extracted from PFAD design system (lichtpfad internal dashboard). Corner bracket tags, micro-type scale at 12px base. Canvas2D dot-field particle network as background fx.
colors:
  primary: "#d63030"
  on-surface: "#eeeeee"
  on-surface-dim: "#6e6e6e"
  on-surface-muted: "#444444"
  surface: "#0c0c0c"
  surface-card: "#111111"
typography:
  body:
    fontFamily: JetBrains Mono
    fontSize: 12px
  label:
    fontFamily: JetBrains Mono
    fontSize: 8px
rounded:
  none: 0px
---

<!-- Frontmatter conforms to the Stitch DESIGN.md open standard
     (Apache 2.0, https://github.com/google-labs-code/design.md).
     Single-palette profile — frontmatter is the canonical source.
     The `--color-accent-dim` / `--color-accent-glow` /
     `--color-border` rgba values stay in palettes/default.css —
     Stitch Color type is hex SRGB only. `rounded.none: 0px`
     formalises the sharp-edges restriction. The body sections below
     preserve the existing h2t-creative conventions and coexist with
     the standard. -->

# h2t-pfad

## Brand Intent
Elegant tactical dashboard aesthetic — small, monospace, red accent. Extracted from PFAD design system (lichtpfad internal dashboard). Corner bracket tags, `// SECTION` labels, micro-type scale at 12px base. Canvas2D dot-field particle network as background fx.

## Color Tokens

### default (red)
- `--color-bg`: `#0c0c0c`
- `--color-bg-card`: `#111111`
- `--color-fg`: `#eeeeee`
- `--color-fg-dim`: `#6e6e6e`
- `--color-fg-muted`: `#444444`
- `--color-accent`: `#d63030`
- `--color-accent-dim`: `rgba(214,48,48,0.4)`
- `--color-accent-glow`: `rgba(214,48,48,0.18)`
- `--color-border`: `rgba(255,255,255,0.10)`

## Available Palettes
- `default` — red accent (original PFAD)

## Typography
- `--font`: JetBrains Mono, IBM Plex Mono, monospace
- Base: 12px, labels: 8px, nano: 7.5px — no sans-serif

## Restrictions
- All text monospace only
- No border-radius (sharp edges)
- Corner brackets via CSS ::before/::after on key elements
- fx/ background: Canvas2D dot-field particle network
