# h2t-mono (SpecDesigner) Design System
Extracted from: `C:/dev/h2t-landings/specdesigner.html` (1223 lines, golden source)

---

## Color Tokens
Source: `:root` in `<style>`

| Token | Value |
|-------|-------|
| `--bg` | `#0a0a0a` |
| `--bg-card` | `#111111` |
| `--fg` | `#e0e0e0` |
| `--fg-dim` | `#888888` |
| `--fg-muted` | `#555555` |
| `--accent` | `#d63030` |
| `--accent-dim` | `rgba(214,48,48,0.4)` |
| `--accent-glow` | `rgba(214,48,48,0.15)` ← very subtle, not 0.4 |
| `--ok` | `#1DD9A0` (teal green — used for success/highlight states) |
| `--border` | `rgba(255,255,255,0.10)` ← white border, NOT accent-colored |
| `--font` | `'JetBrains Mono', 'SF Mono', 'Fira Code', monospace` |

Note: accent color is `#d63030` (darker, less pink than h2t-graphs `#e94560`).

---

## Spacing System
Source: `:root` — explicit 8px grid

```css
--grid: 8px;
--space-xs:  8px   (grid × 1)
--space-sm:  16px  (grid × 2)
--space-md:  24px  (grid × 3)
--space-lg:  40px  (grid × 5)
--space-xl:  64px  (grid × 8)
--space-2xl: 80px  (grid × 10)
--space-3xl: 96px  (grid × 12)
--space-4xl: 120px (grid × 15)
```

Unlike h2t-graphs, spacing scale is explicit and strictly 8px-based.

---

## Layout System
Source: `.container`, `section`, `:root` layout vars

```css
:root {
  --max-width: 1200px;
  --side-padding: var(--space-lg); /* 40px desktop */
  --col-gap: var(--space-md); /* 24px */
}
.container {
  max-width: var(--max-width); /* 1200px */
  margin: 0 auto;
  padding-left: var(--side-padding);
  padding-right: var(--side-padding);
}
section {
  padding-top: var(--space-3xl);    /* 96px */
  padding-bottom: var(--space-3xl); /* 96px */
}

/* Mobile */
@media (max-width: 768px) {
  :root { --side-padding: var(--space-md); } /* 24px */
  section { padding-top: var(--space-xl); padding-bottom: var(--space-xl); } /* 64px */
}
```

- Max-width: **1200px** (wider than h2t-graphs 1100px)
- Uses `.container` wrapper class (unlike h2t-graphs which uses `section` directly)
- 12-column grid available via `.grid { display: grid; grid-template-columns: repeat(12, 1fr) }`

---

## Background
Source: no `body::before` in golden source

**No background grid pattern.** Clean black background `#0a0a0a`. No decorative elements on body.

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

---

## Typography
Source: `<style>` block selectors

| Role | Selector | Value |
|------|----------|-------|
| Body base | `body` | `font-family: var(--font); font-size: 14px; line-height: 1.6` |
| Section label | `.section-title` | `font-size: 14px; font-weight: 400; letter-spacing: 0.2em; color: var(--accent); text-transform: uppercase` |
| Section label prefix | `.section-title::before` | `content: ':: '` ← double colon, NOT `//` |
| Hero logo | `.hero-logo` | `font-size: clamp(36px, 5vw, 56px); font-weight: 300; letter-spacing: 0.1em; text-transform: uppercase` |
| Hero logo accent | `.hero-logo .accent` | `color: var(--accent)` (only "DESIGNER" part) |
| Hero subtitle | `.hero-subtitle` | `font-size: clamp(13px, 1.8vw, 16px); color: var(--fg-dim); letter-spacing: 0.08em` |
| Hero rotating headline | `.headline` | `font-size: clamp(16px, 2.5vw, 22px); font-weight: 300; color: var(--fg); letter-spacing: 0.02em` |
| Card number | `.card-num` | `font-size: 28px; font-weight: 300; color: var(--accent); opacity: 0.25; line-height: 1` |
| Card label | `.card-label` | `font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; font-weight: 400; color: var(--fg)` |
| Card text | `.card-text` | `font-size: 13px; font-weight: 300; color: var(--fg-dim); line-height: 1.7` |
| Node label | `.node-label` | `font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 400; color: var(--fg)` |
| Node desc | `.node-desc` | `font-size: 10px; color: var(--fg-dim); line-height: 1.5` |
| Section quote | `.section-quote` | `font-size: clamp(14px, 1.6vw, 16px); font-weight: 300; color: var(--fg-dim); font-style: italic; text-align: center` |
| Terminal cmd | `.t-cmd` | `color: var(--accent)` |
| Terminal ok | `.t-ok` | `color: var(--ok)` |
| Terminal dim | `.t-dim` | `color: var(--fg-muted)` |
| Btn | `.btn` | `font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; font-family: var(--font)` |
| Footer | `.site-footer` | `font-size: 10px; color: var(--fg-muted); letter-spacing: 0.1em` |

---

## Component Inventory

### hero
Source: `.hero`, `.hero-logo`, `.hero-subtitle`, `.hero-headlines`, `.hero-cta`, `.hero-terminal-wrapper` CSS

```css
.hero {
  padding-top: var(--space-4xl);    /* 120px */
  padding-bottom: var(--space-2xl); /* 80px */
  text-align: center;
}
```

No `min-height: 100vh`. No nav — the page has no navigation bar.

HTML structure:
```html
<section class="hero">
  <div class="container">
    <div class="hero-logo">SPEC<span class="accent">DESIGNER</span></div>
    <div class="hero-subtitle">Visual context designer for AI agents.</div>
    <div class="hero-headlines">
      <div class="headline active">One tool. Always up-to-date specs. Nothing to maintain.</div>
      <div class="headline">...</div>  <!-- rotates every 4s -->
    </div>
    <div class="hero-cta">
      <a href="#waitlist" class="btn btn-primary">JOIN WAITLIST</a>
      <a href="..." class="btn btn-secondary">TELEGRAM</a>
    </div>
    <div class="hero-terminal-wrapper"><div class="hero-terminal" id="hero-terminal"></div></div>
    <div class="hero-agents">...</div>  <!-- agent logo badges -->
  </div>
</section>
```

Note: **no navigation bar** in golden source. Page starts directly with hero.

---

### hero-terminal
Source: `.hero-terminal` CSS + terminal animation JS

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

- No L-bracket corners
- Animated via JS: lines appear with `fade-in` animation, scroll through lines, MAX_LINES=9
- Content: `$ specdesigner compile` → graph validation → per-module specs compilation

---

### card (generic)
Source: `.card` CSS

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

- **No L-bracket corners** — cards use animated top-border accent line on hover
- Border is white `rgba(255,255,255,0.10)`, not accent-colored
- `.card-num`: large faded accent number (opacity 0.25)

---

### problem-grid
Source: `.problem-grid` CSS

```css
.problem-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm); /* 16px */
}
/* Mobile */
@media (max-width: 768px) {
  .problem-grid { grid-template-columns: 1fr; gap: var(--space-xs); }
}
```

Contains 3 `.card` items with `.card-num` (01/02/03), `.card-label`, `.card-text`.

---

### pipeline (SVG)
Source: `.desktop-pipeline` + inline `<svg>` + `.mobile-pipeline` SVG

Desktop SVG: `viewBox="0 0 1100 170"` — 5 nodes (DESIGN/SPECIFY/VERIFY/DELIVER/IMPLEMENT) connected by horizontal lines with circular ports.

Each node: `<rect>` with colored top bar (`height: 2.5`), `<circle>` port dot, `<text>` label.

Node colors: DESIGN `#438DD5`, SPECIFY `#438DD5`, VERIFY `#00897B`, DELIVER `#E65100`, IMPLEMENT `#6B7280`

Mobile: vertical waterfall SVG, same nodes connected by zig-zag paths.

```css
.desktop-pipeline { overflow-x: auto; }
@media (max-width: 768px) {
  .desktop-pipeline { display: none !important; }
  .mobile-pipeline { display: block !important; }
}
```

---

### c4-grid / c4-row
Source: `.c4-grid`, `.c4-row`, `.c4-level`, `.c4-mapping` CSS

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

2-column table-like layout: level name/desc | mapping with `→` prefix.

---

### comparison-table
Source: `.comparison-table`, `.table-scroll`, `.sticky-col` CSS

```css
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.comparison-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.comparison-table th, .comparison-table td {
  padding: var(--space-sm) var(--space-md); /* 16px 24px */
  border: 1px solid var(--border);
  text-align: center; white-space: nowrap;
}
.comparison-table th {
  background: var(--bg-card); color: var(--fg-dim);
  text-transform: uppercase; letter-spacing: 0.1em; font-weight: 400; font-size: 12px;
}
.comparison-table td { color: var(--fg-dim); font-size: 14px; }
.comparison-table td:first-child { text-align: left; color: var(--fg); font-size: 13px; }
.comparison-table .hl { color: var(--ok); font-weight: 500; } /* highlight = green, not accent */
/* Sticky columns for scrollable table */
.sticky-col { position: sticky; background: var(--bg-card); z-index: 2; }
.sticky-feature { left: 0; }
.sticky-ours { left: 160px; border-right: 2px solid rgba(29,217,160,0.2); }
```

---

### faq-item
Source: `.faq-item`, `details`, `summary` CSS

```css
.faq-item {
  border: 1px solid var(--border); border-bottom: none; background: var(--bg-card);
}
.faq-item:last-child { border-bottom: 1px solid var(--border); }
.faq-item summary {
  padding: var(--space-sm) var(--space-md); /* 16px 24px */
  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 400;
  cursor: pointer; list-style: none;
  display: flex; justify-content: space-between; align-items: center;
}
.faq-item summary::after { content: '+'; color: var(--fg-muted); font-size: 16px; }
.faq-item[open] summary::after { content: '-'; }
.faq-item p { padding: 0 var(--space-md) var(--space-sm); font-size: 13px; color: var(--fg-dim); }
```

Uses native `<details>/<summary>` HTML — no JS toggle.

---

### features-grid
Source: `.features-grid` CSS

```css
.features-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px;
}
@media (max-width: 768px) {
  .features-grid { grid-template-columns: 1fr; gap: var(--space-xs); }
}
```

Contains `.card` items.

---

### btn
Source: `.btn`, `.btn-primary`, `.btn-secondary` CSS

```css
.btn {
  display: inline-flex; align-items: center;
  padding: 12px 32px; /* calc(grid×1.5) calc(grid×4) */
  font-family: var(--font); font-size: 11px;
  letter-spacing: 0.16em; text-transform: uppercase;
  border: 1px solid var(--border);
  transition: all 0.2s;
}
.btn-primary { background: var(--accent); color: var(--fg); border-color: var(--accent); }
.btn-primary:hover { background: transparent; color: var(--accent); }
.btn-secondary { background: transparent; color: var(--fg-dim); }
.btn-secondary:hover { border-color: var(--fg-dim); color: var(--fg); }
```

---

### cta-card / waitlist-form
Source: `.cta-card`, `.waitlist-form` CSS

```css
.cta-card {
  max-width: 640px; margin: 0 auto;
  background: var(--bg-card); border: 1px solid var(--border);
  padding: var(--space-lg); /* 40px */
}
.waitlist-form { display: flex; gap: var(--space-xs); }
.waitlist-form input {
  flex: 1; padding: 12px 16px;
  font-family: var(--font); font-size: 12px;
  background: var(--bg); border: 1px solid var(--border); color: var(--fg);
}
.waitlist-form input:focus { border-color: var(--accent); }
```

---

### site-footer
Source: `.site-footer` CSS

```css
.site-footer {
  padding: var(--space-md) 0; /* 24px */
  border-top: 1px solid var(--border);
  font-size: 10px; color: var(--fg-muted); letter-spacing: 0.1em;
}
```

Minimal — only copyright line inside `.container`.

---

## Interaction / FX Grammar

| Effect | Selector / Rule |
|--------|----------------|
| Card hover border | `.card:hover { border-color: rgba(255,255,255,0.18) }` |
| Card top accent line | `.card::before { width: 0 → 100%; height: 2px; background: var(--accent) }` on hover |
| Btn-primary hover | `background: transparent; color: var(--accent)` (inverts fill) |
| Btn-secondary hover | `border-color: var(--fg-dim); color: var(--fg)` |
| Terminal animation | JS: lines appear sequentially with fade-in, 200–500ms delay per line |
| Hero headline rotation | JS: `classList.toggle('active')` every 4000ms, `opacity: 0 → 1` via `transition: opacity 0.8s` |
| FAQ toggle | Native `<details>/<summary>`, `+` / `-` toggle char via `::after` |
| Node hover | `.node:hover { border-color: var(--accent) }` |
| No backdrop blur | No blur effects anywhere |
| No glow on body grid | No `body::before` at all |
| Smooth link transitions | `a { transition: opacity 0.2s }` |
| Agent logo hover | `.agent-logo:hover { opacity: 1 }` (from `opacity: 0.6`) |

---

## Forbidden Patterns
(what is NOT in this design system)

- **No navigation bar** — page has no nav/header element
- **No L-bracket corners** — no `.hud-panel` style pseudo-element corners
- **No background grid** — no `body::before` pattern
- **No accent-colored borders** — all borders are `rgba(255,255,255,0.10)` (white)
- **No `text-shadow` glow effects** on text — only subtle `--accent-glow: rgba(214,48,48,0.15)`
- **No backdrop-filter blur** — no glassmorphism
- **No mermaid diagrams** — pipeline uses SVG drawn directly
- **No section-tag with `//` prefix** — uses `:: ` (double colon)
- **No `min-height: 100vh`** hero — hero is padded, not full-height
- **No `cursor: crosshair`** anywhere
- **No sticky nav** — there is no nav
- **No `.surface` background cards** — cards use `--bg-card: #111111`

---

## Profile-Specific vs Reusable

| Element | Scope |
|---------|-------|
| Color tokens (all `--bg`, `--fg`, `--accent` red, `--ok` teal) | profile-specific |
| 8px spacing scale (`--space-*`) | reusable pattern (profile sets values) |
| `.container` + `.grid` layout wrapper | reusable base pattern |
| Section rhythm (96px desktop / 64px mobile) | profile-specific values |
| Section title `:: ` prefix | profile-specific |
| Card hover animated top-border | profile-specific |
| Terminal animation (JS) | profile-specific |
| Hero logo format (SPEC + DESIGNER accent) | profile-specific |
| Headline rotation JS | profile-specific |
| SVG pipeline (5-node diagram) | profile-specific |
| Comparison table with sticky columns | reusable with profile tokens |
| FAQ `<details>/<summary>` pattern | reusable with profile tokens |
| Waitlist CTA form | profile-specific |
| `--font` single monospace stack (no serif/sans split) | profile-specific (contrast to h2t-graphs which uses --mono + --sans) |
