---
version: alpha
name: h2t-default
description: Clean, editorial Swiss-grid aesthetic — high contrast, geometric precision, generous whitespace. Suited for technical product landings and educational presentations.
colors:
  primary: "#1a1aff"
  primary-hover: "#0000cc"
  on-surface: "#0a0a0a"
  on-surface-dim: "#6b7280"
  surface: "#ffffff"
  surface-low: "#f5f5f5"
  border: "#e5e7eb"
typography:
  body:
    fontFamily: system-ui
  headline:
    fontFamily: system-ui
---

<!-- Frontmatter conforms to the Stitch DESIGN.md open standard
     (Apache 2.0, https://github.com/google-labs-code/design.md).
     Single-palette profile — frontmatter is the canonical source.
     Body sections below preserve the existing h2t-creative
     conventions and coexist with the standard. -->

# h2t-default

## Brand Intent
Clean, editorial Swiss-grid aesthetic. High contrast, geometric precision, generous whitespace.
Suited for technical product landing pages and educational course presentations.

## Color Tokens
- `--color-bg`: #ffffff
- `--color-fg`: #0a0a0a
- `--color-accent`: #1a1aff
- `--color-accent-hover`: #0000cc
- `--color-muted`: #6b7280
- `--color-surface`: #f5f5f5
- `--color-border`: #e5e7eb

## Typography
- `--font-display`: system-ui, sans-serif
- `--font-body`: system-ui, sans-serif

## Restrictions
- Do NOT use drop shadows or gradients
- Maintain 8px spacing grid (use --space-* tokens only)
- Links must meet WCAG AA contrast ratio

## Usage Examples
Use for: Hou2Touch course landing pages, workshop announcements, tool documentation pages.
