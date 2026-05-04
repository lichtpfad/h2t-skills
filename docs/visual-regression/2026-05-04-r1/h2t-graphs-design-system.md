# h2t-graphs Design System
Extracted from: `C:/dev/h2t-landings/graphs/index.html` (899 lines, golden source)

---

## Color Tokens
Source: `:root` in `<style>`

| Token | Value |
|-------|-------|
| `--bg` | `#060609` |
| `--bg2` | `#0a0a10` |
| `--surface` | `#0e0e16` |
| `--accent` | `#e94560` |
| `--accent-glow` | `rgba(233,69,96,0.4)` |
| `--green` | `#00ff88` |
| `--green-glow` | `rgba(0,255,136,0.3)` |
| `--blue` | `#4a9eff` |
| `--amber` | `#ffb800` |
| `--text` | `#a0a0b8` |
| `--text-hi` | `#d0d0e0` |
| `--text-dim` | `#3a3a50` |
| `--grid` | `rgba(255,255,255,0.02)` ← subtle white, NOT accent-colored |
| `--border` | `rgba(233,69,96,0.12)` |
| `--mono` | `'JetBrains Mono', monospace` |
| `--sans` | `'Inter', system-ui, sans-serif` |
| `--corner` | `12px` |

No explicit spacing scale — values are used inline (0.6rem, 2rem, 2.5rem, etc.).

---

## Typography
Source: `<style>` block selectors

| Role | Selector | Value |
|------|----------|-------|
| Body base | `body` | `font-family: var(--mono); line-height: 1.7` |
| Section label | `.section-tag` | `font-size: 0.55rem; letter-spacing: 0.25em; text-transform: uppercase; color: var(--text-dim)` |
| Section label prefix | `.section-tag::before` | `content: '// '; color: var(--accent)` |
| Section heading | `h2` | `font-family: var(--sans); font-size: 1.6rem; font-weight: 800; color: var(--text-hi); letter-spacing: -0.02em; margin-bottom: 0.8rem` |
| Section subtext | `.sub` | `color: var(--text-dim); font-size: 0.78rem; max-width: 650px; line-height: 1.8` |
| Hero headline | `.hero h1` | `font-family: var(--sans); font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 900; line-height: 1.15; color: var(--text-hi); letter-spacing: -0.03em` |
| Hero glow word | `.hero h1 .glow` | `color: var(--accent); text-shadow: 0 0 20px var(--accent-glow), 0 0 40px rgba(233,69,96,0.15)` |
| Hero desc | `.hero .desc` | `font-size: 0.85rem; color: var(--text); max-width: 600px` |
| Nav brand | `nav .logo` | `font-weight: 700; color: var(--text-dim)` |
| Nav brand accent | `nav .logo span` | `color: var(--accent); text-shadow: 0 0 8px var(--accent-glow)` |
| Nav links | `nav .links a` | `color: var(--text-dim); text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.1em` |
| Footer motto | `footer .motto` | `font-family: var(--sans); font-size: 1.3rem; font-weight: 800; color: var(--text-hi)` |
| Footer motto accent | `footer .motto span` | `color: var(--accent); text-shadow: 0 0 15px var(--accent-glow)` |
| Footer sub | `footer p` | `color: var(--text-dim); font-size: 0.7rem; letter-spacing: 0.05em` |
| Code | inline `style` on `pre` | `font-size: 0.75rem; color: var(--text); line-height: 2; overflow-x: auto` |
| Code dim | `<span style="color:var(--text-dim)">` | comment-style lines |
| Code success | `<span style="color:var(--green)">` | output/response lines |
| Chip | `.chip` | `font-family: var(--mono); font-size: 0.7rem; font-weight: 500; color: var(--text-dim)` |
| Chip hi | `.chip.hi` | `color: var(--accent); text-shadow: 0 0 6px var(--accent-glow)` |

---

## Layout System
Source: `section`, `.hud-panel`, responsive rules

```css
/* Universal section container */
section {
  max-width: 1100px;
  margin: 0 auto;
  padding: 5rem 2rem;
  position: relative;
  z-index: 1;
}

/* Mobile */
@media (max-width: 700px) {
  section { padding: 3rem 1rem; }
}
```

- Max-width: **1100px** for all content sections
- No `.container` wrapper class — `section` itself is the container
- No explicit column grid system — uses `display: grid` per component

---

## Background FX
Source: `body::before`

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

- Color: `rgba(255,255,255,0.02)` — white, extremely subtle
- No `mask-image` gradient — grid is uniform full-page
- No `cursor: crosshair` on body

---

## Component Inventory

### nav
Source: `nav { ... }` CSS + `<nav>` HTML

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

HTML structure:
```html
<nav>
  <div class="logo">[<span>H2T</span>] GRAPHS</div>
  <div class="links">
    <a href="#why">Why</a>
    <a href="#how">How it works</a>
    ...
  </div>
</nav>
```

Note: `position: fixed`, NOT sticky. Logo format: `[<span>H2T</span>] GRAPHS` where `span` is accent color.

---

### hero
Source: `.hero { ... }` CSS + `<section class="hero">` HTML

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
/* Badge has only TOP-LEFT and TOP-RIGHT corners (no bottom corners) */
.hero-badge::before { top: -1px; left: -1px; border-width: 1px 0 0 1px; }
.hero-badge::after  { top: -1px; right: -1px; border-width: 1px 1px 0 0; }
```

- Hero is centered, full-height
- Badge has 2 accent corners (top-left, top-right only)
- Buttons: `.btn-row` flex center, `.btn-fill` + `.btn-outline`
- Body below hero is `padding-top: 0` sections

---

### hud-panel
Source: `.hud-panel { ... }` CSS

```css
.hud-panel {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2rem 2.5rem;
}
/* 4 accent corners via pseudo-elements + .corner-br span */
.hud-panel::before        { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.hud-panel::after         { top: -1px; right: -1px; border-width: 2px 2px 0 0; }
.hud-panel .corner-br::before { bottom: -1px; left: -1px; border-width: 0 0 2px 2px; }
.hud-panel .corner-br::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
/* All corners: width/height: var(--corner) = 12px; border-color: var(--accent) */
```

HTML structure requires `<span class="corner-br"></span>` as direct child for bottom corners.

Used for: code blocks, API access section. Not used as generic content card.

---

### mermaid-wrap
Source: `.mermaid-wrap { ... }` CSS

```css
.mermaid-wrap {
  position: relative; background: var(--surface);
  border: 1px solid var(--border); padding: 1.5rem; overflow: hidden;
}
/* Only 2 diagonal corners: top-left + bottom-right */
.mermaid-wrap::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; width: 10px; height: 10px; }
.mermaid-wrap::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; width: 10px; height: 10px; }
.mermaid { display: flex; justify-content: center; }
.mermaid svg { max-width: 100%; height: auto; }
```

Mermaid initialization (source: `<script>` at bottom of body):
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

---

### compare-grid / compare-card
Source: `.compare-grid`, `.compare-card` CSS

```css
.compare-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin: 2rem 0;
}
.compare-card {
  background: var(--surface); border: 1px solid var(--border);
  padding: 1.5rem 2rem; position: relative;
}
/* Single top-left corner only */
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

---

### feature-grid / feature-cell
Source: `.feature-grid`, `.feature-cell` CSS

```css
.feature-grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 1px; background: var(--border); border: 1px solid var(--border);
  position: relative;
}
/* 2 diagonal corners on the grid container */
.feature-grid::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; width: 8px; height: 8px; }
.feature-grid::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; width: 8px; height: 8px; }
.feature-cell { background: var(--surface); padding: 1.5rem; }
.feature-cell .icon { font-size: 1.2rem; margin-bottom: 0.5rem; }
.feature-cell h3 { font-family: var(--sans); font-size: 0.85rem; font-weight: 700; color: var(--text-hi); }
.feature-cell p { font-size: 0.7rem; color: var(--text-dim); line-height: 1.7; }
```

---

### chip / stack-row
Source: `.chip`, `.stack-row` CSS

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

---

### table (API/compare)
Source: `table`, `th`, `td` CSS

```css
table { border-collapse: collapse; font-size: 0.85rem; width: 100%; }
th, td { padding: 0.8rem 1.2rem; border: 1px solid var(--border); text-align: left; }
th { background: var(--surface); color: var(--text-dim); text-transform: uppercase;
     letter-spacing: 0.1em; font-size: 0.65rem; font-weight: 600; }
td { background: var(--bg2); }
```

---

### btn / btn-row
Source: `.btn`, `.btn-fill`, `.btn-outline` CSS

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

---

### footer
Source: `footer { ... }` CSS

```css
footer {
  text-align: center; padding: 4rem 2rem;
  border-top: 1px solid var(--border);
  position: relative; z-index: 1;
}
```

---

## Interaction / FX Grammar

| Effect | Selector / Rule |
|--------|----------------|
| Background grid | `body::before` — fixed, full-page, `rgba(255,255,255,0.02)` white, 40×40px |
| Smooth scroll | `html { scroll-behavior: smooth }` |
| Nav link hover glow | `nav .links a:hover { color: var(--accent); text-shadow: 0 0 6px var(--accent-glow) }` |
| CTA fill hover | `.btn-fill:hover { box-shadow: 0 0 20px var(--accent-glow) }` |
| Hero word glow | `.glow { text-shadow: 0 0 20px var(--accent-glow), 0 0 40px rgba(233,69,96,0.15) }` |
| Footer motto glow | `.motto span { text-shadow: 0 0 15px var(--accent-glow) }` |
| Chip hi glow | `.chip.hi { text-shadow: 0 0 6px var(--accent-glow) }` |
| Compare green glow | `.compare-card.yes h3 { text-shadow: 0 0 8px var(--green-glow) }` |
| Backdrop blur nav | `nav { backdrop-filter: blur(12px); background: rgba(6,6,9,0.95) }` |
| Canvas graph viz | `<canvas id="graphCanvas">` — interactive force-directed graph (JS, ~350 lines) |
| Mermaid dark theme | `mermaid.initialize()` with full `themeVariables` in `<script>` at bottom of body |

---

## Forbidden Patterns
(what is NOT in this design system)

- **No `cursor: crosshair`** on body — that's not in the source
- **No `mask-image` gradient** on `body::before` — grid is uniform, no fade
- **No stats-bar** with numbers (619/9/28) — does not exist in golden source
- **No numbers-grid** component — does not exist in golden source
- **No layers** component — does not exist in golden source
- **No `position: sticky`** on nav — nav is `position: fixed`
- **No border-radius** — corner-size is for L-bracket pseudo-elements, not rounded corners
- **No `box-shadow` on cards** — hover uses `box-shadow` only on `.btn-fill`, not on panels/cards
- **No left-aligned hero** — hero is always centered with `text-align: center; align-items: center`
- **No `.hud-panel` used as generic content block** — used only for code/API access sections

---

## Profile-Specific vs Reusable

| Element | Scope |
|---------|-------|
| Color tokens (`--bg`, `--surface`, `--accent` red/green/blue/amber) | profile-specific |
| Grid color `rgba(255,255,255,0.02)` | profile-specific |
| Section-tag `// ` prefix | profile-specific |
| L-bracket corners (hud-panel, mermaid-wrap, compare-card) | profile-specific |
| `body::before` grid pattern | profile-specific |
| Nav structure (`[H2T] brand + links`) | profile-specific |
| Canvas graph animation | profile-specific |
| Mermaid themeVariables | profile-specific |
| `.section` container pattern (max-width + auto margins + padding) | reusable base pattern |
| `.btn` / `.btn-row` | reusable with profile tokens |
| `.chip` / `.stack-row` | reusable with profile tokens |
| `font-family: var(--mono/sans)` body/heading split | reusable pattern |
