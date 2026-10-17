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
