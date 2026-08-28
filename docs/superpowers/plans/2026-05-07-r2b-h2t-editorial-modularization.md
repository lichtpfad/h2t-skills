---
title: "R2b — h2t-editorial deck + landing modularization plan"
status: "draft"
date: "2026-05-07"
milestone: ""
issue: ""
---
# R2b — h2t-editorial deck + landing modularization plan

> **⚠ Source Arbitration Reset — 2026-05-07.** Implementation through
> Batch B (T1–T7) was carried out against the wrong primary source —
> pos-sprint editorial (System A: terracotta accent + Inter body). The
> human canonical visual target is **rejuve-pitch-deck** (System B: gold
> accent + Georgia body + brand-wordmark cover). All T1–T7 styling/recipe
> artifacts are flagged for rebuild before any visual pass. See the
> `## Source Arbitration Reset (2026-05-07)` section below for the decision
> record and rebuild scope. Full report:
> [`docs/superpowers/specs/2026-05-07-r2b-source-arbitration.md`](../specs/2026-05-07-r2b-source-arbitration.md).

**Issues:**
- [#87 skills: [R2b] Recover h2t-editorial deck legacy fidelity](https://github.com/lichtpfad/h2t-skills/issues/87)
- [#88 skills: [R2b] Recover h2t-editorial landing legacy fidelity](https://github.com/lichtpfad/h2t-skills/issues/88)

**Branch:** `codex/r2b-editorial-deck` — implements **#87 only** (deck form).
The T0 artifacts in this plan (locked goldens for both forms, dossier for
both forms, full plan) ship together with the first deck implementation
commit. Landing (#88) is a follow-up branch `codex/r2b-editorial-landing`
that rebases onto merged deck PR and adds only landing-specific component
work; it reuses this plan + the already-locked landing goldens.

No standalone "T0 inventory" PR is opened — keeps the per-profile PR
count to two (deck + landing) instead of three.

**Pipeline:** governed by `plugins/h2t-creative/skills/legacy-fidelity`.

**Acceptance gates (two-contour from T0, NOT amended mid-flight):**

1. **Gate A — Desktop fidelity.** Both forms at 1440×900 must match the
   approved goldens. Token contract preserved from existing `DESIGN.md`
   (3 palettes default/warm/night).
2. **Gate B — Mobile usability.** Both forms at 390×844 must render without
   catastrophic overflow / clipping / unreadable layout. Profile-owned
   `@media (max-width: 480px)` rules required from the start (NOT banned, as
   the original R2a plan wrongly stated). Mobile is a usability gate, not a
   passive baseline.

Both gates verified per the legacy-fidelity skill: Agent Visual QA opens
every screenshot before any human review.

---

## 1. Slice strategy — split #87 and #88

R2a was deck-only (one slice). R2b targets both deck (#87) and landing (#88)
on the same profile. To keep PRs reviewable and gates independent:

- **R2b-deck (#87)** — current branch. T1+ implementation in this PR.
- **R2b-landing (#88)** — separate branch `codex/r2b-editorial-landing`,
  rebased on top of merged R2b-deck PR. Reuses this plan + already-locked
  landing goldens (which ship in the R2b-deck PR as part of T0 inventory).

Both slices share the same `profiles/h2t-editorial/` profile dir. The deck
slice adds `deck/`; the landing slice updates `components/` (already
present — `cta`, `footer`, `hero`, `nav`, `section`).

**This branch is scoped to #87 only.** Landing implementation is explicitly
deferred. Landing-related sections of this plan (§3.2, §5.2, §6.2, §7.2,
§8.landing-specific, §9.2) are forward-reference documentation for the
follow-up branch — they describe what `codex/r2b-editorial-landing` will do,
not what this PR delivers.

### Why split:
- Gate B for deck is a different design problem than Gate B for landing
  (slide reflow vs scrollable section reflow).
- Each PR stays under the same scale as R2a (~1.5k lines insert).
- Failures in one form don't block the other.

### Why no separate inventory PR:
- T0 work (golden lock + plan) is rapport, not deliverable. Bundling it with
  the first implementation commit keeps the per-profile PR count to two
  (deck + landing) instead of three (inventory + deck + landing).
- Landing PR rebases on merged deck → it sees the locked goldens + plan as
  already-existing context, not as a parallel WIP.

---

## 2. Caller inventory (T0 — assembler API stability)

**Greppable callers of `assemble_landing` and `assemble_deck`:** all live in
`tests/h2t_creative/test_assembler.py` and `plugins/h2t-creative/tests/`.
No external CLI, scripts, or consumer skills depend on either signature.

R2a-introduced switch `_is_deck_form_profile(profile_dir)` flips
`assemble_deck` to single-file form-v2 when `<profile>/deck/tokens.css` exists.

**Implication for R2b:**
- Adding `deck/` subdir to `profiles/h2t-editorial/` activates form-v2 for
  editorial deck — assembler signature unchanged, no caller migration needed.
- `assemble_landing` is unchanged from R2a; landing slice updates only
  components and palettes, not the API.

**Conclusion:** both APIs stable. No T0 caller-migration step required.

---

## 3. Source dossier (locked under `docs/visual-regression/2026-05-07-r2b/`)

### 3.1 Editorial deck (#87)

| id | role | kind | path | size |
|---|---|---|---|---|
| `pos-sprint-editorial-example` | **primary** | golden-html | `h2t-editorial-deck-golden/pos-sprint-editorial-example.html` | 20 KB |
| `pos-sprint-deck-skill` | contract | skill-doc | `h2t-editorial-deck-golden/pos-sprint-deck-SKILL.md` | 16 KB |
| `pos-sprint-deck-readme` | contract | skill-readme | `h2t-editorial-deck-golden/pos-sprint-deck-README.md` | 3 KB |
| `rejuve-presentation` | secondary | live-deck | `h2t-editorial-deck-golden/rejuve-presentation.html` (83 slides) | 76 KB |
| `rejuve-pitch-deck` | secondary | live-deck | `h2t-editorial-deck-golden/rejuve-pitch-deck.html` (45 slides) | 42 KB |

**Reference screenshots captured:** `screenshots-{pos-sprint,rejuve-presentation,rejuve-pitch-deck}/unknown/{desktop,mobile}_*.png` for slide 01 of each (3 sources × 2 formats = 6 PNGs).

**Note on `rejuve-pitch-deck`:** Inter not present (only Playfair). Treat as
secondary-only, do NOT lift body typography decisions from this file.

### 3.2 Editorial landing (#88)

| id | role | kind | path | size |
|---|---|---|---|---|
| `rejuve-appendix-competitive-report` | **primary** | golden-html | `h2t-editorial-landing-golden/rejuve-appendix-competitive-report.html` | 70 KB |
| `rejuve-appendix-elpodium-decomposition` | **primary** | golden-html | `h2t-editorial-landing-golden/rejuve-appendix-elpodium-decomposition.html` | 70 KB |

**Reference screenshots captured:** `screenshots-rejuve-appendix-{competitive-report,elpodium-decomposition}/unknown/{desktop,mobile}_*.png` (2 sources × 2 formats = 4 PNGs).

Both files use `<nav class="tabs">` + `<div class="section">` containers with
`<h1>`/`<h2>` headings and prose. `appendix-competitive-report.html` also has
`<table class="bt">` (decomposition + comparison tables) — confirms landing
layout vocabulary covers nav + sections + tables.

**No pos-sprint primary for landing form** — pos-sprint is a deck skill only.
The two rejuve appendix files are the authoritative source for editorial
landing structure. Typography tokens reuse the deck dossier (Playfair + Inter,
3-palette family).

### 3.3 Existing in-repo state (NOT golden — current implementation)

`profiles/h2t-editorial/`:
- `DESIGN.md` — documents 3 palettes + Playfair/Inter contract
- `tokens.css` — landing-form contract (`--color-*` prefix per R1 convention)
- `palettes/{default,warm,night}.css`
- `components/{cta,footer,hero,nav,section}/` — landing components, may need
  fidelity update against rejuve goldens (#88)
- `profile.yaml` — `web_fonts` link to Google Fonts (Playfair + Inter)

R2b-deck does **not** modify any of the above; it adds a parallel `deck/`
tree following the R2a deck-form pattern. R2b-landing **may** modify
existing components if they drift from goldens — discovery in T1+.

---

## 4. Token contract (preserved from existing `DESIGN.md` + #87)

### Color tokens (3 palettes)

| Token | default (dark ink) | warm (cream) | night (dark gold) |
|---|---|---|---|
| `--color-bg` | `#faf9f6` | `#fdf8f0` | `#1a1614` |
| `--color-bg-light` | `#f0eeeb` | `#f5ede0` | `#242018` |
| `--color-bg-card` | `#ffffff` | `#fffdf9` | `#2a2620` |
| `--color-text` | `#1a1a1a` | `#2a1f14` | `#e8dfd4` |
| `--color-text-dim` | `#6b6b6b` | `#8a7a6a` | `#9a9080` |
| `--color-accent` | `#c45a3c` | `#b85c30` | `#d4aa50` |
| `--color-border` | `#e0ddd8` | `#e8ddd0` | `#403830` |

**Token-name convention:** existing landing form uses `--color-*` prefix
(R1 convention). Deck form (R2b-deck) will follow R2a's deck convention of
**bare `--bg/--text/--accent` token names** in `deck/tokens.css` to match
the form-v2 single-file output pattern. Tests assert the convention boundary
(deck CSS uses bare names, landing CSS uses `--color-*`).

### Typography tokens

| Token | Value |
|---|---|
| `--font-display` (landing) / `--font-heading` (deck) | `'Playfair Display', Georgia, serif` |
| `--font-body` | `'Inter', 'Helvetica Neue', sans-serif` |
| Google Fonts link | `Playfair+Display:ital,wght@0,400;0,700;1,400&family=Inter:wght@400;500;700&display=swap` (already in `profile.yaml`) |

`h1` Playfair 64-72px display weight, `h2` Playfair 32-40px, body Inter
16px line-height 1.75+, generous classical leading. Exact sizes
extracted from goldens in T1.

---

## 5. Layout vocabulary

### 5.1 Editorial deck (#87)

Per `pos-sprint-deck-SKILL.md` STYLE 2 § + observed in `rejuve-presentation`:

| layout | purpose | required content | observed in |
|---|---|---|---|
| `title` | Centered display title slide | `eyebrow?`, `headline`, `subline?`, `attribution?` | pos-sprint slide 01, rejuve slide 01 |
| `title-body` | Default content slide (h2 + prose) | `eyebrow?`, `headline`, `body_html` | most slides |
| `quote` | Pull-quote slide with attribution | `quote_html`, `attribution?` | pos-sprint slide 03 |
| `two-column` | Side-by-side prose / list | `headline`, `left_html`, `right_html` | rejuve presentation throughout |
| `image-text` | Image (or figure) + caption + body | `image_url`, `caption?`, `body_html` | rejuve presentation |
| `divider` | Section break / chapter heading | `eyebrow`, `headline` | rejuve presentation |
| `final` | Closing slide (large centered) | `eyebrow?`, `headline`, `subline?` | pos-sprint final, rejuve final |

**Layouts NOT in editorial deck** (carried from terminal deck for awareness,
but should NOT appear): `code` (no monospace ornaments per editorial brand),
`table` (use prose tables sparingly; if needed, `title-body` with `<table>`
in `body_html`), `cards`/`stats`/`layers` (not used in editorial — these are
terminal-style components).

### 5.2 Editorial landing (#88)

Per existing `components/` + observed in rejuve appendix files:

| component | purpose | source |
|---|---|---|
| `nav` | Top tabs (`<nav class="tabs">`) | rejuve appendix files |
| `hero` | Page header / `<h1>` + subtitle | both goldens |
| `section` | `<div class="section">` with `<h2>` + prose | both goldens |
| `prose-block` | Long-form prose with classical column width | both goldens |
| `comparison-table` | `<table class="bt">` decomposition / comparison | `rejuve-appendix-competitive-report` |
| `cta` | Call-to-action buttons | existing landing component |
| `footer` | Page footer | existing landing component |

Existing components (`cta`, `footer`, `hero`, `nav`, `section`) likely need
fidelity update against rejuve goldens. T1 of #88 = component-by-component
audit + alignment.

---

## 6. Mobile adaptation contract (Gate B — designed from T0)

Mirror R2a `@media (max-width: 480px)` pattern, profile-specific values:

### 6.1 Deck

| Rule | Value |
|---|---|
| `.slide` padding | `28px 20px 32px` (vs desktop `64px 80px 96px`) |
| `h1` (display, title slide) | `36px` (vs desktop `64px+`) |
| `h2` (content slide) | `22px` (vs desktop `32-40px`) |
| Body / `p` | `15px line-height 1.7` (vs desktop `16px line-height 1.75+`) |
| `.two-column` | `grid-template-columns: 1fr` (single column stack) |
| `.image-text` | image ≤ viewport width; caption tightens; padding shrinks |
| Frame chrome | counter / nav-hint scaled to 11px / 10px (per R2a precedent) |

### 6.2 Landing

| Rule | Value |
|---|---|
| `body` padding | reduce horizontal padding (~24px from desktop ~80px) |
| `h1` | `32px` (vs desktop `48-56px`) |
| `h2` | `22px` |
| `nav.tabs` | wrap or scroll-snap horizontally; do not collapse to hamburger in this slice (out of scope — separate UX decision) |
| `table.bt` | dual-representation (T15.5 pattern from R2a): `.table-desktop` keeps `<table>`; `.table-mobile` stacks rows as cards. Tests assert the toggle. |
| `.section` | reduce vertical rhythm (margin / line-height) |

Both forms follow the legacy-fidelity skill's mobile rules:
- ❌ no `display: none` on essential content
- ❌ no JS viewport branching
- ❌ no random redesign that changes desktop fidelity
- ✅ profile-owned `@media (max-width: 480px)` rules in deck/landing CSS
- ✅ alternative mobile representations toggled via CSS (e.g. table cards)

---

## 7. Recipe contracts (sketches — finalized per slice in T7)

### 7.1 Deck recipe — `validation/recipe-deck.yaml`

```yaml
type: deck
profile: h2t-editorial
palette: default
lang: en
title: "Editorial Deck Validation"
nav_buttons: false
nav_hint_text: "arrows / space / swipe"

slides:
  - layout: title
    align: center
    content:
      eyebrow: "chapter 01"
      headline: "On Light, On Form"
      subline: "Notes toward a classical web."
      attribution: "speaker · 2026"
  - layout: title-body
    content:
      eyebrow: "the question"
      headline: "What does serif on screen ask of us?"
      body_html: "<p>...</p>"
  - layout: quote
    content:
      quote_html: "<p>Form follows function — but only when both are noticed.</p>"
      attribution: "Louis Sullivan · 1896"
  - layout: two-column
    content:
      headline: "Two readings"
      left_html: "<h3>Tradition</h3>..."
      right_html: "<h3>Affordance</h3>..."
  - layout: image-text
    content:
      image_url: "..."
      caption: "Figure 1. ..."
      body_html: "<p>...</p>"
  - layout: divider
    align: center
    content:
      eyebrow: "// part II"
      headline: "Practice"
  - layout: final
    align: center
    content:
      eyebrow: "principle 01"
      headline: "Read slowly. Iterate kindly."
```

7-slide validation deck (one per layout). Mirrors R2a's 11-slide pattern but
fewer layouts since editorial drops `code` / `table` / `cards` / `stats` /
`layers`.

### 7.2 Landing recipe — `validation/recipe.yaml`

Existing landing recipe contract; extend per-section as needed in T7.
Sections: `nav` → `hero` → 3-5 `section` blocks (one with prose, one with
comparison-table, one with `cta`) → `footer`.

---

## 8. Forbidden patterns (deck + landing — guarded by tests)

### Both forms

- ❌ `cursor: crosshair` (terminal-style, not editorial)
- ❌ Mermaid diagrams
- ❌ Emojis in headlines / labels (use accent color instead)
- ❌ Mobile reflow / JS viewport hacks (`matchMedia`, `innerWidth`)
- ❌ `display: none` / `visibility: hidden` on essential slide/section
  content (state-based via `:empty` / `:not(...)` allowed)
- ❌ Synthetic copy in validation recipe (`lorem ipsum`, `placeholder`,
  `TODO`, `synthetic`, etc.)

### Deck-specific

- ❌ Scanline overlay (`body::after` with `repeating-linear-gradient`) —
  that is terminal-style; editorial is clean
- ❌ Monospace fonts anywhere (`code-block`, `pre`, `mono` chips)
- ❌ Bare `--bg` / `--text` declarations outside `deck/` subdir (deck-form
  contract isolation)

### Landing-specific

- ❌ `--color-*` declarations inside `deck/` subdir (landing-form contract
  isolation)
- ❌ Slide containers (`.slide`, `.slide-inner`) — those belong to deck
- ❌ Horizontal scroll on `<table>` as the primary mobile UX (use
  dual-representation per R2a T15.5)

---

## 9. Test groups (mirror R2a contract layout)

New file per slice: `tests/test_r2b_legacy_fidelity_{deck,landing}.py`.

### 9.1 Deck (#87) test groups

| § | Group |
|---|---|
| 9.1.1 | Source dossier (references.yaml + screenshots) |
| 9.1.2 | Token contract (3 palettes, 7 tokens each, with exact values) |
| 9.1.3 | Slide layout coverage (7 layouts: title, title-body, quote, two-column, image-text, divider, final) |
| 9.1.4 | Single-file output contract (no base.css/profile.css/script src) |
| 9.1.5 | Frame contract (counter / progress-bar / nav-hint / lang attr / no slide-menu) |
| 9.1.6 | Forbidden patterns (no scanlines / no monospace / no crosshair / no emoji / no mermaid) |
| 9.1.7 | Single-font contract (Playfair display + Inter body — NO monospace fallbacks) |
| 9.1.8 | Helper unit tests (existing `_render_*` reuse where applicable; no new helpers expected) |
| 9.1.9 | Generic test alignment (`test_smoke.py` + `test_font_loading.py`) |
| 9.1.10 | Mobile adaptation contract (breakpoint, desktop invariants outside `@media`, mobile coverage per layout) |

### 9.2 Landing (#88) test groups

| § | Group |
|---|---|
| 9.2.1 | Component fidelity (`nav`, `hero`, `section`, `cta`, `footer`, `comparison-table`) — new component if needed |
| 9.2.2 | Token reuse (landing CSS uses existing `--color-*` from R1 contract) |
| 9.2.3 | Recipe contract (validation/recipe.yaml exercises every component once) |
| 9.2.4 | Multi-file output (`index.html` + `base.css` + `profile.css` per R1 landing pattern) |
| 9.2.5 | Forbidden patterns (no slide containers, no deck-form bare tokens, etc.) |
| 9.2.6 | Mobile adaptation contract (breakpoint, table dual-representation, `<nav class="tabs">` mobile policy) |

---

## 10. Build sequence

### 10.1 R2b-deck (#87) — this branch

T0 already complete (this plan + locked goldens). Implementation enters at
**T1 deck-only**. T0 artifacts ship in the same commit/PR as the first deck
implementation (no standalone inventory commit).

| Step | Task |
|---|---|
| T0 | ✅ Caller inventory + golden lock + plan (this commit's T0 artifacts) |
| T1 | Tests-first for §9.1.1 (source dossier + token contract — deck only) → implement `profiles/h2t-editorial/sources/references.yaml` (deck section) + `deck/tokens.css` + `deck/palettes/{default,warm,night}.css` |
| T2 | Tests-first for §9.1.3 (deck slide layout coverage) → 7 layouts under `deck/slides/<layout>/` (HTML + CSS + manifest) |
| T3 | Tests-first for §9.1.5 (frame contract) → `deck/frame/frame.css` + `deck/js/deck-nav.js` |
| T4 | Tests-first for §9.1.4 (single-file output) + §9.1.6 (forbidden patterns) → assembler routing (already in place from R2a) verified for h2t-editorial deck |
| T5 | `validation/recipe-deck.yaml` exercising all 7 layouts |
| T6 | Tests-first for §9.1.10 mobile contract → `@media (max-width: 480px)` rules in deck CSS |
| T7 | Tests-first for §9.1.7 (single-font: Playfair display + Inter body, NO monospace) and §9.1.9 (generic test alignment) |
| T8 | Build deck → `dist/r2b-h2t-editorial-deck-validation/index.html` |
| T9 | Capture all slides (desktop + mobile) via `tools/deck-screenshot-all.py` |
| T10 | **Mandatory Agent Visual QA** — open every PNG, write `parity-notes.md` per legacy-fidelity skill |
| T11 | Iterate any BLOCKER issues → re-capture → re-QA |
| T12 | Human approval (Gate A + Gate B) |
| T13 | Commit slice (single squashed `feat(h2t-creative): recover h2t-editorial deck profile from golden sources`; **no version bump**) |
| T14 | Push branch + create PR |
| T15 | Live verify → bump (`chore(h2t-creative): bump version after editorial deck live verification`) |
| T16 | Merge |

**Boundary:** T1 starts deck implementation only. **Do not touch
`profiles/h2t-editorial/components/`** in this branch — that's landing
territory. **Do not modify** existing landing-form `tokens.css` /
`palettes/*.css` at profile root — they are owned by R2b-landing slice.

### 10.2 R2b-landing (#88) — follow-up branch

Same T1..T16 shape, applied to landing components (§9.2.x test groups).
Branch `codex/r2b-editorial-landing` is created from main AFTER R2b-deck PR
merges; it re-uses this plan + the already-locked landing goldens that
shipped in R2b-deck.

Mobile is designed from the start (T6) — not a mid-flight amendment, per
legacy-fidelity skill rule.

---

## 11. Out of scope (deferred)

- Other profiles (h2t-default polish, h2t-graphs, h2t-mono, h2t-pfad)
- Editorial deck `cards` / `stats` / `layers` / `code` / `table` layouts —
  deliberately NOT in editorial vocabulary (see §5.1)
- Mobile nav-hamburger UX — deferred (out of scope until human design decision)
- pos-sprint STYLE 1 → editorial mapping — STYLE 2 only is editorial; STYLE 1
  was R2a (terminal)
- Print / PDF export
- External image assets — placeholders / Unsplash refs in validation recipe
  only; production decks supply own images

---

## 12. R2a precedents reused in R2b

Things that R2b inherits from R2a without reinventing:

- Two-gate visual QA model (Gate A desktop + Gate B mobile)
- Agent Visual QA mandatory before human review (per legacy-fidelity skill)
- `_is_deck_form_profile` switch — flips assemble_deck to single-file when
  `deck/tokens.css` exists; no caller migration needed
- Form-v2 deck output pattern (`tokens.css` + `palettes/` + `frame/` +
  `slides/<layout>/` + `js/deck-nav.js`)
- `deck-screenshot-all.py` tool for per-slide capture via `window.showSlide`
- Validation recipe + `parity-notes.md` workflow
- Token-namespace separation: `deck/` uses bare `--bg/--text/--accent`;
  landing uses `--color-*`
- Dual-representation table pattern (`.table-desktop` + `.table-mobile`
  cards) — applied to landing's `comparison-table` (#88)
- Layout owns structural wrappers; recipe owns inner content
- Synthetic-copy guard (no lorem ipsum / placeholder / TODO in recipe)
- Slide-padding tokens (`--deck-slide-padding-{top,right,bottom,left}`) —
  reuse the same handle for editorial deck if per-deck inset tuning desired

---

## 13. T0 deliverables (ship in same commit as deck T1+ implementation)

- [x] Plan: this file
- [x] Source dossier locked under `docs/visual-regression/2026-05-07-r2b/`:
  - `h2t-editorial-deck-golden/` — 5 sources + 6 reference screenshots
  - `h2t-editorial-landing-golden/` — 2 sources + 4 reference screenshots
- [x] Caller inventory (§2) — both APIs stable, no migration needed
- [x] Token + typography contracts documented (§4)
- [x] Layout / component vocabulary documented (§5)
- [x] Mobile adaptation contract drafted (§6)
- [x] Recipe contract sketches (§7)
- [x] Forbidden-pattern list (§8)
- [x] Test group plan (§9)
- [x] Build sequence outline (§10)

**T0 stop.** Next commit on this branch = T1 deck implementation. Landing
implementation (#88) is a separate branch — see §1 and §10.2.

---

## 14. Reference

- legacy-fidelity skill: `plugins/h2t-creative/skills/legacy-fidelity/SKILL.md`
- pressure scenarios: `plugins/h2t-creative/skills/legacy-fidelity/references/pressure-scenarios.md`
- R2a exemplar: PR #95, commits `da2f47f` (recovery) + `4c40973` (bump)
- R2a plan: `docs/superpowers/plans/2026-05-05-r2a-h2t-terminal-deck-modularization.md`
- R2a parity-notes: `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/parity-notes.md`

---

## 15. Source Arbitration Reset (2026-05-07)

### 15.1 Trigger

After Batch C (build + screenshots) the human reviewer compared the
assembled deck slide-01 against the rejuve-pitch-deck reference and called
the visual delta unacceptable: *"стиль ни хрена не похож"*. The
implementation through T1–T7 had treated `pos-sprint-editorial-example` as
the **primary** source and tried to honour it faithfully. The rejuve goldens
were marked **secondary** in the §3 dossier — and the agent silently
absorbed their mismatched signals as "secondary variation" instead of
flagging the conflict.

### 15.2 What was actually different

The three deck goldens turn out to encode **two distinct visual systems**,
not three variants of one editorial style:

| Aspect           | A — tech-article (pos-sprint, rejuve-presentation) | B — luxury-print (rejuve-pitch-deck)         |
|------------------|----------------------------------------------------|----------------------------------------------|
| Accent           | `#c45a3c` terracotta                               | `#c9a96e` gold                               |
| Body font        | **Inter** (sans)                                   | **Georgia** (serif)                          |
| Heading font     | Playfair Display                                   | Playfair Display                             |
| Token convention | `--font-heading` / `--font-body`                   | `--fh` / `--fb` / `--fu`                     |
| Background       | `#faf9f6`                                          | `#fafaf8` (warmer)                           |
| Cover grammar    | left-aligned article + `<hr>` rule                 | brand wordmark + 40×2 gold rule + meta line  |
| Per-slide kicker | uppercase letter-spaced "eyebrow"                  | small uppercase ".label"                     |
| Decorative rule  | thin border-bottom                                 | 40×2px accent rectangle (heavily reused)     |
| Progress-bar     | (T3 implementation: 1px)                           | 2px                                          |
| Counter type     | dim + zero-padded (R2a JS contract leak)           | sans 11px dim, no zero-pad                   |

Both systems share the high-level design intent ("editorial, serif headline,
classical leading, restrained chrome") but differ on every concrete value
that drives visual identity — palette, body typography, kicker style,
decoration, and cover composition.

### 15.3 Decision

Promote `rejuve-pitch-deck` to **primary** (canonical_source). Demote
`pos-sprint-editorial-example` to **secondary**. Demote `rejuve-presentation`
to **secondary** (alternate sub-style of System A). Keep
`pos-sprint-deck-skill` / `pos-sprint-deck-readme` as **contract-only**
references for assembler-shape (single-file output, slide structure, JS
hooks) but explicitly NOT as visual styling references. Recorded in
`profiles/h2t-editorial/sources/references.yaml::source_conflict`.

### 15.4 Invalidated artifacts

The following T1–T7 outputs are tied to System A and require **rebuild**
before any visual pass:

- T1: `profiles/h2t-editorial/deck/tokens.css` — Playfair+Inter stack and
  terracotta-shaped tokens; rebuild for Playfair+Georgia + gold palette
- T1: `profiles/h2t-editorial/deck/palettes/{default,warm,night}.css`
- T2: every per-layout `*.html` and `*.css` under
  `profiles/h2t-editorial/deck/slides/` (System A typography stack +
  pos-sprint cover composition)
- T3: `profiles/h2t-editorial/deck/frame/frame.css` (1px progress-bar,
  `.eyebrow` shared primitive — pitch-deck uses `.label` and a 2px bar
  + `.rule` decorator)
- T5: `profiles/h2t-editorial/validation/recipe-deck.yaml` (copy lifted
  from pos-sprint slides 1–7; needs to come from pitch-deck)
- T6: mobile @media calibrated to System A type sizes
- Build artifacts: `dist/r2b-h2t-editorial-deck-validation/*` and
  `docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-modular/*` —
  not committed; safe to discard at rebuild time

### 15.5 Preserved artifacts

- Plugin assembler routing (`_is_deck_form_profile` /
  `_assemble_deck_form_v2`) — form-agnostic
- `profiles/h2t-editorial/deck/js/deck-nav.js` — chrome JS contract is
  design-system-agnostic
- 7-layout vocabulary CONCEPT (title / title-body / quote / two-column /
  image-text / divider / final) — System B uses the same conceptual layouts
- Single-file output contract (T4 — independent of styling)
- Source-dossier file (this branch's `references.yaml` — restructured but
  content kept; the conflict is now part of the durable record)
- `known_fidelity_gaps` marker for image-text (still valid: pitch-deck
  carries no `<img>` either)
- Mobile Gate B contract shape (CSS-only, no JS branching)
- Test scaffolding — helpers, parametrized matrices, structural contracts.
  Assertion *values* (font sizes, accent literals, kicker class names) will
  recompute under System B; the contract structure holds.

### 15.6 Rebuild scope (next phase, NOT this batch)

The user explicitly stopped before any rewrite. Rebuild work is staged
for a separate batch under the working name **`rebuild-around-pitch-deck`**:

1. Re-derive `tokens.css` from rejuve-pitch-deck CSS: gold accent, Georgia
   body, slide-padding tokens calibrated to pitch-deck spacing.
2. Replace `.eyebrow` shared primitive with `.label` (pitch-deck kicker
   class). Add `.rule` decorative primitive (40×2 accent rectangle).
3. Rewrite `title.html` as brand-wordmark cover: `.brand` (with
   `<em>` accent fragment) + `.cover-sub` + `.rule` + `.cover-meta`.
   New manifest field set; tests update accordingly.
4. Rewrite per-layout CSS for System B typography (h1 42 / h2 27 / body
   Georgia 16.5 / line-height 1.65).
5. Re-lift validation recipe content from rejuve-pitch-deck slides
   (Russian copy preserved verbatim; no synthetic translation unless human
   provides English source).
6. Re-run T6 mobile coverage with System B base sizes (matrix structure
   unchanged, values recompute).
7. Re-build → re-capture → human visual approval.

### 15.7 Lesson recorded

A secondary source must not silently shape primary visual decisions. When
two source HTMLs visibly disagree on palette, body typography, kicker
class, and cover grammar, the agent must surface the conflict at T0 dossier
review and request human arbitration *before* T1 builds tokens. This is
codified going forward as a pressure scenario in
`plugins/h2t-creative/skills/legacy-fidelity/references/pressure-scenarios.md`
on the rebuild branch.

### 15.8 Known risks (recorded post human-approval, NOT R2b blockers)

These items were surfaced during human visual review (2026-05-07) of the
8-slide validation deck and are accepted as-is for the R2b release. They
are tracked here so a follow-up branch / issue can address them without
blocking the current recovery merge.

**R-1 — `table` layout under long-form cell content**

- **Status.** `table` layout is approved for the current validation
  recipe (pitch-deck slide 10 — "Три компетенции", 3 rows of short
  Russian cell copy with bold leads). Visual verdict PASS at 1440 and
  390.
- **Risk.** Cells with longer copy (multi-clause Russian or English,
  multi-paragraph content, very long unbreakable strings like URLs) may
  wrap heavily on mobile, reduce scan-ability, or trigger horizontal
  overflow. The current implementation uses a single `<table>` on both
  viewports with cell text-wrap and no representation switch.
- **Follow-up scope** (NEW BRANCH, not in R2b):
  1. Author a stress recipe with long-form table cells (6+ rows,
     multi-clause Russian + English mix, mixed `<strong>`/`<em>`/inline
     code emphasis, at least one cell with a long unbreakable token).
  2. Visually verify desktop 1440 + mobile 390 captures.
  3. Decide one of:
     - keep the current `<table>` everywhere (acceptable density
       boundary documented in deck-author guidance);
     - convert mobile to a stacked-card representation, reusing the R2a
       `.table-desktop / .table-mobile` dual-representation pattern
       (assembler `_render_table` already supports this for terminal —
       editorial would need a parallel renderer or a raw-HTML stacked
       template);
     - add an authoring guidance doc capping cell content density.
- **Why not now.** Pitch-deck fidelity at the canonical-content density
  is the R2b release scope. Re-engineering the table for an unknown
  future content density would speculate beyond the canonical reference
  and risk a re-arbitration on a hypothetical use case.

**R-2 — `image-text` layout has no canonical visual reference**

- **Status.** Already documented in
  `profiles/h2t-editorial/sources/references.yaml::known_fidelity_gaps`.
  Layout retains structural test coverage but is excluded from the
  visual gate. Visual deck has 8 slides instead of 9.
- **Risk.** If a future recipe uses the image-text layout with a real
  asset, there is no canonical pitch-deck reference to score the
  visual against. The slide will render structurally but cannot pass
  a fidelity check.
- **Follow-up.** When a real editorial image asset surfaces (rejuve
  client photography, studio diagram, etc.), swap the dossier `stub_*`
  marker for an asset reference and reinstate the image-text slide
  into the validation deck. Update the dossier to remove the
  `parity_gate: excluded` flag at that point.
