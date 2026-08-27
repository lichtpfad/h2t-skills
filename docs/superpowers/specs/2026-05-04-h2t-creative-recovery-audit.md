---
title: "h2t-creative Recovery Audit"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-04"
milestone: ""
---
# h2t-creative Recovery Audit

**Date:** 2026-05-04
**Status:** Approved
**Scope:** Gap analysis between legacy h2t skills and current h2t-creative modular system. Prerequisite for recovery spec.

---

## 1. Context

h2t-creative v1.2.0 was bumped after Phase 2b ("Aesthetic Recovery") visual regression that compared profiles against themselves — not against the original reference pages. The minor bump is **not live-confirmed** and should be treated as a patch-level increment until the real fidelity is restored.

Original skills being replaced:
- `h2t:landing` (v2.14.1) — HUD tactical landing page generator
- `h2t:deck` (v2.14.1) — HTML presentation generator (STYLE 1: terminal, STYLE 2: editorial)
- `h2t:design` (v2.14.1) — PFAD design system

Profile sources:
| Profile | Source |
|---------|--------|
| `h2t-graphs` | `C:/dev/h2t-landings/graphs/index.html` + `h2t:landing` SKILL.md |
| `h2t-pfad` | `h2t:design` SKILL.md (PFAD Design System) |
| `h2t-terminal` | `h2t:deck` STYLE 1 |
| `h2t-editorial` | `h2t:deck` STYLE 2 |
| `h2t-mono` | specdesigner.netlify.app |

Live reference screenshots: `docs/visual-regression/reference/`

---

## 2. What Was Migrated (Present in h2t-creative)

For each profile: `tokens.css` + `palettes/` + 5 base components (nav, hero, section, cta, footer) + `profile.yaml` (web fonts).

Shared components added in Phase 2a: `features-grid`, `stats`, `testimonials`, `pricing`, `faq`, `logos`.

These shared components use canonical tokens (color + font) — the Phase 2b work. They render correctly but are **structurally generic**.

---

## 3. What Was Lost — Complete Inventory

### 3.1 Profile-Specific Rich Components

Components that existed in the legacy skills as **named, reusable patterns** but were not migrated into profile `components/` directories:

| Component | Description | Source | Missing from |
|-----------|-------------|--------|--------------|
| `hud-panel` | Surface panel with 4 L-shaped corner brackets, 1px accent border | h2t:landing | h2t-graphs, h2t-pfad |
| `stats-bar` | Segmented stat cells, Inter numbers with accent glow, 1px grid borders | h2t:landing | h2t-graphs |
| `numbers-grid` | Cell-based data grid (1px border, `--surface` bg per cell) | h2t:landing | h2t-graphs |
| `chip` / `stack` | Monospace tech-stack label tags, border, optional accent highlight | h2t:landing | h2t-graphs, h2t-pfad |
| `code-block` | Styled code display with bg, border, mono font | h2t:deck | all dark profiles |
| `cards-grid` | Grid of content cards with colored borders, hover effects | h2t:deck | all profiles |
| `quote` / `pull-quote` | Left-border accent quote block | h2t:deck STYLE 2 | h2t-editorial |
| `layers` | Ordered steps list with colored left-borders, hover slide | h2t:deck | all profiles |
| `comparison-table` | Feature matrix with checkmarks and colored columns | specdesigner | h2t-mono, h2t-graphs |
| `two-column` | Side-by-side split layout (before/after, left/right) | specdesigner | h2t-mono |
| `screenshot-card` | Screenshot embed panel, green corner brackets, no image filters | h2t:landing | h2t-graphs, h2t-pfad |
| `section-tag` | `// LABEL` monospace prefix via `::before` | h2t:landing, h2t:design | h2t-graphs, h2t-pfad |
| `pfad-card` | bg-card surface, `:: LABEL` prefix, red sweep hover animation | h2t:design | h2t-pfad |
| `pfad-tag` | 4-corner bracket tag, expand-on-hover, active state fills edge | h2t:design | h2t-pfad |

### 3.2 Overlay / Background System

Visual layer system that sits underneath all content. Must be injected per-profile, not shared.

| Layer | Description | Source | Missing from |
|-------|-------------|--------|--------------|
| Grid background | 40–60px subtle CSS grid (`linear-gradient` repeating) | h2t:landing, h2t:design | h2t-graphs, h2t-pfad |
| Dot-field animation | Canvas2D, 50 drifting dots with red connection lines | h2t:design | h2t-graphs (currently `fx/background.js` in h2t-pfad only) |
| Scanlines overlay | CSS `repeating-linear-gradient`, z-index 9998 | h2t:design, h2t:deck STYLE 1 | already in h2t-terminal `tokens.css::after` ✓ |
| Corner marks | 4 L-shaped fixed marks at viewport edges | h2t:design | h2t-pfad |
| Coordinate labels | 8px fixed labels: N/E/version/date at corners | h2t:design | h2t-pfad |
| Cursor reticle | JS lerp-following crosshair, 4 brackets, pixel coords, label reveal | h2t:design | h2t-pfad (optional for landing) |

### 3.3 Visual Effects / CSS Patterns

Individual CSS patterns that make the profiles distinctive:

| Effect | Description | Missing from |
|--------|-------------|--------------|
| Glow text-shadow | `text-shadow: 0 0 15px var(--accent-glow)` on accent numbers | h2t-graphs |
| Red sweep hover | `card::before { width: 0 → 100% }` on hover | h2t-pfad |
| Blinking cursor | `::after { content: '▋'; animation: blink }` on h1 | h2t-terminal (hero ✓ only) |
| `$ ` prompt prefix | `hero__prompt::before { content: '$ ' }` | h2t-terminal (hero ✓ only) |
| Fade-up animation | `@keyframes fadeUp` staggered per child | all deck profiles |
| Slide-in animation | `@keyframes slideIn` from left | h2t-editorial |
| Corner bracket tag | 4-corner CSS bracket as hero badge | h2t-graphs (hero ✓ has it) |
| `::` card label prefix | `card-label::before { content: ':: ' }` | h2t-pfad |

### 3.4 Integration (Mermaid)

| Feature | Description | Missing from |
|---------|-------------|--------------|
| Mermaid diagrams | Dark-themed Mermaid.js flowcharts (CDN) matching HUD tokens | h2t-graphs, h2t-pfad |

---

## 4. Shared Components: Correct Scope

Current shared components (Phase 2a) are appropriate ONLY for `h2t-default` and `h2t-editorial`. For dark/mono profiles they should be replaced by profile-specific variants.

| Component | h2t-default | h2t-editorial | h2t-graphs | h2t-pfad | h2t-terminal | h2t-mono |
|-----------|-------------|---------------|------------|----------|--------------|----------|
| `features-grid` | shared ✓ | shared ✓ | → profile-specific | → profile-specific | → profile-specific | → profile-specific |
| `stats` | shared ✓ | shared ✓ | → `stats-bar` (glow) | → profile-specific | → profile-specific | shared ✓ |
| `testimonials` | shared ✓ | → `quote` (editorial) | → profile-specific | → profile-specific | → profile-specific | shared ✓ |
| `pricing` | shared ✓ | shared ✓ | → `hud-panel` wrapper | → profile-specific | → profile-specific | shared ✓ |
| `faq` | shared ✓ | shared ✓ | shared ✓ | shared ✓ | shared ✓ | shared ✓ |
| `logos` | shared ✓ | shared ✓ | → `chip` row | → `chip` row | → `chip` row | → minimal variant |

---

## 5. Semver Status

| Version | Status | Notes |
|---------|--------|-------|
| `1.1.0` | Live-confirmed | Phase 2a shared components |
| `1.2.0` | **NOT live-confirmed** | Phase 2b token contract — visual gate was wrong (self-comparison, not vs references) |

**Correct semver path:** v1.2.0 remains not live-confirmed. Next confirmed release version must be decided before bump based on actual git/publish state at the time of gate passage — do not assume re-use of `1.2.0` tag is safe.

---

## 6. Recovery Spec Scope (Next Step)

The recovery spec (`2026-05-04-h2t-creative-recovery-spec.md`) must cover:

1. **Phase R1 — Profile-specific rich components** for h2t-graphs + h2t-pfad (highest fidelity gap)
2. **Phase R2 — Overlay system** (grid + dot-field for graphs/pfad, already OK for terminal)
3. **Phase R3 — h2t-mono rich patterns** (two-column, comparison-table)
4. **Phase R4 — Visual gate** against live reference pages (not self-comparison)
5. **Phase R5 — Version confirmation** bump to 1.2.0 only after R4 passes

---

## 7. Reference Assets

| Asset | Path |
|-------|------|
| specdesigner.netlify.app screenshot | `docs/visual-regression/reference/specdesigner.netlify.app/desktop_20260504_000404.png` |
| graphs.lichtpfadstudio.com screenshot | `docs/visual-regression/reference/graphs.lichtpfadstudio.com/desktop_20260504_000404.png` |
| h2t:landing legacy skill | `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/landing/SKILL.md` |
| h2t:deck legacy skill | `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/deck/SKILL.md` |
| h2t:design legacy skill | `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/design/SKILL.md` |
| h2t-landings/graphs source | `C:/dev/h2t-landings/graphs/index.html` |
