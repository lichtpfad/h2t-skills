---
name: landing
description: "HUD-style single-page landing generator. Dark tactical aesthetic with Mermaid diagrams, corner brackets, grid background, glow accents. Produces self-contained HTML. Triggers: 'landing', 'create landing', 'landing page', 'micro-presentation', 'showcase page', 'h2t:landing'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# HUD Landing Page Generator

Generate a single-file HTML landing page in HUD tactical aesthetic with Mermaid diagrams. No external dependencies except Google Fonts CDN and Mermaid.js CDN.

## When to use

- Creating project showcase / micro-presentation pages
- Marketing + technical landing pages for GitHub projects
- Single-page Netlify deploys
- Quick pitch pages with data visualizations

## Design Tokens

```css
:root {
  --bg:         #060609;
  --bg2:        #0a0a10;
  --surface:    #0e0e16;
  --accent:     #e94560;
  --accent-glow: rgba(233,69,96,0.4);
  --green:      #00ff88;
  --green-glow: rgba(0,255,136,0.3);
  --blue:       #4a9eff;
  --amber:      #ffb800;
  --text:       #a0a0b8;
  --text-hi:    #d0d0e0;
  --text-dim:   #3a3a50;
  --grid:       rgba(255,255,255,0.02);
  --border:     rgba(233,69,96,0.12);
  --mono:       'JetBrains Mono', monospace;
  --sans:       'Inter', system-ui, sans-serif;
  --corner:     12px;
}
```

## Fonts

```html
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
```

- **Body / labels / tags:** JetBrains Mono (monospace)
- **Headings / numbers:** Inter (sans-serif)

## Key Visual Elements

### 1. Grid Background

Subtle 40px grid on body, gives tactical/HUD feel:

```css
body::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 40px 40px;
}
```

### 2. Corner Brackets (HUD panels)

Red L-shaped corners on panels — the signature HUD element:

```css
.hud-panel {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2rem 2.5rem;
}
.hud-panel::before,
.hud-panel::after,
.hud-panel .corner-br::before,
.hud-panel .corner-br::after {
  content: '';
  position: absolute;
  width: var(--corner); height: var(--corner);
  border-color: var(--accent);
  border-style: solid;
}
.hud-panel::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.hud-panel::after  { top: -1px; right: -1px; border-width: 2px 2px 0 0; }
.hud-panel .corner-br::before { bottom: -1px; left: -1px; border-width: 0 0 2px 2px; }
.hud-panel .corner-br::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
```

Usage: `<div class="hud-panel"><span class="corner-br"></span>content</div>`

For simpler elements (stats, grids), use 2-corner variant:

```css
.element::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.element::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
```

### 3. Section Tags

Monospace labels with `//` prefix in accent color:

```css
.section-tag {
  font-size: 0.55rem;
  color: var(--text-dim);
  letter-spacing: 0.25em;
  text-transform: uppercase;
}
.section-tag::before { content: '// '; color: var(--accent); }
```

Usage: `<div class="section-tag">pipeline</div>` renders as `// PIPELINE`

### 4. Glow Effects

Apply text-shadow for glowing accent text:

```css
color: var(--accent);
text-shadow: 0 0 15px var(--accent-glow);
```

For green status indicators:
```css
color: var(--green);
text-shadow: 0 0 6px var(--green-glow);
```

### 5. Crosshair Cursor

```css
body { cursor: crosshair; }
```

### 6. Stats Bar

Segmented stat cells with corner brackets:

```css
.stats {
  display: flex; gap: 0;
  border: 1px solid var(--border);
  position: relative;
}
.stat {
  flex: 1; text-align: center;
  padding: 1.5rem 1rem;
  border-right: 1px solid var(--border);
  background: var(--surface);
}
.stat .num {
  font-family: var(--sans);
  font-size: 2.2rem; font-weight: 900;
  color: var(--accent);
  text-shadow: 0 0 15px var(--accent-glow);
}
.stat .lbl {
  font-size: 0.55rem; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.2em;
}
```

### 7. Numbers Grid

Grid with 1px borders (cell-based, like spreadsheet):

```css
.num-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
}
.num-cell {
  background: var(--surface);
  padding: 1.5rem 1rem; text-align: center;
}
```

### 8. Chip Tags

For tech stack, labels:

```css
.chip {
  font-family: var(--mono);
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 0.35rem 0.9rem;
  font-size: 0.7rem;
}
.chip.hi {
  border-color: rgba(233,69,96,0.25);
  color: var(--accent);
  text-shadow: 0 0 6px var(--accent-glow);
}
```

## Mermaid Integration

Include via CDN:

```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
```

Dark theme config matching HUD tokens:

```javascript
mermaid.initialize({
  startOnLoad: true,
  theme: 'dark',
  themeVariables: {
    darkMode: true,
    background: '#0e0e16',
    primaryColor: '#16161f',
    primaryTextColor: '#a0a0b8',
    primaryBorderColor: '#2a2a3a',
    lineColor: '#3a3a4a',
    secondaryColor: '#0e0e16',
    tertiaryColor: '#0e0e16',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '11px',
    clusterBkg: '#0a0a10',
    clusterBorder: '#1e1e2e',
    edgeLabelBackground: '#0a0a10',
  },
  flowchart: { curve: 'basis', padding: 14, htmlLabels: true }
});
```

Mermaid node color coding convention:

| Status | fill | stroke | color |
|--------|------|--------|-------|
| Done (green) | `#0a1a0d` | `#00ff88` | `#00ff88` |
| Active/accent (red) | `#1a0a10` | `#e94560` | `#e94560` |
| Info (blue) | `#0a0d1a` | `#4a9eff` | `#4a9eff` |
| Goal (amber) | `#0e0e14` | `#ffb800` | `#ffb800` |
| Dim/planned | `#0e0e14` | `#3a3a50` | `#3a3a50` |

Wrap mermaid in HUD panel:

```html
<div class="mermaid-wrap">
  <pre class="mermaid">
    graph LR
      A["Node"] --> B["Node"]
      style A fill:#0a1a0d,stroke:#00ff88,color:#00ff88
  </pre>
</div>
```

```css
.mermaid-wrap {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 1.5rem;
  overflow: hidden;  /* no scrollbars! */
}
/* Add corner brackets */
.mermaid-wrap::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.mermaid-wrap::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
```

## Screenshot Cards

For embedding app screenshots — NO scanlines or filters over images:

```css
.screen-card {
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
}
.screen-card img {
  width: 100%; display: block;
  filter: none;  /* never apply filters to screenshots */
}
.screen-card .caption { padding: 1rem 1.5rem; }
```

Green corner brackets for screenshot cards:

```css
.screen-card::before, .screen-card::after {
  border-color: var(--green);
}
```

## Page Structure Template

```
1. NAV        — fixed, blurred bg, [LOGO] + links
2. HERO       — badge tag, h1 with glow, description, stats bar
3. CONTEXT    — hud-panel with problem statement
4. PIPELINE   — mermaid flowchart (green = done)
5. DETAIL     — mermaid detail diagram
6. STUDIO     — screenshot cards (no scanlines!)
7. NUMBERS    — num-grid cells
8. GRAPH      — mermaid structure diagram
9. ROADMAP    — mermaid with done/next/planned color coding
10. STACK     — chip rows
11. FOOTER    — motto + credits
```

## Reference Implementation

See: `C:/dev/h2t-transcription/landing/index.html`

## Do NOT

- Add scanline overlays over images (impossible to exclude reliably)
- Use `overflow: auto` on mermaid containers (causes scrollbars)
- Apply `filter: brightness()` to screenshots
- Use rounded corners (`border-radius`) — HUD is sharp edges only
