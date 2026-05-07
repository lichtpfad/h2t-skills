---
name: deck
description: "HTML presentation generator — 2 styles: terminal (dark, monospace, scanlines) and editorial (light, serif, book-like). Single-file HTML, keyboard navigation, zero dependencies."
version: 1.0
trigger: ["презентация", "deck", "слайды", "presentation", "slide deck", "slides"]
---

# Deck — HTML Presentation Generator

Generate single-file HTML presentations with full design system. Two visual styles. No external dependencies (except Google Fonts). Works offline, keyboard navigation, mobile-friendly.

---

## Step 1 — Choose Style

**ALWAYS ask the user before generating.** Use AskUserQuestion:

```
Which presentation style?

1. terminal — dark background, monospace font, scanline effect, green accent. Hacker aesthetic.
2. editorial — light background, serif headings, book-like typography, warm tones. Magazine aesthetic.
```

After the user picks — apply the matching design system below.

---

## Step 2 — Get Content

Ask what the presentation is about. You need:
- **Topic / title**
- **Slide plan** — even rough ("5 slides about X" is enough)
- **Audience** (optional — helps pick the right tone)

If the user gives just a topic, propose a slide structure yourself (5–15 slides).

---

## Step 3 — Generate

Create a single `index.html` file with ALL CSS and JS inline. No external files needed.

**Requirements for ALL styles:**
- Single-file HTML, all CSS/JS inline
- Google Fonts loaded via `<link>` in `<head>`
- Keyboard navigation (arrows, space, enter, home, end)
- Touch swipe for mobile
- Progress bar at bottom
- Slide counter top-right corner
- Responsive: works on desktop, tablet, mobile
- Smooth transition animations between slides

After generating, tell the user:
```
open index.html
```

---

## STYLE 1: TERMINAL

Dark background. Monospace font. Scanline overlay. Green accent. Terminal/hacker aesthetic.

### CSS Variables

```css
:root {
  --bg: #0d1117;
  --bg-light: #161b22;
  --bg-card: #1c2129;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #55aa88;
  --accent2: #d4a843;
  --accent3: #4488cc;
  --danger: #cc4444;
  --highlight: #9966cc;
  --pop: #ee6688;
  --border: #30363d;
  --font-heading: 'JetBrains Mono','Fira Code','SF Mono','Menlo','Consolas',monospace;
  --font-body: 'JetBrains Mono','Fira Code','SF Mono','Menlo','Consolas',monospace;
}
```

### Google Fonts

```html
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
```

### Typography Rules

```css
h1 {
  font-family: var(--font-heading);
  font-size: 40px;
  font-weight: 700;
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 16px;
  line-height: 1.2;
}

h2 {
  font-family: var(--font-heading);
  font-size: 28px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 20px;
  line-height: 1.3;
}

h3 {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 12px;
}

p, li {
  font-family: var(--font-body);
  font-size: 17px;
  line-height: 1.6;
  color: var(--text);
}
```

**Color classes** (use instead of emojis):

```css
.dim { color: var(--text-dim); }
.accent { color: var(--accent); }     /* green */
.accent2 { color: var(--accent2); }   /* amber */
.accent3 { color: var(--accent3); }   /* blue */
.danger { color: var(--danger); }     /* red */
.highlight { color: var(--highlight); } /* purple */
.pop { color: var(--pop); }           /* pink */
```

### Visual Effects

**Scanline overlay** — subtle horizontal lines over everything:
```css
body::after {
  content: '';
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.03) 2px,
    rgba(0,0,0,0.03) 4px
  );
  pointer-events: none;
  z-index: 9999;
}
```

**Blinking cursor** after headings:
```css
.cursor::after {
  content: '\2588';
  animation: blink 1s step-end infinite;
  color: var(--accent);
  margin-left: 2px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
```

**Fade-up animation** — elements appear from below:
```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.slide.active .slide-inner > * {
  animation: fadeUp 0.5s ease-out both;
}
.slide.active .slide-inner > *:nth-child(2) { animation-delay: 0.08s; }
.slide.active .slide-inner > *:nth-child(3) { animation-delay: 0.16s; }
.slide.active .slide-inner > *:nth-child(4) { animation-delay: 0.24s; }
.slide.active .slide-inner > *:nth-child(5) { animation-delay: 0.32s; }
.slide.active .slide-inner > *:nth-child(6) { animation-delay: 0.40s; }
.slide.active .slide-inner > *:nth-child(7) { animation-delay: 0.48s; }
```

**Card hover** — border lights up:
```css
.card:hover { border-color: var(--accent); }
```

**Progress bar** — thin green bar at bottom:
```css
.progress-bar {
  position: fixed;
  bottom: 0; left: 0;
  height: 3px;
  background: var(--accent);
  transition: width 0.3s;
  z-index: 100;
}
```

---

## STYLE 2: EDITORIAL

Light background. Serif headings. Sans-serif body. Book/magazine aesthetic. Warm tones.

### CSS Variables

```css
:root {
  --bg: #faf9f6;
  --bg-light: #f0eeeb;
  --bg-card: #ffffff;
  --text: #1a1a1a;
  --text-dim: #6b6b6b;
  --accent: #c45a3c;
  --accent2: #2d5f8a;
  --accent3: #5a8a5c;
  --danger: #b33a3a;
  --highlight: #8b6fb0;
  --pop: #c45a3c;
  --border: #e0ddd8;
  --font-heading: 'Playfair Display','Georgia','Times New Roman',serif;
  --font-body: 'Inter','Helvetica Neue','Arial',sans-serif;
}
```

### Google Fonts

```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

### Typography Rules

```css
h1 {
  font-family: var(--font-heading);
  font-size: 44px;
  font-weight: 700;
  color: var(--text);
  /* NO text-transform — normal case, not uppercase */
  margin-bottom: 16px;
  line-height: 1.2;
}

h2 {
  font-family: var(--font-heading);
  font-size: 30px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 20px;
  line-height: 1.3;
}

h3 {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 500;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 12px;
}

p, li {
  font-family: var(--font-body);
  font-size: 18px;
  line-height: 1.7;
  color: var(--text);
}
```

**Emphasis through italics**, not colored spans:
```css
em, .emphasis { font-style: italic; color: var(--accent); }
```

### Visual Effects

**NO overlay** — clean background. No scanlines, no grain.

**Slide-in animation** — elements appear from the left (not from below):
```css
@keyframes slideIn {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}
.slide.active .slide-inner > * {
  animation: slideIn 0.5s ease-out both;
}
.slide.active .slide-inner > *:nth-child(2) { animation-delay: 0.08s; }
.slide.active .slide-inner > *:nth-child(3) { animation-delay: 0.16s; }
.slide.active .slide-inner > *:nth-child(4) { animation-delay: 0.24s; }
.slide.active .slide-inner > *:nth-child(5) { animation-delay: 0.32s; }
.slide.active .slide-inner > *:nth-child(6) { animation-delay: 0.40s; }
.slide.active .slide-inner > *:nth-child(7) { animation-delay: 0.48s; }
```

**Card hover** — shadow grows (not border):
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  transition: box-shadow 0.3s;
}
.card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
```

**Thin rules** between sections:
```css
.slide-inner > h2 {
  border-top: 1px solid var(--border);
  padding-top: 20px;
}
```

**Quotes** — accent border + italic:
```css
.quote {
  border-left: 3px solid var(--accent);
  padding: 16px 24px;
  margin: 16px 0;
  background: transparent;
}
.quote p {
  font-family: var(--font-heading);
  font-style: italic;
  font-size: 20px;
  line-height: 1.6;
}
```

**Code blocks** — light warm background:
```css
.code-block {
  background: #f5f3f0;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 22px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  line-height: 1.7;
}
```

**Progress bar** — thinner, terracotta:
```css
.progress-bar {
  position: fixed;
  bottom: 0; left: 0;
  height: 2px;
  background: var(--accent);
  transition: width 0.3s;
  z-index: 100;
}
```

---

## SHARED: Slide Structure (both styles)

### Base layout

```css
html, body {
  width: 100%; height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 16px;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

.slide {
  display: none;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100vw;
  height: 100vh;
  padding: 56px 80px 80px;
  position: relative;
}
.slide.active { display: flex; }

.slide-inner {
  width: 100%;
  max-width: 1100px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.slide-counter {
  position: absolute;
  top: 24px; right: 32px;
  font-size: 12px;
  color: var(--text-dim);
  opacity: 0.6;
}
```

### Components

**Cards grid:**
```html
<div class="cards">
  <div class="card">
    <h3><span class="accent">Label</span></h3>
    <p>Description text here.</p>
    <span class="tag">tag</span>
  </div>
</div>
```
```css
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  margin-top: 10px;
  background: rgba(85,170,136,0.15);
  color: var(--accent);
}
```

**Code block:**
```html
<div class="code-block">
  <span class="comment"># install dependencies</span><br>
  <span class="accent">npm install</span> <span class="dim">-- installs packages</span>
</div>
```
```css
.code-block {
  background: var(--bg-light);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px 24px;
  font-size: 14px;
  line-height: 1.7;
  margin-top: 16px;
  font-family: 'JetBrains Mono', monospace;
}
.comment { color: var(--text-dim); }
```

**Quote:**
```html
<div class="quote">
  <p>The best way to predict the future is to invent it.</p>
  <div class="author">-- Alan Kay</div>
</div>
```
```css
.quote {
  border-left: 3px solid var(--accent2);
  padding: 12px 20px;
  margin: 14px 0;
  border-radius: 0 6px 6px 0;
}
.quote .author {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 6px;
}
```

**Two columns:**
```html
<div class="split">
  <div>Left column content</div>
  <div>Right column content</div>
</div>
```
```css
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
  margin-top: 14px;
}
```

**Stats row:**
```html
<div class="stat-row">
  <div class="stat">
    <div class="num accent">86%</div>
    <div class="label">completion rate</div>
  </div>
  <div class="stat">
    <div class="num accent2">12</div>
    <div class="label">participants</div>
  </div>
</div>
```
```css
.stat-row { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
.stat {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 18px;
  flex: 1;
  min-width: 130px;
  text-align: center;
}
.stat .num { font-size: 28px; font-weight: 700; }
.stat .label { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
```

**Layers (ordered items with colored borders):**
```html
<div class="layers">
  <div class="layer l1">
    <div class="layer-icon">01</div>
    <div class="layer-name accent">First Step</div>
    <div class="layer-desc">Description of what happens here.</div>
  </div>
  <div class="layer l2">
    <div class="layer-icon">02</div>
    <div class="layer-name accent2">Second Step</div>
    <div class="layer-desc">Description of the next step.</div>
  </div>
</div>
```
```css
.layers { display: flex; flex-direction: column; gap: 8px; margin-top: 18px; }
.layer {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 20px; border-radius: 8px;
  border: 1px solid var(--border);
  transition: transform 0.3s;
}
.layer:hover { transform: translateX(6px); }
.layer-icon { font-size: 22px; min-width: 36px; text-align: center; }
.layer-name { font-size: 17px; font-weight: 600; min-width: 120px; }
.layer-desc { font-size: 13px; color: var(--text-dim); }
.layer.l1 { border-color: rgba(85,170,136,0.4); background: rgba(85,170,136,0.04); }
.layer.l2 { border-color: rgba(212,168,67,0.4); background: rgba(212,168,67,0.04); }
.layer.l3 { border-color: rgba(68,136,204,0.4); background: rgba(68,136,204,0.04); }
```

### Navigation (JavaScript)

```javascript
let current = 0;
const slides = document.querySelectorAll('.slide');
const bar = document.querySelector('.progress-bar');
const counterCurrent = document.querySelectorAll('.current');
const counterTotal = document.querySelectorAll('.total');

function showSlide(n) {
  slides[current].classList.remove('active');
  current = Math.max(0, Math.min(n, slides.length - 1));
  slides[current].classList.add('active');
  if (bar) bar.style.width = ((current + 1) / slides.length * 100) + '%';
  counterCurrent.forEach(el => el.textContent = current + 1);
}

counterTotal.forEach(el => el.textContent = slides.length);
slides[0].classList.add('active');
if (bar) bar.style.width = (1 / slides.length * 100) + '%';

document.addEventListener('keydown', e => {
  if (['ArrowRight','Space','Enter'].includes(e.code)) { e.preventDefault(); showSlide(current + 1); }
  if (['ArrowLeft','Backspace'].includes(e.code)) { e.preventDefault(); showSlide(current - 1); }
  if (e.code === 'Home') { e.preventDefault(); showSlide(0); }
  if (e.code === 'End') { e.preventDefault(); showSlide(slides.length - 1); }
});

// Touch swipe
let touchStartX = 0;
document.addEventListener('touchstart', e => { touchStartX = e.changedTouches[0].screenX; });
document.addEventListener('touchend', e => {
  const diff = touchStartX - e.changedTouches[0].screenX;
  if (Math.abs(diff) > 50) { diff > 0 ? showSlide(current + 1) : showSlide(current - 1); }
});
```

### Navigation hint (bottom-right):
```html
<div class="nav-hint">arrows / space / swipe</div>
```
```css
.nav-hint {
  position: fixed;
  bottom: 16px; right: 32px;
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.4;
}
```

### Responsive

```css
@media (max-width: 768px) {
  .slide { padding: 32px 24px 48px; }
  h1 { font-size: 28px; }
  h2 { font-size: 22px; }
  p, li { font-size: 15px; }
  .split { grid-template-columns: 1fr; }
  .cards { grid-template-columns: 1fr; }
  .nav-hint { display: none; }
}
```

---

## Content Guidelines

- **One idea per slide** — don't overcrowd
- **5–7 bullet points max** per list
- **Code blocks short** — 3–5 lines
- **Whitespace matters** — let content breathe
- **No emojis** — use colored text classes (`.accent`, `.accent2`, etc.)
- **15–20 slides** is ideal for a 20–30 min talk

---

## File Structure

```
my-presentation/
├── index.html      ← single file, everything inline
└── (optional: images if referenced)
```

No build step. No dependencies. Open in browser — done.
