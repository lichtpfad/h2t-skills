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
