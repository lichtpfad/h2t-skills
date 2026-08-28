---
title: "R2b — Source Arbitration Reset (h2t-editorial deck, #87)"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-07"
milestone: ""
issue: ""
---
# R2b — Source Arbitration Reset (h2t-editorial deck, #87)

**Status:** Decision recorded. Rebuild required before any visual pass.
**Trigger date:** 2026-05-07
**Branch:** `codex/r2b-editorial-deck`
**Linked plan:** [`docs/superpowers/plans/2026-05-07-r2b-h2t-editorial-modularization.md`](../plans/2026-05-07-r2b-h2t-editorial-modularization.md)
**Linked dossier:** `plugins/h2t-creative/profiles/h2t-editorial/sources/references.yaml::source_conflict`

---

## 1. Summary

Three goldens were locked at R2b T0 inventory under
`docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-golden/`:

- `pos-sprint-editorial-example.html`
- `rejuve-presentation.html`
- `rejuve-pitch-deck.html`

T1 dossier marked `pos-sprint-editorial-example` as the **primary** target
and treated the two rejuve goldens as **secondary** content references.
T1–T7 implementation built tokens, palettes, layouts, frame chrome, and
mobile rules to honour pos-sprint. After Batch C build + screenshot capture,
human review against the rejuve-pitch-deck reference rejected the result:
the implementation faithfully reproduced pos-sprint *and* missed the human
canonical visual target.

The three sources do **not** form one coherent editorial system. They
encode **two distinct visual systems** (A and B). The canonical target
for `h2t-editorial` is **System B** (rejuve-pitch-deck). T1–T7 was built
for System A and must be rebuilt.

---

## 2. Visual systems detected

### System A — tech-article editorial
**Members:** `pos-sprint-editorial-example`, `rejuve-presentation`

| Aspect            | Value                                                      |
|-------------------|------------------------------------------------------------|
| Background        | `#faf9f6`                                                  |
| Text              | `#1a1a1a`                                                  |
| Text-dim          | `#6b6b6b`                                                  |
| Accent            | `#c45a3c` (terracotta)                                     |
| Border            | `#e0ddd8`                                                  |
| Heading font      | Playfair Display                                           |
| Body font         | **Inter (sans-serif)**                                     |
| Mono font         | JetBrains Mono (rejuve-presentation chrome only)           |
| Token shape       | `--font-heading`, `--font-body`, `--bg`, `--text`, `--accent` |
| Cover grammar     | left-aligned article OR centered Playfair italic subtitle  |
| Decorative `<hr>` | thin border-bottom-style horizontal rule                   |
| Per-slide kicker  | uppercase `.title-eyebrow` / Inter accent letter-spaced    |
| Heading sizes     | h1 ≈ 44–64px, h2 ≈ 30px (Playfair)                         |
| Body              | Inter 16–17px, line-height 1.6                             |

### System B — luxury-print editorial
**Members:** `rejuve-pitch-deck`

| Aspect            | Value                                                      |
|-------------------|------------------------------------------------------------|
| Background        | `#fafaf8` (warmer)                                         |
| Text              | `#141414`                                                  |
| Text-dim          | `#6b6560`                                                  |
| Accent            | `#c9a96e` (gold)                                           |
| Accent-text       | `#8a6520` (darker gold for em + ::before bullets)          |
| Copper            | `#7d4e2d` (secondary accent)                               |
| Border            | `#e2dfd8`                                                  |
| Heading font      | Playfair Display                                           |
| Body font         | **Georgia (serif)**                                        |
| Utility/sans font | system-ui (counter, .label, table chrome)                  |
| Token shape       | `--fh`, `--fb`, `--fu` (heading / body-serif / utility-sans) |
| Cover grammar     | brand wordmark `<div class="brand">RE<em>juve</em></div>` (Playfair 58px, em fragment in accent) + `.cover-sub` (sans 13px uppercase letter-spaced 3.5) + `.rule` (40×2px gold) + `.cover-meta` (sans 12px dim) |
| Decorative rule   | `.rule` — 40×2px gold rectangle, reused as section divider |
| Per-slide kicker  | `.label` — sans 10.5px uppercase letter-spaced 2.5, gold   |
| Heading sizes     | h1 42px, h2 27px (Playfair)                                |
| Body              | Georgia 16.5px, line-height 1.65                           |
| Progress-bar      | 2px gold                                                   |
| Counter           | sans 11px dim, top-right (no zero-pad)                     |

### Why they are not one system

Same design *intent* ("editorial, serif headline, classical leading,
restrained chrome") but different on every concrete value that drives
visual identity:

- accent **terracotta vs gold** — different brand mood
- body font **sans vs serif** — fundamentally different reading texture
- kicker class **`eyebrow` vs `label`** — different DOM contract
- decorative rule **none / hr vs `.rule` 40×2px rectangle** — different
  decorative grammar
- cover composition **left-aligned article vs centered brand wordmark** —
  different opening intent (article-prose vs brand-pitch)

These do not compose. A profile cannot be "both" without becoming
incoherent.

---

## 3. Canonical pick for #87

**`rejuve-pitch-deck` is canonical** (System B — luxury-print editorial).

Reasons:
- The human reviewer's canonical visual reference is rejuve-pitch-deck
  (confirmed via direct screenshot post in the 2026-05-07 review).
- pitch-deck represents the strongest visual identity of the three
  goldens: gold accent + Georgia body + brand-wordmark cover create a
  distinct "luxury-print" feel that system A cannot reproduce.
- pos-sprint is documentation of a *skill spec* (STYLE 2 baseline) rather
  than a chosen production design — useful as a contract reference for
  assembler shape but not as an arbiter of visual identity.

The `profile.yaml::profile = h2t-editorial` is therefore re-anchored on
System B going forward.

---

## 4. Demoted sources

| Source                          | New role          | Notes                                                                                                   |
|---------------------------------|-------------------|---------------------------------------------------------------------------------------------------------|
| `pos-sprint-editorial-example`  | secondary         | System A. Layout-vocabulary catalogue still useful (the 7 layout names hold). Tokens, body font, cover composition NOT canonical.        |
| `rejuve-presentation`           | secondary         | System A. Recipe-content reference (long-form slides at scale). Do not lift its tokens or palette.       |
| `pos-sprint-deck-skill`         | contract-only     | Assembler-shape contract: single-file output, slide structure, JS hooks. NOT a visual-styling reference. |
| `pos-sprint-deck-readme`        | contract-only     | Skill overview only.                                                                                    |
| `rejuve-pitch-deck`             | **primary**       | System B. Authoritative for tokens, palette, typography, cover composition, chrome.                     |

---

## 5. Invalidated R2b T1–T7 artifacts

Tied to System A; rebuild required before any visual pass:

- **T1** — `profiles/h2t-editorial/deck/tokens.css`
- **T1** — `profiles/h2t-editorial/deck/palettes/{default,warm,night}.css`
- **T2** — `profiles/h2t-editorial/deck/slides/title/{title.html,title.css}`
  (cover composition wrong: pos-sprint article vs pitch-deck brand wordmark)
- **T2** — `profiles/h2t-editorial/deck/slides/title-body/*` (h2 + body typography)
- **T2** — `profiles/h2t-editorial/deck/slides/quote/quote.css`
- **T2** — `profiles/h2t-editorial/deck/slides/two-column/two-column.css`
- **T2** — `profiles/h2t-editorial/deck/slides/image-text/image-text.css`
- **T2** — `profiles/h2t-editorial/deck/slides/divider/divider.css`
- **T2** — `profiles/h2t-editorial/deck/slides/final/final.css`
- **T3** — `profiles/h2t-editorial/deck/frame/frame.css` (1px progress-bar,
  `.eyebrow` primitive — pitch-deck uses 2px bar + `.label` + `.rule`)
- **T5** — `profiles/h2t-editorial/validation/recipe-deck.yaml` (copy lifted
  from pos-sprint slides 1–7 — replace with pitch-deck content)
- **T6** — mobile `@media` blocks calibrated to System A sizes (the matrix
  structure holds; the values recompute under System B)
- **Build outputs (uncommitted, safe to discard at rebuild):**
  - `dist/r2b-h2t-editorial-deck-validation/`
  - `docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-modular/`
    (14 captured screenshots — not visual evidence)

---

## 6. Preserved artifacts

These do not depend on the visual system and survive the reset:

- **Assembler routing** — `assembler.py::_is_deck_form_profile` and
  `_assemble_deck_form_v2`. Form-agnostic. Tests under T4 stay green.
- **`deck/js/deck-nav.js`** — chrome JS contract is design-system-agnostic
  (`window.showSlide`, keyboard / touch / hash sync, counter zero-pad
  behaviour). Note: pitch-deck does not zero-pad the counter; the JS
  contract may need an opt-out flag at rebuild time. Not a blocker.
- **Layout vocabulary CONCEPT** — the seven layouts (title / title-body /
  quote / two-column / image-text / divider / final) all map to slides
  pitch-deck actually contains; the names hold.
- **Single-file output contract (T4)** — independent of styling.
- **Source-dossier file** — restructured to record the conflict; kept.
- **`known_fidelity_gaps` for image-text** — pitch-deck also has no `<img>`
  assets, so the gap remains valid.
- **Mobile Gate B contract shape** — CSS-only, no JS branching. Holds.
- **Test scaffolding** — helpers (`_strip_css_comments`, `_iter_rules`,
  `_extract_media_blocks`), parametrized matrices, structural assertions
  (single-file, inline CSS/JS, no terminal patterns, mobile breakpoint
  presence). Assertion *values* recompute under System B; structure stays.

---

## 7. Rebuild plan (separate batch)

Per human direction the rebuild work is **not** in this batch. Staged
under the working name **`rebuild-around-pitch-deck`**:

1. **tokens.css** — derive from rejuve-pitch-deck:
   - palette: gold + copper + dim copper-text
   - typography: `--fh` Playfair, `--fb` Georgia, `--fu` system-ui
   - slide-padding tokens calibrated to pitch-deck spacing
2. **frame.css** — replace `.eyebrow` with `.label`. Add `.rule`
   decorative primitive (40×2 gold). Bump `#progress-bar` to 2px.
   Counter typography: sans 11px dim, no zero-pad if compatible with JS.
3. **title.html / title.css** — brand-wordmark cover. New manifest:
   `brand_text` (with `accent_fragment`), `cover_sub`, `cover_meta`.
   Update T2 tests for new field set.
4. **Per-layout CSS** — System B sizes (h1 42, h2 27, Georgia 16.5).
5. **validation/recipe-deck.yaml** — re-lift content from rejuve-pitch-deck
   slides verbatim. Russian preserved if no English source available.
6. **T6 mobile** — recompute size scale under System B base.
7. **Build → capture → Agent Visual QA → human approval.**

---

## 8. Process lesson

Codify in `plugins/h2t-creative/skills/legacy-fidelity/references/pressure-scenarios.md`
on the rebuild branch:

> **Source conflict at T0 dossier:** When goldens disagree on palette,
> body typography, kicker class, or cover composition, the agent must
> surface the conflict during T0 dossier review and request human
> arbitration *before* T1 starts building tokens. A "secondary" source
> cannot silently override primary visual decisions, and the agent
> cannot resolve a visual-identity conflict on its own — that is a human
> arbitration decision. Marker for detection: any pair of goldens whose
> CSS `:root` blocks differ on `--accent` hex, body `font-family`, or
> brand-wordmark vs article cover composition.

---

## 9. Stop

Per Source Arbitration Reset scope: no CSS fixes, no further screenshots,
no commits in this batch. This document + the dossier `source_conflict`
block + the plan §15 amendment are the entirety of the deliverable.
Rebuild starts only on explicit human go-ahead.
