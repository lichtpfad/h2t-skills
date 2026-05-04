---
type: plan
status: draft — awaiting approval
created: 2026-05-04
author: Claude / Stanislav Glazov
parent-plan: 2026-05-04-h2t-creative-extraction-pipeline.md
source-of-truth:
  - docs/visual-regression/2026-05-04-r1/h2t-graphs-design-system.md
  - docs/visual-regression/2026-05-04-r1/h2t-mono-design-system.md
---

# h2t-creative Step 3: Modularization Plan

## Rule

Every value in this document is copied verbatim from the two design-system documents above.
No renaming. No aesthetics improvement. Mechanical cut only.

---

## Profile: h2t-graphs

### Target file tree

```
plugins/h2t-creative/profiles/h2t-graphs/
├── tokens.css
├── palettes/
│   └── default.css
├── profile.yaml
├── components/
│   ├── nav/
│   │   ├── nav.html
│   │   └── nav.css
│   ├── hero/
│   │   ├── hero.html
│   │   └── hero.css
│   ├── hud-panel/
│   │   ├── hud-panel.html
│   │   └── hud-panel.css
│   ├── mermaid-wrap/
│   │   ├── mermaid-wrap.html
│   │   └── mermaid-wrap.css
│   ├── compare-grid/
│   │   ├── compare-grid.html
│   │   └── compare-grid.css
│   ├── feature-grid/
│   │   ├── feature-grid.html
│   │   └── feature-grid.css
│   ├── stack-row/
│   │   ├── stack-row.html
│   │   └── stack-row.css
│   ├── btn/
│   │   ├── btn.html
│   │   └── btn.css
│   └── footer/
│       ├── footer.html
│       └── footer.css
└── validation/
    └── recipe.yaml
```

### tokens.css
Values from `h2t-graphs-design-system.md § Color Tokens` — exact copy:

```css
:root {
  --bg:          #060609;
  --bg2:         #0a0a10;
  --surface:     #0e0e16;
  --accent:      #e94560;
  --accent-glow: rgba(233,69,96,0.4);
  --green:       #00ff88;
  --green-glow:  rgba(0,255,136,0.3);
  --blue:        #4a9eff;
  --amber:       #ffb800;
  --text:        #a0a0b8;
  --text-hi:     #d0d0e0;
  --text-dim:    #3a3a50;
  --grid:        rgba(255,255,255,0.02);
  --border:      rgba(233,69,96,0.12);
  --mono:        'JetBrains Mono', monospace;
  --sans:        'Inter', system-ui, sans-serif;
  --corner:      12px;
}
```

Note: `--sans` is `Inter`, NOT Space Grotesk. `--border` is `rgba(233,69,96,0.12)`, NOT white.

### body::before (background grid)
From `§ Background FX`:

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

No `mask-image`. No fade. Grid is uniform full-page.

### profile.yaml
From `§ Interaction / FX Grammar — Mermaid dark theme` and `§ Typography — fonts`:

```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800;900&display=swap
head_scripts:
  - https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js
```

### Component → golden selector mapping

| Component dir | Golden class(es) | Source section |
|--------------|-----------------|----------------|
| `nav/` | `nav`, `.logo`, `.links`, `.links a` | `§ nav` |
| `hero/` | `.hero`, `.hero-badge`, `.glow`, `.desc`, `.btn-row`, `.btn-fill`, `.btn-outline` | `§ hero` |
| `hud-panel/` | `.hud-panel`, `.corner-br` | `§ hud-panel` |
| `mermaid-wrap/` | `.mermaid-wrap`, `.mermaid`, `pre.mermaid` + mermaid init script | `§ mermaid-wrap` |
| `compare-grid/` | `.compare-grid`, `.compare-card`, `.compare-card.yes`, `.compare-card.no` | `§ compare-grid / compare-card` |
| `feature-grid/` | `.feature-grid`, `.feature-cell`, `.feature-cell .icon` | `§ feature-grid / feature-cell` |
| `stack-row/` | `.stack-row`, `.chip`, `.chip.hi` | `§ chip / stack-row` |
| `btn/` | `.btn`, `.btn-fill`, `.btn-outline`, `.btn-row` | `§ btn / btn-row` |
| `footer/` | `footer`, `.motto`, `.motto span` | `§ footer` |

### nav CSS (from `§ nav`)

```css
nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: rgba(6,6,9,0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  padding: 0.6rem 2rem;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.7rem; letter-spacing: 0.1em;
}
```

`position: fixed` — NOT sticky.

### hero CSS (from `§ hero`)

```css
.hero {
  min-height: 100vh;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center;
  padding-top: 6rem;
}
.hero-badge {
  font-size: 0.6rem; letter-spacing: 0.2em; text-transform: uppercase;
  color: var(--accent); border: 1px solid var(--border);
  padding: 0.3rem 1rem; margin-bottom: 2rem;
  position: relative; text-shadow: 0 0 10px var(--accent-glow);
}
.hero-badge::before { top: -1px; left: -1px; border-width: 1px 0 0 1px; }
.hero-badge::after  { top: -1px; right: -1px; border-width: 1px 1px 0 0; }
```

Badge has only 2 corners (top-left, top-right). Not 4.

### hud-panel CSS (from `§ hud-panel`)

```css
.hud-panel {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2rem 2.5rem;
}
.hud-panel::before        { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.hud-panel::after         { top: -1px; right: -1px; border-width: 2px 2px 0 0; }
.hud-panel .corner-br::before { bottom: -1px; left: -1px; border-width: 0 0 2px 2px; }
.hud-panel .corner-br::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
```

All 4 corners require `<span class="corner-br"></span>` in HTML.

### mermaid-wrap CSS (from `§ mermaid-wrap`)

```css
.mermaid-wrap {
  position: relative; background: var(--surface);
  border: 1px solid var(--border); padding: 1.5rem; overflow: hidden;
}
.mermaid-wrap::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; width: 10px; height: 10px; }
.mermaid-wrap::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; width: 10px; height: 10px; }
.mermaid { display: flex; justify-content: center; }
.mermaid svg { max-width: 100%; height: auto; }
```

Only 2 diagonal corners (top-left + bottom-right).

Mermaid init script (from `§ mermaid-wrap — Mermaid initialization`):

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
    fontSize: '17px',
    clusterBkg: '#0a0a10',
    clusterBorder: '#1e1e2e',
    edgeLabelBackground: '#0a0a10',
  },
  flowchart: { curve: 'basis', padding: 20, htmlLabels: true, nodeSpacing: 30, rankSpacing: 60 }
});
```

### compare-grid CSS (from `§ compare-grid / compare-card`)

```css
.compare-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin: 2rem 0;
}
.compare-card {
  background: var(--surface); border: 1px solid var(--border);
  padding: 1.5rem 2rem; position: relative;
}
.compare-card::before {
  content: ''; position: absolute; top: -1px; left: -1px;
  width: 10px; height: 10px; border-color: var(--accent);
  border-style: solid; border-width: 2px 0 0 2px;
}
.compare-card h3 { font-family: var(--sans); font-size: 0.95rem; font-weight: 700; }
.compare-card ul { list-style: none; font-size: 0.75rem; line-height: 2; }
.compare-card.yes h3 { color: var(--green); text-shadow: 0 0 8px var(--green-glow); }
.compare-card.yes ul li::before { content: '✓'; color: var(--green); }
.compare-card.no h3 { color: var(--text-dim); }
.compare-card.no ul li::before { content: '—'; color: var(--text-dim); }
```

### feature-grid CSS (from `§ feature-grid / feature-cell`)

```css
.feature-grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 1px; background: var(--border); border: 1px solid var(--border);
  position: relative;
}
.feature-grid::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; width: 8px; height: 8px; }
.feature-grid::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; width: 8px; height: 8px; }
.feature-cell { background: var(--surface); padding: 1.5rem; }
.feature-cell .icon { font-size: 1.2rem; margin-bottom: 0.5rem; }
.feature-cell h3 { font-family: var(--sans); font-size: 0.85rem; font-weight: 700; color: var(--text-hi); }
.feature-cell p { font-size: 0.7rem; color: var(--text-dim); line-height: 1.7; }
```

### stack-row / chip CSS (from `§ chip / stack-row`)

```css
.stack-row {
  display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; margin-bottom: 0.6rem;
}
.chip {
  font-family: var(--mono); background: var(--surface);
  border: 1px solid var(--border); padding: 0.35rem 0.9rem;
  font-size: 0.7rem; font-weight: 500; color: var(--text-dim);
}
.chip.hi {
  border-color: rgba(233,69,96,0.25); color: var(--accent);
  text-shadow: 0 0 6px var(--accent-glow);
}
```

### btn CSS (from `§ btn / btn-row`)

```css
.btn {
  font-family: var(--mono); font-size: 0.75rem;
  padding: 0.7rem 2rem; letter-spacing: 0.1em; text-transform: uppercase;
}
.btn-fill { background: var(--accent); color: #fff; }
.btn-fill:hover { box-shadow: 0 0 20px var(--accent-glow); }
.btn-outline { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
.btn-outline:hover { background: rgba(233,69,96,0.1); }
.btn-row { display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; }
```

### section layout (from `§ Layout System`)

```css
section {
  max-width: 1100px;
  margin: 0 auto;
  padding: 5rem 2rem;
  position: relative;
  z-index: 1;
}
@media (max-width: 700px) {
  section { padding: 3rem 1rem; }
}
```

No `.container` class — `section` is the container.

### validation/recipe.yaml — reference-equivalent content

Exact golden DOM order. Section labels are literal strings from golden source — do not normalize or compress.

1. Hero — `[H2T] GRAPHS` logo, glow headline, `.desc` subtitle, `.btn-row` with 2 buttons
2. `// how it works` → graph-canvas section: `.section-tag` + `h2` + `.sub` + `mermaid-wrap` containing `<canvas id="graphCanvas">` + caption
3. `// positioning` → `compare-grid`: `.compare-grid` with `.compare-card.no` and `.compare-card.yes`
4. `// architecture` → `mermaid-wrap`
5. `// search` → `feature-grid`: `.feature-grid` with 4 `.feature-cell` items
6. `// provenance` → `mermaid-wrap` + inline source-types paragraph
7. `// real-time` → `hud-panel`/code-block: `.hud-panel` with `.corner-br` and `<pre><code>`
8. `// integrations` → `mermaid-wrap` + `compare-grid`: mermaid diagram followed by second `.compare-grid`
9. `// stack` → `stack-row`: three `.stack-row` instances with `.chip` / `.chip.hi`
10. `// access` → `hud-panel`: API access block with two code examples
11. `footer` with `.motto`

### Forbidden patterns (from `§ Forbidden Patterns`)

Test assertions — these must be ABSENT from assembled output:

```
ABSENT: cursor: crosshair
ABSENT: mask-image
ABSENT: .stats-bar
ABSENT: .numbers-grid
ABSENT: .layers
ABSENT: position: sticky   (in nav selector context)
ABSENT: border-radius       (structural — not decorative)
```

---

## Profile: h2t-mono

### Target file tree

```
plugins/h2t-creative/profiles/h2t-mono/
├── tokens.css
├── palettes/
│   └── default.css
├── profile.yaml
├── components/
│   ├── hero/
│   │   ├── hero.html
│   │   └── hero.css
│   ├── card/
│   │   ├── card.html
│   │   └── card.css
│   ├── problem-grid/
│   │   ├── problem-grid.html
│   │   └── problem-grid.css
│   ├── pipeline/
│   │   ├── pipeline.html
│   │   └── pipeline.css
│   ├── c4-grid/
│   │   ├── c4-grid.html
│   │   └── c4-grid.css
│   ├── comparison-table/
│   │   ├── comparison-table.html
│   │   └── comparison-table.css
│   ├── features-grid/
│   │   ├── features-grid.html
│   │   └── features-grid.css
│   ├── faq-item/
│   │   ├── faq-item.html
│   │   └── faq-item.css
│   ├── cta-card/
│   │   ├── cta-card.html
│   │   └── cta-card.css
│   ├── btn/
│   │   ├── btn.html
│   │   └── btn.css
│   └── site-footer/
│       ├── site-footer.html
│       └── site-footer.css
└── validation/
    └── recipe.yaml
```

### tokens.css
Values from `h2t-mono-design-system.md § Color Tokens` and `§ Spacing System` — exact copy:

```css
:root {
  --bg:          #0a0a0a;
  --bg-card:     #111111;
  --fg:          #e0e0e0;
  --fg-dim:      #888888;
  --fg-muted:    #555555;
  --accent:      #d63030;
  --accent-dim:  rgba(214,48,48,0.4);
  --accent-glow: rgba(214,48,48,0.15);
  --ok:          #1DD9A0;
  --border:      rgba(255,255,255,0.10);
  --font:        'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;

  --grid:     8px;
  --space-xs: 8px;
  --space-sm: 16px;
  --space-md: 24px;
  --space-lg: 40px;
  --space-xl: 64px;
  --space-2xl: 80px;
  --space-3xl: 96px;
  --space-4xl: 120px;
}
```

Note: `--space-lg` = 40px, `--space-xl` = 64px, `--space-2xl` = 80px, `--space-3xl` = 96px.
`--border` is white `rgba(255,255,255,0.10)` — NOT accent-colored.

### body (from `§ Background`)

```css
body {
  font-family: var(--font);
  font-size: 14px;
  color: var(--fg);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
  line-height: 1.6;
  overflow-x: hidden;
}
```

No `body::before`. No background grid. No decorative elements on body.

### layout (from `§ Layout System`)

```css
:root {
  --max-width: 1200px;
  --side-padding: var(--space-lg);
  --col-gap: var(--space-md);
}
.container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding-left: var(--side-padding);
  padding-right: var(--side-padding);
}
section {
  padding-top: var(--space-3xl);
  padding-bottom: var(--space-3xl);
}
@media (max-width: 768px) {
  :root { --side-padding: var(--space-md); }
  section { padding-top: var(--space-xl); padding-bottom: var(--space-xl); }
}
```

Uses `.container` wrapper — unlike h2t-graphs where `section` is the container.

### profile.yaml

```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap
head_scripts: []
```

No mermaid. No external JS. Terminal and headline rotation are inline JS in component HTML.

### Component → golden selector mapping

| Component dir | Golden class(es) | Source section |
|--------------|-----------------|----------------|
| `hero/` | `.hero`, `.hero-logo`, `.hero-subtitle`, `.hero-headlines`, `.headline`, `.hero-cta`, `.hero-terminal-wrapper`, `.hero-terminal` | `§ hero`, `§ hero-terminal` |
| `card/` | `.card`, `.card::before`, `.card-num`, `.card-label`, `.card-text` | `§ card (generic)` |
| `problem-grid/` | `.problem-grid` (contains `.card` items) | `§ problem-grid` |
| `pipeline/` | `.desktop-pipeline`, `.mobile-pipeline`, inline SVG | `§ pipeline (SVG)` |
| `c4-grid/` | `.c4-grid`, `.c4-row`, `.c4-level`, `.c4-name`, `.c4-what`, `.c4-mapping` | `§ c4-grid / c4-row` |
| `comparison-table/` | `.table-scroll`, `.comparison-table`, `.sticky-col`, `.sticky-feature`, `.sticky-ours`, `.hl` | `§ comparison-table` |
| `features-grid/` | `.features-grid` (contains `.card` items) | `§ features-grid` |
| `faq-item/` | `.faq-item`, `details`, `summary` | `§ faq-item` |
| `cta-card/` | `.cta-card`, `.waitlist-form`, `.waitlist-form input` | `§ cta-card / waitlist-form` |
| `btn/` | `.btn`, `.btn-primary`, `.btn-secondary` | `§ btn` |
| `site-footer/` | `.site-footer` | `§ site-footer` |

### hero CSS (from `§ hero`)

```css
.hero {
  padding-top: var(--space-4xl);
  padding-bottom: var(--space-2xl);
  text-align: center;
}
```

No `min-height: 100vh`. No nav. No L-brackets anywhere.

### hero-terminal CSS (from `§ hero-terminal`)

```css
.hero-terminal-wrapper { max-width: 640px; margin: 0 auto var(--space-xl); height: 280px; }
.hero-terminal {
  position: absolute; inset: 0;
  text-align: left;
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: var(--space-md);
  font-size: clamp(11px, 1.2vw, 13px);
  line-height: 1.8;
  color: var(--fg-dim);
  overflow: hidden;
}
.term-line { opacity: 0; animation: fade-in 0.3s forwards; white-space: pre; }
.t-cmd { color: var(--accent); }
.t-ok  { color: var(--ok); }
.t-dim { color: var(--fg-muted); }
```

JS: lines appear sequentially with `fade-in`, 200–500ms delay per line, MAX_LINES=9.
Content: `$ specdesigner compile` → graph validation → per-module specs.

### card CSS (from `§ card (generic)`)

```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: var(--space-md);
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s;
}
.card:hover { border-color: rgba(255,255,255,0.18); }
.card::before {
  content: ''; position: absolute; top: 0; left: 0;
  width: 0; height: 2px; background: var(--accent);
  transition: width 0.4s ease;
}
.card:hover::before { width: 100%; }
```

Animated top-border on hover — NOT L-bracket corners.

### c4-grid CSS (from `§ c4-grid / c4-row`)

```css
.c4-row {
  display: grid; grid-template-columns: 1fr 1fr;
  border: 1px solid var(--border); border-bottom: none;
  background: var(--bg-card);
}
.c4-row:last-child { border-bottom: 1px solid var(--border); }
.c4-level {
  padding: var(--space-sm) var(--space-md);
  border-right: 1px solid var(--border);
}
.c4-name { font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--fg); }
.c4-what { font-size: 10px; color: var(--fg-muted); }
.c4-mapping { padding: var(--space-sm) var(--space-md); font-size: 14px; color: var(--accent); }
```

### comparison-table CSS (from `§ comparison-table`)

```css
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.comparison-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.comparison-table th, .comparison-table td {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border);
  text-align: center; white-space: nowrap;
}
.comparison-table th {
  background: var(--bg-card); color: var(--fg-dim);
  text-transform: uppercase; letter-spacing: 0.1em; font-weight: 400; font-size: 12px;
}
.comparison-table td { color: var(--fg-dim); font-size: 14px; }
.comparison-table td:first-child { text-align: left; color: var(--fg); font-size: 13px; }
.comparison-table .hl { color: var(--ok); font-weight: 500; }
.sticky-col { position: sticky; background: var(--bg-card); z-index: 2; }
.sticky-feature { left: 0; }
.sticky-ours { left: 160px; border-right: 2px solid rgba(29,217,160,0.2); }
```

Highlight color is `--ok` (teal), not `--accent`.

### faq-item CSS (from `§ faq-item`)

```css
.faq-item {
  border: 1px solid var(--border); border-bottom: none; background: var(--bg-card);
}
.faq-item:last-child { border-bottom: 1px solid var(--border); }
.faq-item summary {
  padding: var(--space-sm) var(--space-md);
  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 400;
  cursor: pointer; list-style: none;
  display: flex; justify-content: space-between; align-items: center;
}
.faq-item summary::after { content: '+'; color: var(--fg-muted); font-size: 16px; }
.faq-item[open] summary::after { content: '-'; }
.faq-item p { padding: 0 var(--space-md) var(--space-sm); font-size: 13px; color: var(--fg-dim); }
```

Native `<details>/<summary>` — no JS toggle.

### section-title (from `§ Typography`)

```css
.section-title {
  font-size: 14px; font-weight: 400; letter-spacing: 0.2em;
  color: var(--accent); text-transform: uppercase;
}
.section-title::before { content: ':: '; }
```

Prefix is `:: ` (double colon + space) — NOT `// `.

### validation/recipe.yaml — reference-equivalent content

Exact golden DOM order. Section labels are literal strings from golden source — do not normalize or compress.

1. Hero — `SPEC<span class="accent">DESIGNER</span>` logo, subtitle, rotating `.headline` items, CTA buttons, `.hero-terminal-wrapper`
2. `:: The Problem` → `problem-grid` (3 `.card` items, `.card-num` 01/02/03)
3. `:: How It Works` → `pipeline` SVG (desktop + mobile variants)
4. `:: Built on C4` → `c4-grid` with `.c4-row` rows
5. `:: Comparison` → `comparison-table` with `.sticky-col`
6. `:: Key Principles` → `features-grid` (`.card` items)
7. `:: See It In Action` → screenshot-frame: `.container` `text-align:center` + `.section-title` + bordered image wrapper (`max-width:960px; margin:0 auto; border:1px solid var(--border); border-radius:8px; overflow:hidden`) + caption
8. `:: FAQ` → list of `faq-item` (`<details>`)
9. `:: Get Early Access` → `cta-card` with `waitlist-form`
10. `site-footer`

### Forbidden patterns (from `§ Forbidden Patterns`)

Test assertions — these must be ABSENT from assembled output:

```
ABSENT: site-nav
ABSENT: .corner-tl
ABSENT: .corner-br
ABSENT: .hud-panel
ABSENT: .section-tag
ABSENT: repeating-linear-gradient
ABSENT: backdrop-filter
ABSENT: mermaid
ABSENT: min-height: 100vh
ABSENT: cursor: crosshair
```

---

## Execution order

1. h2t-graphs: tokens.css → body::before → nav → hero → hud-panel → mermaid-wrap → compare-grid → feature-grid → stack-row → btn → footer → recipe.yaml
2. h2t-mono: tokens.css → layout → hero (incl. hero-terminal inline JS) → card → problem-grid → pipeline SVG → c4-grid → comparison-table → features-grid → faq-item → cta-card → btn → site-footer → recipe.yaml
3. Forbidden-pattern tests for both profiles
4. Gate: human screenshot comparison against golden imports — no version bump before that

---

## Rules inherited from pipeline plan

1. Agent does not mark visual match as passed. Only human can pass.
2. Screenshots only through approved h2t screenshot workflow.
3. No invented content.
4. If assembled page differs from golden, that is a modularity error — fix components, do not redesign.
5. No version bump until Step 4 human gate passes.
