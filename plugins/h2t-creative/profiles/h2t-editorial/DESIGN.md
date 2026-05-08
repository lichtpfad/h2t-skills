---
version: alpha
name: h2t-editorial
description: Light book-like aesthetic — serif headlines, generous whitespace, classical typography. Extracted from h2t:deck STYLE 2.
colors:
  primary: "#c45a3c"
  on-surface: "#1a1a1a"
  on-surface-dim: "#6b6b6b"
  surface: "#faf9f6"
  surface-low: "#f0eeeb"
  surface-card: "#ffffff"
  border: "#e0ddd8"
typography:
  headline-display:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Playfair Display
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.3
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.75
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.6
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.04em
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
rounded:
  sm: 4px
  md: 8px
  lg: 12px
---

<!-- Frontmatter above conforms to the Stitch DESIGN.md open standard
     (Apache 2.0, https://github.com/google-labs-code/design.md). It
     carries the *default* palette only; the warm and night palettes
     live in palettes/{warm,night}.css and remain part of the runtime
     CSS implementation layer beneath this spec. The body sections
     below preserve the existing h2t-creative editorial conventions
     (Brand Intent / multi-palette table / Restrictions); they coexist
     with the standard rather than replace it. -->

# h2t-editorial

## Brand Intent
Light book-like aesthetic — serif headlines, generous whitespace, classical typography. Extracted from h2t:deck STYLE 2. Playfair Display for headlines, Inter for body.

## Color Tokens

### default (dark ink)
- `--color-bg`: `#faf9f6`
- `--color-bg-light`: `#f0eeeb`
- `--color-bg-card`: `#ffffff`
- `--color-text`: `#1a1a1a`
- `--color-text-dim`: `#6b6b6b`
- `--color-accent`: `#c45a3c`
- `--color-border`: `#e0ddd8`

### warm
- `--color-bg`: `#fdf8f0`, `--color-bg-light`: `#f5ede0`, `--color-bg-card`: `#fffdf9`
- `--color-text`: `#2a1f14`, `--color-text-dim`: `#8a7a6a`, `--color-accent`: `#b85c30`, `--color-border`: `#e8ddd0`

### night
- `--color-bg`: `#1a1614`, `--color-bg-light`: `#242018`, `--color-bg-card`: `#2a2620`
- `--color-text`: `#e8dfd4`, `--color-text-dim`: `#9a9080`, `--color-accent`: `#d4aa50`, `--color-border`: `#403830`

## Available Palettes
- `default` — dark ink
- `warm` — cream
- `night` — dark gold

## Typography
- `--font-display`: Playfair Display, Georgia, serif
- `--font-body`: Inter, Helvetica Neue, sans-serif

## Restrictions
- Headlines always in Playfair Display
- Body always in Inter
- Large leading (1.75+)
