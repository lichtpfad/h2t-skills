---
name: h2t-creative:design
description: "This skill should be used when the user wants to generate dashboards, presentations, or interfaces in HUD tactical style with tactical dashboard aesthetic: monochrome + red accent, bracket tags, canvas animations, cursor reticle. Triggers: 'h2t-design', 'HUD design', 'tactical dashboard', 'design system', 'h2t-creative:design'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# PFAD Design System

## When to use
- Generating new PFAD-styled dashboards or pages
- Creating presentations in PFAD aesthetic
- Applying HUD design to other DOR interfaces
- Onboarding new panels / modules into the PFAD dashboard

---

## Design Tokens

Extract verbatim from `src/pfad-extension/style.css :root`. Copy-paste into any new page:

```css
:root {
  --bg:        #0c0c0c;
  --bg-card:   #111111;
  --fg:        #eeeeee;
  --fg-dim:    #6e6e6e;
  --fg-muted:  #444444;
  --red:       #d63030;
  --red-dim:   rgba(214,48,48,0.4);
  --red-glow:  rgba(214,48,48,0.18);
  --border:    rgba(255,255,255,0.10);
  --grid-line: rgba(255,255,255,0.045);

  /* Domain colors — override via JS from API, or set directly */
  --c-dev:      #4A94FF;
  --c-art:      #BB6EFF;
  --c-photo:    #FFB020;
  --c-h2t:      #1DD9A0;
  --c-learn:    #12D4E8;
  --c-admin:    #8A919A;
  --c-personal: #B0B8C4;

  --font: 'JetBrains Mono', 'IBM Plex Mono', monospace;
}
```

---

## Typography

### Font faces

```css
@font-face {
  font-family: 'JetBrains Mono';
  src: url('fonts/JetBrainsMono-Light.woff2') format('woff2');
  font-weight: 300;
  font-display: swap;
}
@font-face {
  font-family: 'JetBrains Mono';
  src: url('fonts/JetBrainsMono-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}
@font-face {
  font-family: 'JetBrains Mono';
  src: url('fonts/JetBrainsMono-Medium.woff2') format('woff2');
  font-weight: 500;
  font-display: swap;
}
@font-face {
  font-family: 'IBM Plex Mono';
  src: url('fonts/IBMPlexMono-Light.woff2') format('woff2');
  font-weight: 300;
  font-display: swap;
}
@font-face {
  font-family: 'IBM Plex Mono';
  src: url('fonts/IBMPlexMono-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}
```

Fonts ship in `src/pfad-extension/fonts/`. For standalone pages, either copy the woff2 files or swap in CDN URLs.

### Type Scale

| Role | Size | Weight | Class/element |
|------|------|--------|---------------|
| Clock / hero number | 44px | 300 | `.clock` |
| Body / task text | 12px | 400 | `body` |
| Secondary / schedule | 11px | 400 | `.sched-item` |
| Small / email, icon-btn | 10px | 400 | `.email-item`, `.icon-btn` |
| Micro labels | 8px | 400 | `.card-label`, `.date-display`, `.email-sender` |
| Nano / tag-sm | 7.5px | 400 | `.tag-sm`, `.ptag` |
| Timeline hours, status bar | 7px–8px | 400 | `.timeline-hours`, `.status-bar` |

All numeric contexts should use `font-variant-numeric: tabular-nums` (utility class `.tabnum`).

```css
body {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  color: var(--fg);
  background: var(--bg);
  cursor: crosshair; /* fallback before reticle JS loads */
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

.tabnum { font-variant-numeric: tabular-nums; }
```

---

## Components

### Corner Bracket Tags

Used in filter bar and inline task labels. Four L-shaped CSS corners drawn via `::before`/`::after` on the tag and a child `.corner-b` helper span.

**HTML template:**

```html
<button class="tag domain-dev active">
  DEV
  <span class="corner-b"></span>
</button>
```

**CSS:**

```css
.tag {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 10px;
  font-size: 8px;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--tag-color, var(--fg-dim));
  cursor: none;
  transition: all 0.2s;
}

/* Four L-shaped corners */
.tag::before, .tag::after,
.tag .corner-b::before, .tag .corner-b::after {
  content: '';
  position: absolute;
  width: 5px;
  height: 5px;
  border-color: var(--tag-color, var(--fg-dim));
  transition: all 0.2s;
}
.tag::before        { top: 0; left: 0; border-top: 1px solid; border-left: 1px solid; }
.tag::after         { top: 0; right: 0; border-top: 1px solid; border-right: 1px solid; }
.tag .corner-b::before { bottom: 0; left: 0; border-bottom: 1px solid; border-left: 1px solid; position: absolute; }
.tag .corner-b::after  { bottom: 0; right: 0; border-bottom: 1px solid; border-right: 1px solid; position: absolute; }

.tag .corner-b {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

/* Hover: expand corners */
.tag:hover::before, .tag:hover::after,
.tag:hover .corner-b::before, .tag:hover .corner-b::after {
  width: 8px;
  height: 8px;
}

/* Active: corners expand to fill full edge */
.tag.active {
  background: color-mix(in srgb, var(--tag-color, var(--fg-dim)) 10%, transparent);
}
.tag.active::before, .tag.active::after,
.tag.active .corner-b::before, .tag.active .corner-b::after {
  width: 100%;
  height: 100%;
}

/* Inactive (dimmed when a different filter is active) */
.tag.dimmed {
  opacity: 0.3;
}

/* Small inline variant — used inside task items */
.tag-sm {
  position: relative;
  display: inline-block;
  padding: 1px 6px;
  font-size: 7.5px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--tag-color, var(--fg-dim));
}
.tag-sm::before, .tag-sm::after {
  content: '';
  position: absolute;
  width: 3px;
  height: 3px;
  border-color: var(--tag-color, var(--fg-dim));
}
.tag-sm::before { top: 0; left: 0; border-top: 1px solid; border-left: 1px solid; }
.tag-sm::after  { bottom: 0; right: 0; border-bottom: 1px solid; border-right: 1px solid; }

/* Project sub-label below tag-sm */
.ptag {
  font-size: 7.5px;
  font-weight: 400;
  text-transform: lowercase;
  letter-spacing: 0.08em;
  color: var(--fg-dim);
  margin-top: 1px;
}
```

**Domain color binding** — inject a `<style>` tag at runtime (or statically):

```css
.domain-dev   { --tag-color: var(--c-dev);   color: var(--c-dev); }
.domain-art   { --tag-color: var(--c-art);   color: var(--c-art); }
.domain-photo { --tag-color: var(--c-photo); color: var(--c-photo); }
```

---

### Card

The fundamental container. Background `--bg-card`, 1px border, no radius. On hover: border brightens and a red sweep line animates across the top edge.

**HTML template:**

```html
<section class="card" data-module="my-module" data-label="MY MODULE">
  <div class="card-label">
    My Module
    <div class="card-header-actions">
      <button class="icon-btn" title="Refresh">&#x21BA;</button>
      <button class="vis-btn" data-module="my-module">&#x25C9;</button>
    </div>
  </div>
  <!-- card body content here -->
</section>
```

**CSS:**

```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 16px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s;
}

.card:hover {
  border-color: rgba(255,255,255,0.16);
}

/* Red sweep line on hover */
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 0;
  height: 1px;
  background: var(--red);
  transition: width 0.5s ease;
  z-index: 1;
}
.card:hover::before {
  width: 100%;
}

/* Card label — uppercase micro text with :: prefix */
.card-label {
  font-size: 8px;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--fg-dim);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-label::before {
  content: ':: ';
}

.card-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Loading state (animated width bar) */
.card-loading {
  height: 1px;
  background: var(--red-dim);
  animation: pulse-width 1.5s ease-in-out infinite;
}
@keyframes pulse-width {
  0%, 100% { width: 20%; }
  50%       { width: 80%; }
}

/* Empty state */
.card-empty {
  font-size: 8px;
  color: var(--fg-muted);
  letter-spacing: 0.05em;
}

/* Icon buttons inside card header */
.icon-btn {
  font-size: 10px;
  color: var(--fg-muted);
  padding: 2px 4px;
  transition: color 0.2s;
}
.icon-btn:hover { color: var(--fg-dim); }

/* Module visibility toggle button */
.vis-btn {
  font-size: 8px;
  opacity: 0.3;
  transition: opacity 0.2s;
}
.vis-btn:hover { opacity: 1; }
```

---

### Timeline Bar

Horizontal time bar showing 06:00–22:00 with event blocks and a live NOW marker.

**HTML template:**

```html
<div class="timeline" id="timeline">
  <div class="timeline-hours" id="timeline-hours"></div>
  <div class="timeline-bar" id="timeline-bar"></div>
</div>
```

**CSS:**

```css
.timeline {
  position: relative;
  height: 34px;
  margin: 0 20px;
  border-bottom: 1px solid var(--border);
  z-index: 10;
}

.timeline-hours {
  display: flex;
  justify-content: space-between;
  padding: 0 2px;
  font-size: 7px;
  color: var(--fg-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.timeline-bar {
  position: relative;
  height: 14px;
  margin-top: 2px;
}

.timeline-event {
  position: absolute;
  height: 100%;
  border-radius: 0;
}
.timeline-event.mtg {
  background: rgba(214,48,48,0.15);
  border-left: 1px solid var(--red-dim);
}
.timeline-event.wrk {
  background: rgba(255,255,255,0.06);
  border-left: 1px solid var(--border);
}

.timeline-now {
  position: absolute;
  top: -4px;
  width: 2px;
  height: calc(100% + 8px);
  background: var(--red);
  box-shadow: 0 0 8px var(--red), 0 0 16px var(--red-glow);
  z-index: 2;
}
.timeline-now-label {
  position: absolute;
  top: -14px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 7px;
  color: var(--red);
  letter-spacing: 0.1em;
  white-space: nowrap;
}
```

**JS — `renderTimeline(events)`:**

```js
// events: [{time: "HH:MM", title: "...", type: "meeting"|"focus"|"break"}]
function renderTimeline(events = []) {
  const hoursEl = document.getElementById('timeline-hours');
  const barEl   = document.getElementById('timeline-bar');
  if (!hoursEl || !barEl) return;

  // Hour markers 06–22
  hoursEl.innerHTML = '';
  for (let h = 6; h <= 22; h++) {
    const span = document.createElement('span');
    span.textContent = String(h).padStart(2, '0');
    hoursEl.appendChild(span);
  }

  // Event blocks
  barEl.innerHTML = '';
  const startH = 6, endH = 22, range = endH - startH;

  events.forEach(item => {
    if (!item.time) return;
    const [hh, mm] = item.time.split(':').map(Number);
    const pos   = ((hh + mm / 60) - startH) / range * 100;
    const width = 30 / 60 / range * 100; // 30min default block

    if (pos < 0 || pos > 100) return;

    const block = document.createElement('div');
    block.className = 'timeline-event ' + (item.type === 'meeting' ? 'mtg' : 'wrk');
    block.style.left  = pos + '%';
    block.style.width = Math.min(width, 100 - pos) + '%';
    block.title = item.title || item.type;
    barEl.appendChild(block);
  });

  // NOW marker
  const now  = new Date();
  const nowH = now.getHours() + now.getMinutes() / 60;
  const nowPos = ((nowH - startH) / range) * 100;
  if (nowPos >= 0 && nowPos <= 100) {
    const marker = document.createElement('div');
    marker.className = 'timeline-now';
    marker.style.left = nowPos + '%';
    const label = document.createElement('span');
    label.className   = 'timeline-now-label';
    label.textContent = 'NOW';
    marker.appendChild(label);
    barEl.appendChild(marker);
  }
}
```

---

### Task Item

```html
<li class="task-item" data-id="abc123">
  <div class="task-check"></div>
  <div class="task-tags">
    <span class="tag-sm domain-dev">DEV</span>
    <span class="ptag">pfad</span>
  </div>
  <span class="task-text">Implement new feature</span>
  <span class="task-due tabnum urgent">today</span>
  <span class="task-delete">×</span>
</li>
```

**CSS:**

```css
.task-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow-y: auto;
  flex: 1;
}

.task-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 4px;
  transition: background 0.15s;
}
.task-item:hover {
  background: rgba(255,255,255,0.03);
}

.task-check {
  width: 10px;
  height: 10px;
  border: 1px solid var(--fg-muted);
  flex-shrink: 0;
  margin-top: 2px;
  cursor: none;
  transition: all 0.15s;
}
.task-check:hover { border-color: var(--fg-dim); }
.task-check.done  { background: var(--fg-muted); border-color: var(--fg-muted); }

.task-tags {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-width: 48px;
}

.task-text {
  flex: 1;
  font-size: 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.task-text.done {
  text-decoration: line-through;
  color: var(--fg-muted);
}

.task-due {
  font-size: 8px;
  color: var(--fg-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  flex-shrink: 0;
}
.task-due.urgent { color: var(--red); }

.task-delete {
  font-size: 8px;
  color: var(--fg-muted);
  opacity: 0;
  transition: opacity 0.15s;
  padding: 0 2px;
}
.task-item:hover .task-delete { opacity: 1; }
.task-delete:hover { color: var(--red); }
```

---

### Status Bar

Footer bar: version / location / date. Fixed height 22px.

**HTML template:**

```html
<div class="status-bar">
  <span class="status-left">
    <span class="status-pfad">PFAD</span> // tactical focus dashboard
  </span>
  <span class="status-center tabnum">52.5200°N 13.4050°E</span>
  <span class="status-right tabnum">v3.0 // <span id="status-date"></span></span>
</div>
```

**CSS:**

```css
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 22px;
  padding: 0 20px;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
  font-size: 8px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--fg-muted);
  z-index: 10;
  flex-shrink: 0;
}

.status-pfad    { color: var(--red); }
.status-offline { color: var(--red); margin-left: 8px; }
```

---

## Micro-Animations

### Radar

Pure CSS rotating sweep line with a grid background and a center red dot.

**HTML:**

```html
<div class="radar-container">
  <div class="radar-sweep"></div>
  <div class="radar-grid"></div>
</div>
```

**CSS:**

```css
.radar-container {
  position: relative;
  width: 44px;
  height: 44px;
  margin: auto;
}

.radar-grid {
  position: absolute;
  inset: 0;
  border: 1px solid var(--border);
  background:
    linear-gradient(var(--border) 1px, transparent 1px) center / 50% 50%,
    linear-gradient(90deg, var(--border) 1px, transparent 1px) center / 50% 50%;
}
.radar-grid::before {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  width: 1px; height: 1px;
  background: var(--red);
  box-shadow: 0 0 4px var(--red);
}

.radar-sweep {
  position: absolute;
  top: 50%; left: 50%;
  width: 22px;
  height: 1px;
  background: linear-gradient(90deg, var(--red), transparent);
  transform-origin: 0 0;
  animation: radar-rotate 3s linear infinite;
}
@keyframes radar-rotate {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
```

---

### Waveform

10 bars with staggered CSS animation delays (0.12s per bar). JS creates bars dynamically.

**HTML:**

```html
<div class="waveform-bars" id="waveform-bars"></div>
```

**CSS:**

```css
.waveform-bars {
  display: flex;
  gap: 2px;
  align-items: flex-end;
  height: 24px;
}
.waveform-bar {
  width: 3px;
  background: var(--red-dim);
  animation: waveform-pulse 1.2s ease-in-out infinite;
}
@keyframes waveform-pulse {
  0%, 100% { height: 4px; }
  50%       { height: 20px; }
}
```

**JS — `initWaveform()`:**

```js
function initWaveform() {
  const container = document.getElementById('waveform-bars');
  if (!container) return;
  for (let i = 0; i < 10; i++) {
    const bar = document.createElement('div');
    bar.className = 'waveform-bar';
    bar.style.animationDelay = (i * 0.12) + 's';
    container.appendChild(bar);
  }
}
```

---

### Oscilloscope

Canvas-based sine wave with glow effect. Auto-resizes to parent width.

**HTML:**

```html
<canvas id="oscilloscope" class="oscilloscope-canvas"></canvas>
```

**CSS:**

```css
.oscilloscope-canvas {
  width: 100%;
  height: 36px;
  display: block;
}
```

**JS — `initOscilloscope()`:**

```js
function initOscilloscope() {
  const canvas = document.getElementById('oscilloscope');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let offset = 0;
  let animId = null;

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width  = rect.width;
    canvas.height = 36;
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const mid = canvas.height / 2;
    const amp = mid * 0.6;

    ctx.beginPath();
    ctx.moveTo(0, mid);
    for (let x = 0; x < canvas.width; x++) {
      const y = mid + Math.sin((x + offset) * 0.04) * amp * Math.sin((x + offset) * 0.008);
      ctx.lineTo(x, y);
    }
    ctx.save();
    ctx.strokeStyle  = 'rgba(214, 48, 48, 0.5)';
    ctx.lineWidth    = 1;
    ctx.shadowColor  = 'rgba(214, 48, 48, 0.3)';
    ctx.shadowBlur   = 6;
    ctx.stroke();
    ctx.restore();

    offset = (offset + 1.5) % 10000;
    animId = requestAnimationFrame(draw);
  }

  resize();
  draw();

  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(animId); animId = null; }
    else if (!animId) { draw(); }
  });
}
```

---

### Scanner

Vertical red line that sweeps from top to bottom, repeating. Pure CSS.

**HTML:**

```html
<div class="cell-scanner">
  <div class="card-label">Trace</div>
  <div class="scanner-line"></div>
</div>
```

**CSS:**

```css
.cell-scanner {
  position: relative;
  overflow: hidden;
}

.scanner-line {
  position: absolute;
  left: 0;
  width: 100%;
  height: 1px;
  background: var(--red-dim);
  box-shadow: 0 0 6px var(--red-glow);
  animation: scanner-sweep 2.5s ease-in-out infinite;
}
@keyframes scanner-sweep {
  0%   { top: 0; }
  100% { top: 100%; }
}
```

---

## Overlay Layers

Layers stack in z-index order: Dot Field (0) → Grid (1) → Corner Marks (2) → Coordinates (3) → Dashboard content (10) → Scanlines (9998) → Reticle (99999).

### Dot Field

Full-viewport canvas with 50 slowly drifting dots connected by faint red lines when close.

**HTML:**

```html
<canvas id="dot-field" class="overlay-dot-field"></canvas>
```

**CSS:**

```css
.overlay-dot-field {
  position: fixed;
  inset: 0;
  z-index: 0;
  opacity: 0.5;
  pointer-events: none;
}
```

**JS — `initDotField()`:**

```js
function initDotField() {
  const canvas = document.getElementById('dot-field');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const DOT_COUNT = 50;
  const MAX_DIST  = 120;
  let dots   = [];
  let animId = null;

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function createDots() {
    dots = [];
    for (let i = 0; i < DOT_COUNT; i++) {
      dots.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12,
        size:  Math.random() < 0.5 ? 1 : 2,
        alpha: 0.03 + Math.random() * 0.21,
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Move dots, wrap at edges
    dots.forEach(d => {
      d.x += d.vx; d.y += d.vy;
      if (d.x < 0) d.x = canvas.width;
      if (d.x > canvas.width)  d.x = 0;
      if (d.y < 0) d.y = canvas.height;
      if (d.y > canvas.height) d.y = 0;
    });

    // Connection lines
    for (let i = 0; i < dots.length; i++) {
      for (let j = i + 1; j < dots.length; j++) {
        const dx   = dots[i].x - dots[j].x;
        const dy   = dots[i].y - dots[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MAX_DIST) {
          ctx.beginPath();
          ctx.moveTo(dots[i].x, dots[i].y);
          ctx.lineTo(dots[j].x, dots[j].y);
          ctx.strokeStyle = `rgba(214, 48, 48, ${0.06 * (1 - dist / MAX_DIST)})`;
          ctx.lineWidth   = 0.5;
          ctx.stroke();
        }
      }
    }

    // Dots (sharp pixel rects)
    dots.forEach(d => {
      ctx.fillStyle = `rgba(214, 48, 48, ${d.alpha})`;
      ctx.fillRect(Math.round(d.x), Math.round(d.y), d.size, d.size);
    });

    animId = requestAnimationFrame(draw);
  }

  resize();
  createDots();
  draw();

  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(animId); animId = null; }
    else if (!animId)    { draw(); }
  });
}
```

---

### Grid Background

60px CSS grid drawn with `linear-gradient`.

```html
<div class="overlay-grid"></div>
```

```css
.overlay-grid {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background-image:
    linear-gradient(var(--grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 60px 60px;
}
```

---

### Scanlines

CRT scanlines overlay at top z-index (under reticle only).

```html
<div class="overlay-scanlines"></div>
```

```css
.overlay-scanlines {
  position: fixed;
  inset: 0;
  z-index: 9998;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 1px,
    rgba(255,255,255,0.04) 1px,
    rgba(255,255,255,0.04) 2px
  );
}
```

---

### Corner Marks + Coordinates

Four L-shaped corner marks at viewport edges. Coordinate labels sit 20px below them.

**HTML:**

```html
<!-- Corner marks -->
<div class="corner-mark corner-tl"></div>
<div class="corner-mark corner-tr"></div>
<div class="corner-mark corner-bl"></div>
<div class="corner-mark corner-br"></div>

<!-- Coordinate labels -->
<div class="coord-mark coord-tl">52.5200°N</div>
<div class="coord-mark coord-tr">13.4050°E</div>
<div class="coord-mark coord-bl">PFAD v3.0</div>
<div class="coord-mark coord-br" id="sys-date"></div>
```

**CSS:**

```css
.corner-mark {
  position: fixed;
  width: 16px;
  height: 16px;
  z-index: 2;
  pointer-events: none;
}
.corner-tl { top: 36px;    left: 36px;  border-top: 1px solid var(--fg-muted); border-left: 1px solid var(--fg-muted); }
.corner-tr { top: 36px;    right: 36px; border-top: 1px solid var(--fg-muted); border-right: 1px solid var(--fg-muted); }
.corner-bl { bottom: 36px; left: 36px;  border-bottom: 1px solid var(--fg-muted); border-left: 1px solid var(--fg-muted); }
.corner-br { bottom: 36px; right: 36px; border-bottom: 1px solid var(--fg-muted); border-right: 1px solid var(--fg-muted); }

.coord-mark {
  position: fixed;
  z-index: 3;
  font-size: 8px;
  color: var(--fg-muted);
  letter-spacing: 0.12em;
  pointer-events: none;
}
.coord-tl { top: 56px;    left: 36px; }
.coord-tr { top: 56px;    right: 36px; text-align: right; }
.coord-bl { bottom: 56px; left: 36px; }
.coord-br { bottom: 56px; right: 36px; text-align: right; }
```

---

## Cursor Reticle

Custom crosshair: two lines (h/v) with a 8px gap at center, four corner brackets, pixel coordinate display, and a label that fades in when hovering over `[data-label]` elements. Follows mouse with lerp (factor 0.35).

**HTML:**

```html
<div class="reticle" id="reticle">
  <div class="reticle-h"></div>
  <div class="reticle-v"></div>
  <div class="reticle-corner rc-tl"></div>
  <div class="reticle-corner rc-tr"></div>
  <div class="reticle-corner rc-bl"></div>
  <div class="reticle-corner rc-br"></div>
  <div class="reticle-coords" id="reticle-coords"></div>
  <div class="reticle-label"  id="reticle-label"></div>
</div>
```

**CSS:**

```css
.reticle {
  position: fixed;
  z-index: 99999;
  pointer-events: none;
  will-change: transform;
}

.reticle-h, .reticle-v {
  position: absolute;
  background: rgba(255,255,255,0.5);
}
.reticle-h {
  width: 32px; height: 1px;
  top: 0; left: -16px;
  /* 8px gap in center */
  clip-path: polygon(0 0, calc(50% - 4px) 0, calc(50% - 4px) 100%, 0 100%,
                      0 0, calc(50% + 4px) 0, 100% 0, 100% 100%, calc(50% + 4px) 100%);
}
.reticle-v {
  width: 1px; height: 32px;
  top: -16px; left: 0;
  clip-path: polygon(0 0, 100% 0, 100% calc(50% - 4px), 0 calc(50% - 4px),
                      0 calc(50% + 4px), 100% calc(50% + 4px), 100% 100%, 0 100%);
}

.reticle-corner {
  position: absolute;
  width: 6px; height: 6px;
  border-color: rgba(255,255,255,0.7);
  transition: all 0.15s;
}
.rc-tl { top: -20px;    left: -20px;  border-top: 1px solid; border-left: 1px solid; }
.rc-tr { top: -20px;    right: -20px; border-top: 1px solid; border-right: 1px solid; }
.rc-bl { bottom: -20px; left: -20px;  border-bottom: 1px solid; border-left: 1px solid; }
.rc-br { bottom: -20px; right: -20px; border-bottom: 1px solid; border-right: 1px solid; }

/* Hover state: corners expand */
.reticle.hovering .reticle-corner { width: 10px; height: 10px; }

/* Click flash: white corners */
.reticle.clicking .reticle-corner { border-color: white; }

.reticle-coords {
  position: absolute;
  top: 8px; left: 24px;
  font-size: 8px;
  color: var(--fg-muted);
  letter-spacing: 0.1em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.reticle-label {
  position: absolute;
  bottom: 8px; left: 24px;
  font-size: 7.5px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--red);
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.15s;
}
.reticle.hovering .reticle-label { opacity: 1; }
```

**JS — `initReticle()`:**

```js
function initReticle() {
  const el       = document.getElementById('reticle');
  const coordsEl = document.getElementById('reticle-coords');
  const labelEl  = document.getElementById('reticle-label');
  if (!el) return;

  let mx = 0, my = 0;   // actual mouse pos
  let rx = 0, ry = 0;   // lerped reticle pos
  let hoveredLabel = '';
  let animId = null;
  const LERP = 0.35;

  function update() {
    rx += (mx - rx) * LERP;
    ry += (my - ry) * LERP;
    el.style.transform = `translate(${rx}px, ${ry}px)`;

    if (coordsEl) {
      const cx = Math.max(0, Math.round(rx));
      const cy = Math.max(0, Math.round(ry));
      coordsEl.textContent = `${String(cx).padStart(4,'0')} : ${String(cy).padStart(4,'0')}`;
    }

    // Read data-label from element under cursor
    const target  = document.elementFromPoint(mx, my);
    const labeled = target?.closest('[data-label]');
    const newLabel = labeled?.dataset.label || '';
    if (newLabel !== hoveredLabel) {
      hoveredLabel = newLabel;
      if (labelEl) labelEl.textContent = hoveredLabel;
      el.classList.toggle('hovering', !!hoveredLabel);
    }

    animId = requestAnimationFrame(update);
  }

  // Hide native cursor
  document.body.style.cursor = 'none';
  document.querySelectorAll('button, a, input, textarea, select').forEach(elem => {
    elem.style.cursor = 'none';
  });

  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  document.addEventListener('mousedown', () => {
    el.classList.add('clicking');
    setTimeout(() => el.classList.remove('clicking'), 150);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(animId); animId = null; }
    else if (!animId)    { update(); }
  });

  update();
}
```

---

## Usage Example

Minimal complete PFAD-styled page — all layers, tokens, animations. Replace `<!-- CONTENT -->` with cards or custom modules.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MY PFAD PAGE</title>
  <style>
    /* ── Tokens ── */
    :root {
      --bg: #0c0c0c; --bg-card: #111111;
      --fg: #eeeeee; --fg-dim: #6e6e6e; --fg-muted: #444444;
      --red: #d63030; --red-dim: rgba(214,48,48,0.4); --red-glow: rgba(214,48,48,0.18);
      --border: rgba(255,255,255,0.10); --grid-line: rgba(255,255,255,0.045);
      --font: 'JetBrains Mono', 'IBM Plex Mono', monospace;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font); font-size: 12px; color: var(--fg);
      background: var(--bg); overflow: hidden; cursor: crosshair;
      -webkit-font-smoothing: antialiased;
    }

    /* ── Overlay layers ── */
    .overlay-dot-field  { position: fixed; inset: 0; z-index: 0; opacity: 0.5; pointer-events: none; }
    .overlay-grid       { position: fixed; inset: 0; z-index: 1; pointer-events: none;
      background-image: linear-gradient(var(--grid-line) 1px, transparent 1px),
                        linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
      background-size: 60px 60px; }
    .overlay-scanlines  { position: fixed; inset: 0; z-index: 9998; pointer-events: none;
      background: repeating-linear-gradient(0deg, transparent, transparent 1px,
        rgba(255,255,255,0.04) 1px, rgba(255,255,255,0.04) 2px); }

    /* ── Corner marks ── */
    .corner-mark { position: fixed; width: 16px; height: 16px; z-index: 2; pointer-events: none; }
    .corner-tl { top: 36px; left: 36px; border-top: 1px solid var(--fg-muted); border-left: 1px solid var(--fg-muted); }
    .corner-tr { top: 36px; right: 36px; border-top: 1px solid var(--fg-muted); border-right: 1px solid var(--fg-muted); }
    .corner-bl { bottom: 36px; left: 36px; border-bottom: 1px solid var(--fg-muted); border-left: 1px solid var(--fg-muted); }
    .corner-br { bottom: 36px; right: 36px; border-bottom: 1px solid var(--fg-muted); border-right: 1px solid var(--fg-muted); }
    .coord-mark { position: fixed; z-index: 3; font-size: 8px; color: var(--fg-muted); letter-spacing: 0.12em; pointer-events: none; }
    .coord-tl { top: 56px; left: 36px; } .coord-tr { top: 56px; right: 36px; text-align: right; }
    .coord-bl { bottom: 56px; left: 36px; } .coord-br { bottom: 56px; right: 36px; text-align: right; }

    /* ── Reticle ── */
    .reticle { position: fixed; z-index: 99999; pointer-events: none; will-change: transform; }
    .reticle-h, .reticle-v { position: absolute; background: rgba(255,255,255,0.5); }
    .reticle-h { width: 32px; height: 1px; top: 0; left: -16px;
      clip-path: polygon(0 0, calc(50% - 4px) 0, calc(50% - 4px) 100%, 0 100%,
        0 0, calc(50% + 4px) 0, 100% 0, 100% 100%, calc(50% + 4px) 100%); }
    .reticle-v { width: 1px; height: 32px; top: -16px; left: 0;
      clip-path: polygon(0 0, 100% 0, 100% calc(50% - 4px), 0 calc(50% - 4px),
        0 calc(50% + 4px), 100% calc(50% + 4px), 100% 100%, 0 100%); }
    .reticle-corner { position: absolute; width: 6px; height: 6px; border-color: rgba(255,255,255,0.7); transition: all 0.15s; }
    .rc-tl { top: -20px; left: -20px; border-top: 1px solid; border-left: 1px solid; }
    .rc-tr { top: -20px; right: -20px; border-top: 1px solid; border-right: 1px solid; }
    .rc-bl { bottom: -20px; left: -20px; border-bottom: 1px solid; border-left: 1px solid; }
    .rc-br { bottom: -20px; right: -20px; border-bottom: 1px solid; border-right: 1px solid; }
    .reticle.hovering .reticle-corner { width: 10px; height: 10px; }
    .reticle-coords { position: absolute; top: 8px; left: 24px; font-size: 8px;
      color: var(--fg-muted); letter-spacing: 0.1em; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .reticle-label { position: absolute; bottom: 8px; left: 24px; font-size: 7.5px;
      text-transform: uppercase; letter-spacing: 0.12em; color: var(--red);
      white-space: nowrap; opacity: 0; transition: opacity 0.15s; }
    .reticle.hovering .reticle-label { opacity: 1; }

    /* ── Card ── */
    .card { background: var(--bg-card); border: 1px solid var(--border); padding: 16px;
      position: relative; overflow: hidden; display: flex; flex-direction: column; transition: border-color 0.2s; }
    .card:hover { border-color: rgba(255,255,255,0.16); }
    .card::before { content: ''; position: absolute; top: 0; left: 0; width: 0; height: 1px;
      background: var(--red); transition: width 0.5s ease; z-index: 1; }
    .card:hover::before { width: 100%; }
    .card-label { font-size: 8px; text-transform: uppercase; letter-spacing: 0.18em;
      color: var(--fg-dim); margin-bottom: 8px; }
    .card-label::before { content: ':: '; }

    /* ── Page layout ── */
    .page { display: flex; flex-direction: column; height: 100vh; width: 100vw;
      padding: 20px; gap: 2px; z-index: 10; position: relative; }

    /* ── Status bar ── */
    .status-bar { display: flex; justify-content: space-between; align-items: center;
      height: 22px; padding: 0 20px; background: var(--bg-card);
      border-top: 1px solid var(--border); font-size: 8px; text-transform: uppercase;
      letter-spacing: 0.10em; color: var(--fg-muted); z-index: 10; flex-shrink: 0; }
    .status-pfad { color: var(--red); }
  </style>
</head>
<body>

  <!-- Overlay: Dot Field -->
  <canvas id="dot-field" class="overlay-dot-field"></canvas>

  <!-- Overlay: Grid -->
  <div class="overlay-grid"></div>

  <!-- Corner marks -->
  <div class="corner-mark corner-tl"></div>
  <div class="corner-mark corner-tr"></div>
  <div class="corner-mark corner-bl"></div>
  <div class="corner-mark corner-br"></div>

  <!-- Coordinates -->
  <div class="coord-mark coord-tl">52.5200°N</div>
  <div class="coord-mark coord-tr">13.4050°E</div>
  <div class="coord-mark coord-bl">MY PAGE v1.0</div>
  <div class="coord-mark coord-br" id="sys-date"></div>

  <!-- Page content -->
  <div class="page">
    <!-- CONTENT -->
    <section class="card" data-label="EXAMPLE">
      <div class="card-label">Example Card</div>
      <p style="font-size:11px; color: var(--fg-dim);">Content goes here.</p>
    </section>

    <!-- Status bar -->
    <div class="status-bar" style="margin-top:auto;">
      <span><span class="status-pfad">PFAD</span> // my page</span>
      <span id="status-date"></span>
    </div>
  </div>

  <!-- Scanlines -->
  <div class="overlay-scanlines"></div>

  <!-- Reticle -->
  <div class="reticle" id="reticle">
    <div class="reticle-h"></div>
    <div class="reticle-v"></div>
    <div class="reticle-corner rc-tl"></div>
    <div class="reticle-corner rc-tr"></div>
    <div class="reticle-corner rc-bl"></div>
    <div class="reticle-corner rc-br"></div>
    <div class="reticle-coords" id="reticle-coords"></div>
    <div class="reticle-label"  id="reticle-label"></div>
  </div>

  <script>
    // Date display
    function dateKey() {
      const d = new Date();
      return [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-');
    }
    document.getElementById('sys-date').textContent    = dateKey();
    document.getElementById('status-date').textContent = dateKey();

    // Paste initDotField() here (see Dot Field section above)
    // Paste initReticle()  here (see Cursor Reticle section above)

    document.addEventListener('DOMContentLoaded', () => {
      initDotField();
      initReticle();
    });
  </script>

</body>
</html>
```

---

## Notes for agents

- `data-label="CARD NAME"` on any element makes the reticle label appear on hover — add it to all interactive regions.
- All buttons and links should NOT have `cursor: pointer`. The reticle script sets `cursor: none` on everything after `initReticle()` runs. Use `cursor: crosshair` as CSS fallback.
- Domain color classes (`domain-dev`, `domain-art`, etc.) drive `--tag-color` via CSS custom property inheritance. Inject `injectDomainCSS()` or add static CSS to apply them.
- For visibility toggle: add `data-module="module-id"` to cards and use `.module-hidden { display: none !important; }`.
- All canvas animations pause on `visibilitychange` (tab hidden) — copy the pattern from initDotField / initOscilloscope.
