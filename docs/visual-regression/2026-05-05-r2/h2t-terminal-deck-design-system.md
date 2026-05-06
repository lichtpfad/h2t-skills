# h2t-terminal deck Design System

**Form:** deck (slide-based presentation, single-file HTML, keyboard navigation, fixed viewport)
**Acceptance gate:** desktop/laptop slide fidelity. Mobile deck UX is deferred to #92 as a separate design task — R2a must not invent responsive/mobile presentation rules, but mobile screenshots are still required as **baseline for #92**. Catastrophic mobile breakage introduced by R2a must be recorded in `parity-notes.md`; mobile layout optimization is not part of the R2a gate.

## Sources

| Path (in golden import) | Role | Slides | Notes |
|---|---|---|---|
| `pos-sprint-terminal-example.html` | **Primary** — original skill `STYLE 1` | 7 | Authoritative for token contract and core component vocabulary |
| `merkazim.html` | **Secondary** — production deck | 20 | Authoritative for layout variety (title-block, divider-block, table) and palette extension (`--highlight`, `--pop`) |
| `pos-sprint-deck-SKILL.md` | **Skill contract** | — | Authoritative for canonical token list and required deck features |
| `pos-sprint-deck-README.md` | Skill README | — | Overview only |

Both goldens use **identical token family** for `--bg/--text/--accent/--font` — design system is single, not two competing systems.

---

## Color Tokens

Source: `:root` in both goldens + SKILL.md

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0d1117` | Body background |
| `--bg-light` | `#161b22` | Code-block background, hover surfaces |
| `--bg-card` | `#1c2129` | Card background, stat-box, code-block (terminal example) |
| `--text` | `#e6edf3` | Primary body text |
| `--text-dim` | `#8b949e` | Secondary text, labels, captions, slide-counter |
| `--accent` | `#55aa88` | Primary green — eyebrow `// ` prefix, cursor block, divider, progress bar, primary highlights |
| `--accent2` | `#d4a843` | Amber — secondary highlight, code args |
| `--accent3` | `#4488cc` | Blue — tertiary highlight |
| `--danger` | `#cc4444` | Red — warnings, top border on stat-box, danger duration tags |
| `--highlight` | `#9966cc` | Purple — extended palette (merkazim) |
| `--pop` | `#ee6688` | Pink — extended palette (merkazim, money/emphasis) |
| `--border` | `#30363d` | All borders (cards, stats, layers, code, table) |

**Palette policy:** `default` (canonical 7-color set as listed). No `amber` / `cyan` palette variants for deck — terminal landing palettes (`amber`, `cyan`) currently in `palettes/amber.css` / `cyan.css` apply only to landing form should it ever be added. Deck form uses `default` only (matches both goldens, matches SKILL.md).

---

## Typography

| Token / Selector | Value | Source |
|---|---|---|
| `--font-heading` | `'JetBrains Mono','Fira Code','SF Mono','Menlo','Consolas',monospace` | merkazim (5-fallback chain) |
| `--font-body` | identical to `--font-heading` | merkazim |
| Google Fonts link | `JetBrains+Mono:wght@400;500;600;700` (or `400;600;700`) | both goldens + SKILL.md |
| `body` | `font-size: 16px-17px; line-height: 1.6; -webkit-font-smoothing: antialiased; overflow: hidden; user-select: none` | both |
| `h1` | `font-size: 40px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px (≈0.04em); line-height: 1.15-1.2; color: var(--text)` | both |
| `h2` | `font-size: 22px-28px; font-weight: 600; letter-spacing: 0.02em; line-height: 1.25-1.3; color: var(--text)` | both (variance: pos-sprint 28px, merkazim 22px) — canonical = **24px** |
| `h3` | `font-size: 16px-18px; font-weight: 600; color: var(--text-dim); letter-spacing: 0.04em-1px; text-transform: uppercase` | both |
| `p`, `li` | `font-size: 16px-17px; line-height: 1.6-1.7; color: var(--text)` | both |

**Title-slide variant** (merkazim `.title-block h1`):
- `font-size: 64px; letter-spacing: 4px`
- subtitle (`.sub`): `font-size: 18px; color: var(--text-dim); max-width: 60ch; line-height: 1.55`

**Divider-slide variant** (merkazim `.divider-block h1`):
- `font-size: 48px; text-align: center`
- `divider-num` label: `font-size: 14px; color: var(--accent); letter-spacing: 4px`

---

## Spacing

No fixed spacing scale exported as tokens. Both goldens use ad-hoc px/em values. Canonical conventions to use in modular profile:

| Use | Value | Example |
|---|---|---|
| Slide padding | `56px 80px 80px` (merkazim) or `80px 10%` (pos-sprint) | Canonical = **`56px 80px 80px`** with `slide-inner max-width: 1100px` |
| Component vertical spacing | `12px–28px` between blocks | `margin-top: 14px-16px` typical |
| Card grid gap | `14px-20px` | merkazim: 14px, pos-sprint: 20px → canonical **16px** |
| Stat row gap | `14px-24px` | canonical **16px** |
| Quote-block padding | `12px 20px` to `20px 28px` | canonical **16px 24px** |
| Bullet list gap | `4px-12px` between items | canonical **8px** |

---

## Frame (global, outside slides)

### Slide counter
- **pos-sprint**: global `<div id="slide-counter">` with `<span class="current">01</span> / <span id="cnt-total">07</span>`
- **merkazim**: per-slide `<div class="slide-counter">` (duplicated in each slide)
- **Canonical for modular profile**: global frame element, `top: 24px; right: 32px; font-size: 12-13px; color: var(--text-dim); letter-spacing: 0.05em-1px`. Active number colored `var(--accent) font-weight: 600` (pos-sprint pattern).

### Progress bar
Both: `position: fixed; bottom: 0; left: 0; height: 3px; background: var(--accent); transition: width 0.3-0.4s; z-index: 100-1000`. pos-sprint adds `box-shadow: 0 0 8px var(--accent)` for glow.
**Canonical:** include `box-shadow` glow.

### Nav hint
- **pos-sprint**: `bottom: 20px; right: 32px; font-size: 12px`, text `arrows / space / swipe`
- **merkazim**: `bottom: 14px; left: 50%; transform: translateX(-50%); font-size: 10px`, text `← → / space / swipe · 1/20` (with live counter)
- **Canonical:** bottom-right (matches SKILL.md snippet)

### Nav buttons (merkazim only — extension)
`<button class="nav-btn prev">◄ prev</button>`, `next ►`. Optional in modular profile — recipe field decides whether to render.

CSS skeleton:
```css
.nav-btn { position: fixed; bottom: 28px; padding: 10px 18px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 4px; font-size: 13px; font-weight: 600; color: var(--text-dim); letter-spacing: 1px; text-transform: uppercase; cursor: pointer; }
.nav-btn.prev { left: 32px; } .nav-btn.next { right: 32px; }
.nav-btn:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-2px); }
.nav-btn .chevron { color: var(--accent); }
.nav-btn.disabled { opacity: 0.25; pointer-events: none; }
```

### Scanline overlay
Both use `body::after { background: repeating-linear-gradient(0deg|to bottom, transparent 0-2px, rgba(0,0,0,X) 2px, rgba(0,0,0,X) 4px); pointer-events: none; z-index: 9999 }` with X = 0.03 (merkazim, lighter) or 0.06 (pos-sprint).
**Canonical:** `rgba(0,0,0,0.06)` — matches SKILL.md snippet, more visible against `--bg`.

### Touch zones (pos-sprint only)
`#touch-left { left: 0; width: 50% }`, `#touch-right { right: 0; width: 50% }` — invisible left/right halves for tap navigation. Optional; both goldens already implement touch-swipe via JS, touch zones are duplicate UX. **Skip in modular profile** — JS swipe is sufficient.

---

## Slide structure

### Container
```html
<div id="deck">
  <section class="slide [center]" data-index="N">
    <div class="slide-inner">
      <!-- slide content -->
    </div>
  </section>
  ...
</div>
```

### Base CSS
```css
#deck { width: 100%; height: 100%; position: relative; }
.slide {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  justify-content: center; align-items: flex-start;
  padding: 56px 80px 80px;
  opacity: 0; pointer-events: none;
  transition: opacity 0.35s ease;
}
.slide.active { opacity: 1; pointer-events: all; }
.slide.center { align-items: center; text-align: center; }
.slide-inner { width: 100%; max-width: 1100px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
```

**Display strategy:** opacity-fade (pos-sprint) is preferred over `display: none` (merkazim) because it preserves layout and enables fade-out animations.

---

## Slide layouts (recipe vocabulary)

The recipe `slides:` array uses `layout:` field. Canonical layouts:

| `layout` | Purpose | Required content fields | Sources |
|---|---|---|---|
| `title` | Opening title slide. Centered or left-aligned hero. | `eyebrow?`, `headline`, `subline?`, `meta?` | pos-sprint slide 01 (`center`), merkazim slide 01 (`title-block`), merkazim slide 20 (`title-block`) |
| `divider` | Section divider. Centered. | `eyebrow`, `headline` | merkazim slides 04, 17 (`divider-block`) |
| `title-body` | Default content slide. h2 + content blocks. | `eyebrow?`, `headline`, `body_html` | most slides |
| `stats` | h2/headline + 3-up stat row | `eyebrow?`, `headline`, `stats[]` | pos-sprint slide 02, merkazim slides 14, 15, 16 |
| `cards` | h2/headline + N-card grid | `eyebrow?`, `headline`, `cards[]` | pos-sprint slide 04, merkazim slides 05, 12, 19 |
| `layers` | h2/headline + vertical ordered list with colored borders | `eyebrow?`, `headline`, `layers[]` | pos-sprint slide 05, merkazim slide 13 |
| `split` | h2/headline + 2-column body | `eyebrow?`, `headline`, `left_html`, `right_html` | merkazim slides 03, 06–09, 11, 14, 16, 18 |
| `code` | h2/headline + code block | `eyebrow?`, `headline`, `code_title?`, `code_html` | pos-sprint slide 06 |
| `table` | h2/headline + data table | `eyebrow?`, `headline`, `table_headers[]`, `table_rows[][]`, `note?` | merkazim slides 10, 15 |
| `quote` | h2/headline + quote-block + bullet-list | `eyebrow?`, `headline`, `quote_html`, `bullets[]?` | pos-sprint slide 03 |
| `final` | Closing slide. Large centered text. | `eyebrow?`, `headline`, `subline?` | pos-sprint slide 07 |

The `eyebrow` field always renders with `// ` prefix in green (matches both goldens — pos-sprint puts `// ` in CSS pseudo, merkazim puts it in content).

---

## Component primitives

### `slide-label` / `eyebrow`
```html
<div class="eyebrow">// pilot proposal · 2026.04.19</div>
```
```css
.eyebrow {
  font-size: 12px;
  color: var(--accent);
  letter-spacing: 0.12em-3px;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 18px;
}
```

Variant (pos-sprint): `--text-dim` color with `::before { content: '// '; color: var(--accent) }`. Canonical: store `// ` in content (merkazim style — simpler, no pseudo coupling).

### `divider`
```html
<div class="divider"></div>
```
```css
.divider { width: 56px; height: 2px; background: var(--accent); margin: 24px 0; }
.slide.center .divider { margin-left: auto; margin-right: auto; }
```

### `cursor` (blinking block on title)
```html
<h1 class="cursor">Building Your<br><span class="accent">Personal OS</span></h1>
```
```css
.cursor::after {
  content: '\2588';
  color: var(--accent);
  margin-left: 4px;
  animation: blink 1s-1.1s step-end infinite;
}
@keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: 0 } }
```

### `quote-block`
```html
<div class="quote-block">
  not a tool — an operating system.
  <div class="quote-source">// working definition · 2026</div>
</div>
```
```css
.quote-block {
  border-left: 3px solid var(--accent);
  padding: 20px 28px;
  background: var(--bg-light);
  margin: 8px 0 28px;
  font-size: 18px-19px; line-height: 1.55-1.65;
  color: var(--text); font-style: italic;
}
.quote-block .quote-source { font-style: normal; font-size: 13px; color: var(--text-dim); margin-top: 12px; opacity: 0.7; }
```

merkazim variant `.quote` (no background, no italic on container): support both via `quote-block` for emphasized callout, `quote` for inline pull.

### `bullet-list`
```html
<ul class="bullet-list">
  <li data-sym="-->">consistent output regardless of mood or energy</li>
</ul>
```
```css
.bullet-list { list-style: none; display: flex; flex-direction: column; gap: 12px; }
.bullet-list li { display: flex; align-items: baseline; gap: 14px; font-size: 16px; }
.bullet-list li::before { content: attr(data-sym); color: var(--accent); font-weight: 700; font-size: 14px; flex-shrink: 0; }
```

merkazim plain `ul li` variant uses `> ` prefix via `::before { content: '> ' }`. Canonical: support `data-sym` for custom symbols (`-->`, `>`, `>>`, etc.); default `> ` if absent.

### `stat-row` / `stat-box`
```html
<div class="stat-row">
  <div class="stat-box" data-index="01">
    <div class="stat-number">73%</div>
    <div class="stat-label">context switching every single day</div>
  </div>
</div>
```
```css
.stat-row { display: flex; gap: 16px; margin-top: 8px-14px; flex-wrap: wrap; }
.stat-box {
  flex: 1; min-width: 140px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-top: 2px solid var(--danger);  /* pos-sprint: red top accent for problem-stats */
  padding: 28px 24px; position: relative;
}
.stat-box::before { content: attr(data-index); position: absolute; top: 10px; right: 14px; font-size: 11px; color: var(--text-dim); opacity: 0.4; letter-spacing: 0.08em; }
.stat-number { font-size: 32px-36px; font-weight: 700; color: var(--danger); line-height: 1; margin-bottom: 12px; }
.stat-label { font-size: 14px; color: var(--text-dim); line-height: 1.5; }
```

merkazim `.stat` variant: smaller, centered, no top border, uses any accent color (`.num.accent`, `.num.accent2`, etc.). Canonical: support both via `stat-box` (problem-stats with `--danger` top) and `stat` (centered metrics).

### `card-row` / `card`
```html
<div class="card-row">
  <div class="card" style="--card-color: var(--accent);">
    <div class="card-icon">01 · rules</div>
    <div class="card-title">CLAUDE.md</div>
    <div class="card-desc">...</div>
  </div>
</div>
```
```css
.card-row { display: flex; gap: 16px-20px; width: 100%; margin-top: 8px-14px; }
.card {
  flex: 1; min-width: 230px;
  background: var(--bg-card); border: 1px solid var(--border);
  padding: 18px 24px-28px; position: relative; overflow: hidden;
  transition: border-color 0.2s;
}
.card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: var(--card-color, var(--accent)); }  /* pos-sprint top-line */
.card:hover { border-color: var(--accent); }
.card-icon { font-size: 13px; font-weight: 700; color: var(--card-color, var(--accent)); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 14px; }
.card-title { font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 10px; }
.card-desc { font-size: 14px; color: var(--text-dim); line-height: 1.6; }
```

merkazim variant uses `auto-fit grid` with `tag` chip + h3 + ul instead of icon/title/desc. Canonical: support both via `card-row` (3-up flex with explicit cards) and `cards` (auto-fit grid for variable-count card lists).

### `tag` (chip)
```html
<span class="tag amber">SESSION 2</span>
```
```css
.tag {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 3px;
  margin-bottom: 10px;
  background: rgba(85,170,136,0.15); color: var(--accent); letter-spacing: 1px;
}
.tag.amber { background: rgba(212,168,67,0.15); color: var(--accent2); }
.tag.blue { background: rgba(68,136,204,0.15); color: var(--accent3); }
.tag.purple { background: rgba(153,102,204,0.15); color: var(--highlight); }
.tag.pink { background: rgba(238,102,136,0.15); color: var(--pop); }
.tag.red { background: rgba(204,68,68,0.15); color: var(--danger); }
```

### `layers`
```html
<div class="layers">
  <div class="layer l1">
    <div class="layer-num">01</div>
    <div class="layer-name">Physical</div>
    <div class="layer-desc">hardware, files, folders, raw storage</div>
  </div>
</div>
```
```css
.layers { display: flex; flex-direction: column; gap: 8px-16px; width: 100%; margin-top: 8px-18px; }
.layer { display: flex; align-items: center; gap: 14px-20px; padding: 14px-20px 18px-24px; border: 1px solid var(--border); border-left: 3px solid var(--layer-color, var(--accent)); transition: transform 0.3s; }
.layer:hover { transform: translateX(6px); }  /* merkazim only */
.layer-num { font-size: 13px; font-weight: 700; color: var(--layer-color, var(--accent)); letter-spacing: 0.1em-1px; flex-shrink: 0; width: 36px-40px; }
.layer-name { font-size: 16px; font-weight: 700; color: var(--text); flex-shrink: 0; width: 140px-200px; }
.layer-desc { font-size: 13px-14px; color: var(--text-dim); flex: 1; line-height: 1.5; }
.layer.l1 { border-color: rgba(85,170,136,0.4); background: rgba(85,170,136,0.04); }
.layer.l2 { border-color: rgba(212,168,67,0.4); background: rgba(212,168,67,0.04); }
.layer.l3 { border-color: rgba(68,136,204,0.4); background: rgba(68,136,204,0.04); }
.layer.l4 { border-color: rgba(153,102,204,0.4); background: rgba(153,102,204,0.04); }
.layer.lh { border-color: rgba(204,68,68,0.4); background: rgba(204,68,68,0.04); }  /* danger highlight */
```

Per-layer color override via `style="--layer-color: ..."` (pos-sprint pattern). Canonical: support **both** preset classes (`l1`-`l4`, `lh`) AND inline custom color.

### `code-block`
```html
<div class="code-block" data-title="terminal">
  <pre>
<span class="code-prompt">$</span> <span class="code-cmd">mkdir</span> <span class="code-arg">~/.claude/skills</span>
  <span class="code-comment"># create your skills directory</span>
  </pre>
</div>
```
```css
.code-block {
  background: var(--bg-card); border: 1px solid var(--border);
  padding: 28px 32px; width: 100%; position: relative;
}
.code-block::before {  /* badge label, pos-sprint */
  content: attr(data-title);
  position: absolute; top: -1px; left: -1px;
  background: var(--accent); color: var(--bg);
  font-size: 11px; font-weight: 700; padding: 3px 10px;
  letter-spacing: 0.08em; text-transform: uppercase;
}
.code-block pre { font-family: var(--font); font-size: 14px-15px; line-height: 1.7-1.9; color: var(--text); margin-top: 16px; white-space: pre; }
.code-prompt { color: var(--accent); user-select: none; }
.code-cmd    { color: var(--text); }
.code-arg    { color: var(--accent2); }
.code-comment{ color: var(--text-dim); font-size: 13px; }
```

merkazim variant uses `--bg-light` background, no `data-title` badge, simpler. Canonical: support both — `data-title` is optional.

### `split`
```html
<div class="split">
  <div><h3 class="accent">// section a</h3>...</div>
  <div><h3 class="accent2">// section b</h3>...</div>
</div>
```
```css
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-top: 14px; }
```

### `table`
```html
<table>
  <thead><tr><th>Column</th>...</tr></thead>
  <tbody><tr><td class="accent">Cell</td><td class="mono">value</td>...</tr></tbody>
</table>
```
```css
table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 14px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { font-size: 11px; letter-spacing: 1.5px; color: var(--text-dim); text-transform: uppercase; font-weight: 600; }
td.mono { font-family: var(--font-heading); color: var(--accent2); }  /* highlight numerics */
```

### `duration-tag`
```html
<div class="duration-tag">2 встречи × 3 часа</div>
<div class="duration-tag danger">3 недели · 4 встречи · оценочно</div>
```
```css
.duration-tag {
  display: inline-block; font-size: 12px; padding: 4px 10px;
  border: 1px solid var(--accent); color: var(--accent);
  border-radius: 3px; letter-spacing: 1px; margin-bottom: 14px;
}
.duration-tag.danger { border-color: var(--danger); color: var(--danger); }
```

### `disclaimer-badge`
```html
<div class="disclaimer-badge">⚠ гипотеза</div>
```
```css
.disclaimer-badge {
  display: inline-block; padding: 4px 12px; margin-bottom: 12px;
  border: 1px dashed var(--danger); border-radius: 3px;
  font-size: 11px; color: var(--danger);
  letter-spacing: 2px; text-transform: uppercase;
}
```

### `pills`
```html
<div class="pills">
  <span class="pill">topic A</span>
</div>
```
```css
.pills { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; }
.pill {
  display: inline-block; font-size: 14px; padding: 8px 16px;
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text); border-radius: 999px; transition: all 0.2s;
}
.pill:hover { border-color: var(--accent); color: var(--accent); }
```

### `meta-note`
```html
<p class="meta-note">Решение за Merkazim — обсуждаем на встрече.</p>
```
```css
.meta-note { font-size: 12px; color: var(--text-dim); margin-top: 12px; font-style: italic; }
```

### Color utility classes
```css
.dim       { color: var(--text-dim); }
.accent    { color: var(--accent); }     /* green */
.accent2   { color: var(--accent2); }    /* amber */
.accent3   { color: var(--accent3); }    /* blue */
.danger    { color: var(--danger); }     /* red */
.highlight { color: var(--highlight); }  /* purple */
.pop       { color: var(--pop); }        /* pink */
.bold      { font-weight: 700; }
```

These are required as inline-text emphasis classes — bodies use them via `{{ ... | safe }}` injection in templates. **Forbidden:** emojis as visual emphasis (per SKILL.md content guidelines). Use color utilities instead.

---

## Animation

### Fade-up on slide activation
```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px-22px); }
  to   { opacity: 1; transform: translateY(0); }
}
.slide.active .slide-inner > * {
  animation: fadeUp 0.45s-0.5s ease-out both;
}
.slide.active .slide-inner > *:nth-child(1) { animation-delay: 0.00s; }
.slide.active .slide-inner > *:nth-child(2) { animation-delay: 0.08s; }
.slide.active .slide-inner > *:nth-child(3) { animation-delay: 0.16s; }
.slide.active .slide-inner > *:nth-child(4) { animation-delay: 0.24s; }
.slide.active .slide-inner > *:nth-child(5) { animation-delay: 0.32s; }
.slide.active .slide-inner > *:nth-child(6) { animation-delay: 0.40s; }
.slide.active .slide-inner > *:nth-child(7) { animation-delay: 0.48s; }
.slide.active .slide-inner > *:nth-child(8) { animation-delay: 0.56s; }
```

**Canonical:** 0.5s duration, 0.08s stagger, up to 8 children. Selector matches merkazim pattern (auto-applies to slide-inner direct children; no `.animate` opt-in class needed).

### Slide transition
- pos-sprint: `transition: opacity 0.35s ease` (cross-fade)
- merkazim: `display: none/flex` (instant)
- **Canonical: opacity-fade**

### Cursor blink
`1.0s-1.1s step-end infinite`. Canonical: **1.0s**.

### Card / pill / nav-btn hover
- Card border-color → `--accent`, 0.2s
- Nav-btn `transform: translateY(-2px)`, color → `--accent`
- Layer `transform: translateX(6px)`, 0.3s

---

## Navigation (JS)

Required behaviors (both goldens implement):

1. **Keyboard:** ArrowRight/ArrowDown/Space/Enter → next; ArrowLeft/ArrowUp/Backspace → prev; Home → first; End → last.
2. **Touch swipe:** horizontal swipe >40-50px → next/prev. Ignore predominantly-vertical swipes.
3. **Update on slide change:**
   - Toggle `.active` class on slides
   - Update progress bar width: `((current+1) / total) * 100` (merkazim) or `(current / (total-1)) * 100` (pos-sprint, normalized 0-100)
   - Update slide counter (current number, optional total)
   - **Canonical:** use merkazim formula (`(current+1)/total*100`) — first slide shows >0% progress, more intuitive
4. **Hash sync (merkazim):** `history.replaceState(null, '', '#' + (current+1))` and read `location.hash` on init. **Canonical:** include — supports deep-linking to slide.
5. **Optional nav buttons (merkazim):** prev/next with disabled state on edges. **Canonical:** include as opt-in via recipe field.

JS is generated inline in single-file output — modular profile must inline at assembly time, not link external script.

---

## Required HTML head boilerplate

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
```

`profile.yaml` `web_fonts` list must produce these exact `<link>` tags in `<head>`.

---

## Recipe contract

```yaml
title: "Building Your Personal OS"
form: deck
profile: h2t-terminal
palette: default

# Optional global frame controls
nav_buttons: false   # default: false (only nav-hint shown)
nav_hint_text: "arrows / space / swipe"  # default

slides:
  - layout: title
    eyebrow: "session 01"
    headline: 'Building Your<br><span class="accent">Personal OS</span>'
    subline: "from chaos to system"
    meta: '// speaker name &nbsp;&nbsp;|&nbsp;&nbsp; 2026'
    align: center  # title-block default = left, center = pos-sprint variant
    cursor: true   # adds blinking block to headline

  - layout: title-body
    eyebrow: "the problem"
    headline: 'Most knowledge workers<br>operate <span class="danger">without a system.</span>'
    body_html: '<div class="divider"></div>...'

  - layout: stats
    eyebrow: "the problem"
    headline: '...'
    stats:
      - { number: "73%", label: "context switching every single day", index: "01", variant: "stat-box" }
      - { number: "4.1h", label: "lost to tool fragmentation weekly", index: "02", variant: "stat-box" }

  - layout: cards
    eyebrow: "components"
    headline: 'The <span class="accent">Building Blocks</span>'
    cards:
      - { tag: "01 · rules", title: "CLAUDE.md", desc: "...", color: "var(--accent)", variant: "card-row" }

  - layout: layers
    eyebrow: "architecture"
    headline: 'System <span class="accent">Architecture</span>'
    layers:
      - { num: "01", name: "Physical", desc: "...", color: "#cc6677" }
      - { num: "02", name: "Interface", desc: "...", preset: "l2" }

  - layout: split
    eyebrow: "// 02 · формат"
    headline: 'Лаборатория. 15 человек. <span class="accent">3 часа.</span>'
    left_html: '<h3 class="accent">// параметры</h3><ul>...</ul>'
    right_html: '<h3 class="accent2">// структура встречи</h3><ul>...</ul>'

  - layout: code
    eyebrow: "getting started"
    headline: 'Ship in <span class="accent">30 minutes</span>'
    code_title: "terminal"
    code_html: '<span class="code-prompt">$</span> <span class="code-cmd">mkdir</span> <span class="code-arg">~/.claude/skills</span>...'

  - layout: table
    eyebrow: "// 04 · варианты пилота"
    headline: "Как треки собираются"
    table_headers: ["Вариант", "Объём", "Логика"]
    table_rows:
      - ['<span class="accent">A · Узкий фокус</span>', '<span class="mono">2 встречи</span>', "Intro + первые 2 сессии."]
    note: "Решение за Merkazim — обсуждаем на встрече."

  - layout: quote
    eyebrow: "definition"
    headline: 'What is a <span class="accent">Personal OS</span>?'
    quote_html: 'not a tool — an operating system.<br>...<div class="quote-source">// working definition · 2026</div>'
    bullets:
      - { text: "consistent output regardless of mood", sym: "-->" }

  - layout: divider
    eyebrow: "// 03 · темы пилота"
    headline: 'Четыре трека <span class="dim">+</span><br><span class="accent">расширенный intro.</span>'

  - layout: final
    eyebrow: "principle 01"
    headline: 'start with one skill.<br><span class="accent">iterate daily.</span>'
    subline: 'systems compound. clarity compounds. <span class="accent2">start now.</span>'
    cursor: true
```

`{{ field }}` for plain text, `{{ field | safe }}` for fields containing color-utility spans (`headline`, `body_html`, `left_html`, `right_html`, `quote_html`, `code_html`, `table_rows[][]`).

---

## Forbidden patterns

For modular profile guard tests (`test_r2a_legacy_fidelity.py`):

- ❌ External CSS/JS files (decks must be single-file HTML — entire CSS+JS inline in `<style>`/`<script>`)
- ❌ `<header>`, `<nav>`, `<footer>` landmarks (deck has no semantic site nav)
- ❌ `cursor: crosshair` (terminal-deck does not use crosshair cursor unlike graphs/PFAD-style profiles — terminal is monospace-text-cursor only)
- ❌ Mermaid diagrams (not used in either golden; if needed in future deck, separate slide layout)
- ❌ Emojis in headlines/labels (use color utility classes per SKILL.md)
- ❌ `border-radius` on slide containers (must be sharp; only on cards/stats/badges where source uses it)
- ❌ Mobile reflow rules in deck profile CSS — mobile deck UX is deferred to #92; R2a must not invent mobile-specific layouts. (Mobile screenshots remain required as baseline for #92.)
- ❌ `--font-display` / `--font-body` distinction — terminal deck uses single mono font for everything

---

## Out of scope (deferred)

- Mobile slide UX strategy → tracked in #92 (decide separately, apply to all decks)
- `amber` / `cyan` palette variants for deck (terminal-landing palettes; not used in either deck golden)
- Print/PDF export
- External image assets (decks reference no images in either golden — both purely typographic)
- Dark/light theme toggle (terminal is dark-only)

---

## Reference

- R1 design-system pattern: `docs/visual-regression/2026-05-04-r1/h2t-graphs-design-system.md`
- Skill contract: `pos-sprint-deck-SKILL.md` (in this folder)
- Acceptance gate rule: #92 (deck recovery is desktop-first)
