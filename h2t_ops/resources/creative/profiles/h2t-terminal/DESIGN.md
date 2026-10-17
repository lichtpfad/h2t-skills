# h2t-terminal

## Brand Intent
Dark hacker aesthetic — monospace only, green accent, CSS scanline overlay. Extracted from h2t:deck STYLE 1. Uppercase labels, blinking cursor motif, crosshair cursor.

## Color Tokens

### default (green)
- `--color-bg`: `#0d1117`
- `--color-bg-light`: `#161b22`
- `--color-bg-card`: `#1c2129`
- `--color-text`: `#e6edf3`
- `--color-text-dim`: `#8b949e`
- `--color-accent`: `#00ff41`
- `--color-border`: `#30363d`

### amber
Same bg, `--color-accent: #d4a843`

### cyan
Same bg, `--color-accent: #4488cc`

## Available Palettes
- `default` — terminal green
- `amber` — amber
- `cyan` — blue-cyan

## Typography
- `--font`: JetBrains Mono, Fira Code, Menlo, monospace

## Restrictions
- No sans-serif
- CSS scanline overlay always present (in tokens.css body::after)
- Crosshair cursor
