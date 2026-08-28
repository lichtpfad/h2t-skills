---
title: "h2t-creative: Style Extraction Pipeline"
status: "draft"
date: "2026-05-04"
milestone: ""
issue: ""
---
# h2t-creative: Style Extraction Pipeline

## Why this plan exists

R1 implementation (branch `codex/r1-legacy-fidelity`) generated component demos and synthetic
validation pages instead of reproducing the reference. CSS was patched iteratively without visual
verification. Result: pages drifted further from the reference with each iteration.

Any generated validation page with synthetic "R1 recovery" copy is invalid as visual evidence.

**Root cause:** wrong goal was optimized. "Validate components" ≠ "reproduce reference".

**Freeze:** R1 component work is halted. No CSS patches until this plan is approved and executed.

---

## The Correct Pipeline

```
Reference → Golden Import → Design System → Modular Profile → Reference Parity
```

### Step 1 — Reference → Golden Import

Both profiles use Track A (golden import). No LLM rebuild track.

#### Track A: h2t-graphs (golden implementation exists)

Do NOT ask LLM to recreate the page. Use the existing golden implementation directly.

**Step 1A — Golden Import:**
Copy `C:/dev/h2t-landings/graphs/index.html` to
`docs/visual-regression/2026-05-04-r1/h2t-graphs-golden/index.html`.
Make only path-safe normalization if required (e.g. fix relative asset paths).
No redesign. No rewritten CSS. No invented content.

**Step 1B — Render Verification:**
Agent captures screenshot of the golden page and shows it for human review.
Gate: human confirms it renders correctly.

**Step 1C — Design System Extraction:**
Only after golden page renders correctly, extract design-system facts from that exact HTML/CSS
(see Step 2). Source of truth is the golden file, not LLM memory or screenshots.

#### Track A2: h2t-mono (golden implementation exists)

Do NOT ask LLM to recreate the page. Use the existing golden implementation directly.

**Step 1A:** Copy `C:/dev/h2t-landings/specdesigner.html` →
`docs/visual-regression/2026-05-04-r1/h2t-mono-golden/index.html`
with path-safe normalization only. No redesign. No rewritten CSS. No invented content.

**Step 1B:** Agent captures screenshot of the golden page and shows it for human review.
Gate: human confirms it renders correctly.

**Step 1C:** Only after golden page renders correctly, extract design-system facts from that
exact HTML/CSS.

---

### Step 2 — Golden Import → Design System

**Goal:** Extract a named, structured design system from the golden source only.

Deliverables — one document per profile, containing:
- Color tokens (exact hex values from source)
- Typography scale (font families, sizes, weights, line-heights, letter-spacing per role)
- Spacing system (padding/margin values actually used)
- Layout rules (max-width, section padding pattern, grid system)
- Component inventory (what components exist, their HTML structure, their CSS rules)
- Interaction / FX grammar (glows, transitions, cursors, overlays, cursor style)
- Forbidden patterns (what is explicitly NOT in this design system)

**Gate:** Design system document reviewed and approved by human before Step 3 begins.

---

### Step 3 — Design System → Modular Profile

**Goal:** Split the approved design system into the h2t-creative profile structure.

Files produced:
- `tokens.css` — color, typography, spacing variables (values from Step 2, not invented)
- `palettes/default.css` — concrete color values
- `profile.yaml` — web_fonts, head_scripts
- `components/<name>/` — one component per unit identified in Step 2
- `validation/recipe.yaml` — uses reference-equivalent content, not synthetic copy

Rule: if modularization requires inventing a component not present in the reference, that
component must be explicitly marked as an extension, not a recovery.

No version bump at this step.

---

### Step 4 — Modular Profile → Reference Parity

**Goal:** Assembled modular page matches the golden import from Step 1.

Method:
1. Agent assembles the profile using `validation/recipe.yaml`
2. Agent captures screenshots through approved workflow and shows them
3. Human reviews side-by-side against Step 1 reference
4. Differences categorized: modularity error (fix components) vs content difference (acceptable)

**Gate:** Human confirms parity is sufficient. Only then — version bump.

---

## Calibration Cases

### Case A: h2t-graphs

- **Source:** `C:/dev/h2t-landings/graphs/index.html` — complete HTML+CSS, 899 lines, golden
- **Track:** 1A (golden import, no LLM rebuild)
- **Composition:** fixed nav, centered full-height hero, canvas graph viz, comparison sections,
  mermaid diagrams, feature grid, chip stack, code blocks, footer
- **Legacy status:** golden implementation — migrate, do not redesign

### Case B: h2t-mono

- **Source:** `C:/dev/h2t-landings/specdesigner.html` — complete HTML+CSS, 1223 lines, golden
- **Track:** 1A (golden import, no LLM rebuild)
- **Composition:** centered brand name, monospace throughout, terminal/code block aesthetic,
  dark bg, red accent, CTA buttons
- **Legacy status:** golden implementation — migrate, do not redesign

---

## Rules

1. Agent does not mark visual match as passed. Only human can pass visual gates.
2. Agent captures screenshots only through approved h2t screenshot workflow. If unavailable,
   visual gate is blocked.
3. No invented content (copy, numbers, section names) not present in the reference.
4. Old skills v2.14.1 are ground truth. New system must preserve their aesthetic exactly.
5. If Step 4 output differs from Step 1, that is a modularity error — fix the components,
   do not invent a new design.
6. Any generated validation page with synthetic "R1 recovery" copy is invalid as visual evidence.

---

## What happens to current R1 work

Current branch `codex/r1-legacy-fidelity` contains:
- Component scaffolding (hud-panel, stats-bar, mermaid-diagram, etc.) — frozen, not deleted
- Validation recipes with synthetic content — invalid as evidence, will be replaced in Step 3
- CSS written from memory/guessing — will be replaced with Step 2 extraction

None of it is deleted. After Step 2 produces the actual design system, components will be
rewritten from that spec.

---

## First deliverable (approved for Step 1A only)

Both golden imports must be completed before extraction or modularization begins.
Do not proceed to Step 1C / Step 2 until both screenshots are reviewed and approved by human.

**1. h2t-graphs golden import:**
Copy `C:/dev/h2t-landings/graphs/index.html` →
`docs/visual-regression/2026-05-04-r1/h2t-graphs-golden/index.html`
with path-safe normalization only (no CSS changes, no content changes).

**2. h2t-mono golden import:**
Copy `C:/dev/h2t-landings/specdesigner.html` →
`docs/visual-regression/2026-05-04-r1/h2t-mono-golden/index.html`
with path-safe normalization only (no CSS changes, no content changes).

**3. Screenshots:**
Agent captures screenshots of both golden pages through approved h2t screenshot workflow
and shows them for human review. Human confirms both render correctly.

---

## Open technical note

Pre-commit hook uses `/c/Users/.../WindowsApps/python3` shim instead of `.h2t/venv`. This is a
hygiene bug unrelated to this plan — track separately.
