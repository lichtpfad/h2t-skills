# R2b — h2t-editorial deck (System B) parity notes

**Date:** 2026-05-07
**Branch:** `codex/r2b-editorial-deck`
**Build:** `dist/r2b-h2t-editorial-deck-system-b-validation/index.html` (single file, 8 slides)
**Captures:** 16 PNGs in `desktop/` + `mobile/` siblings of this file
**Canonical primary:** `docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-golden/rejuve-pitch-deck.html` (System B — luxury-print editorial)

> **Scope.** Agent Visual QA against rejuve-pitch-deck reference visuals after R2b Rebuild Batch 0 (System B contract rewrite), the 2026-05-07 visual-fix batch (image-text excluded; clamp inset + `align-items: center`), and the 2026-05-07 stats+table extension batch (added `stats` and `table` layouts to the 9-layout closed vocabulary, with `stats` and `table` slides lifted from pitch-deck slides 3 and 10). NOT a human visual approval — that is a separate human review step.

---

## Methodology

Each capture was opened via the Read tool (Claude vision) and compared against:
- **rejuve-pitch-deck slide 0 (cover):** brand wordmark + sub + rule + meta — primary visual reference
- **rejuve-pitch-deck slide 1, 4, 5, 8:** per-slide `.label` + h2 + `.rule` + body grammar
- **rejuve-pitch-deck slide 3:** stats grammar (.stat-row + .stat cards with .num/.lbl)
- **rejuve-pitch-deck slide 10:** table grammar (`<table>` + tr.rcu/.ra colour rows + bold strong leads + note)
- **rejuve-pitch-deck `:root`:** palette + typography stack (System B canonical token shape)
- **rejuve-pitch-deck mobile @media:** mobile sizing reference

Classification: **PASS** = matches System B grammar within editorial tolerance · **ISSUE** = visible but non-blocking deviation requiring follow-up · **BLOCKER** = breaks the visual identity vs canonical.

---

## Desktop (1440×900) — 8 slides

| # | Layout | Verdict | Notes |
|---|--------|---------|-------|
| 01 | title (cover) | **PASS** | `RE` (text black) + `juve` (gold #c9a96e em fragment, font-style: normal) Playfair 58px wordmark, `AI REVENUE INFRASTRUCTURE` 13px sans uppercase letter-spaced 3.5, 40×2 gold `.rule` centered, `Апрель 2026 · Confidential` 12px sans dim. Counter `1 / 8` (NO zero-pad). Composition matches pitch-deck cover slide-0. Slide-inner horizontally centered (clamp inset 8vw ≈ 115px gutters at 1440 → wider gutters than literal 80px). |
| 02 | title-body | **PASS** | `01 — ЗАЧЕМ МЫ ЗДЕСЬ` gold `.label` 10.5px sans uppercase letter-spaced 2.5; `Мы не маркетинговое агентство` Playfair h2 27px; 40×2 gold `.rule`; 3 em-dash bullets in Georgia 16.5px body; `revenue-инфраструктуры`, `отсутствия инфраструктуры`, `ваши реальные данные` rendered as `<strong>`. Slide-inner left-aligned within centered editorial column — matches pitch-deck slide-1 grammar. |
| 03 | divider | **PASS** | Centered: `08 — РАЗБОР ОФФЕРА ELPODIUM` gold `.label`, `Где их модель не работает для вашего случая` Playfair h1 42px, 40×2 gold `.rule` centered. Synthesised divider using pitch-deck slide-8 label+h2 pair (no synthetic copy). |
| 04 | quote | **PASS** | `05 — МЕССЕДЖИ` gold `.label`. `Most people are not lacking effort. They are lacking clarity. REjuve is a diagnostic-first functional health studio.` Playfair italic 18.5px with 3px gold left border + faint `var(--accent-soft)` background + 0/5/5/0 border-radius. `— из вашего brand brief` attribution with em-dash gold prefix. Identical pitch-deck `.quote` grammar. |
| 05 | two-column | **PASS** | `04 — КТО ВАШ КЛИЕНТ?` gold `.label`; `Наша гипотеза — нужна ваша валидация` Playfair h2 27px; grid 1fr 1fr with `ГИПОТЕЗА ICP` (h3 sans uppercase letter-spaced 2px dim) + 4 em-dash bullets left, `ЧТО НАШЛИ В ИССЛЕДОВАНИИ` + 3 em-dash bullets right. No `.rule` between h2 and split — faithful to pitch-deck slide-4. |
| 06 | stats | **PASS** | `03 — РЫНОК ЦУГА` gold `.label`; `Это не просто «богатый швейцарский город»` Playfair h2; flex-wrap row of 6 `.stat` cards (white bg, border, rounded 7px, `min-width: 140px`) — each with Playfair 24px gold `.num` (`143`, `~30%`, `900+`, `~19 000`, `+12%`, `+25%`) + dim sans 10.5px `.lbl`; closing dim utility-sans note paragraph with bold inline emphasis. Identical to pitch-deck slide-3 grammar. |
| 07 | table | **PASS** | `10 — ТРИ РАЗНЫЕ ЗАДАЧИ, ОДНО ОКНО` gold `.label`; `Три компетенции.` Playfair h2; 3-column `<table>` (`ЗАДАЧА / КТО ДЕЛАЕТ / КАК ОРГАНИЗОВАНО` th uppercase letter-spaced 1.5 dim); two `.rcu` copper-soft rows (rows 1 + 2: `1. Позиционирование и бренд`, `2. Performance-трафик`) with copper left border on first cell + one `.ra` accent-soft row (row 3: `3. Revenue-инфраструктура` with `Мы` bold) with gold left border; closing note with bold lead `У вас нет времени управлять тремя командами`. Identical to pitch-deck slide-10. |
| 08 | final | **PASS** | Centered: `14 — ПИЛОТ 4 НЕДЕЛИ` gold `.label`, `Один живой результат к концу второй недели` Playfair h1 42px, 40×2 gold `.rule`, `Условия сотрудничества обсуждаются отдельно — не на этой встрече` 14px sans dim subline. Counter `8 / 8`. |

---

## Mobile (390×844 @2x) — 8 slides

| # | Layout | Verdict | Notes |
|---|--------|---------|-------|
| 01 | title (cover) | **PASS** | Wordmark scales to 36px Playfair (mobile override). `.cover-sub` 11px sans letter-spaced 2.5. `.rule` 32px (mobile global). `.cover-meta` 11px sans dim. Counter `1 / 8`. Centered. |
| 02 | title-body | **PASS** | `.label` 9.5px (mobile shrink), h2 21px Playfair, `.rule` 32px gold, 3 em-dash bullets in Georgia 15px (mobile p-size). No horizontal overflow. Padding 24/20/40/20. |
| 03 | divider | **PASS** | h1 26px Playfair (mobile divider override), centered. `.rule` 32px. Composition holds at 390px. |
| 04 | quote | **PASS** | Quote-block: 16px Playfair italic (mobile shrink), 3px gold left border, accent-soft background, padding 10/14. Attribution 11px. `.label` 9.5px gold. |
| 05 | two-column | **PASS** | Grid collapses to single column (`grid-template-columns: 1fr` mobile @media). Both column kickers + bullets readable. **Gate B confirmed.** |
| 06 | stats | **PASS** | `.stat-row` collapses to single-column vertical stack (`flex-direction: column` mobile @media). Each card: gold `.num` 22px Playfair + dim `.lbl` 11px sans. Note paragraph wraps cleanly. **Gate B confirmed.** |
| 07 | table | **PASS** | Table preserves 3 columns; cells text-wrap to multi-line; th 9.5px / td 12px (mobile shrink). Colour rows still visible (`.rcu` copper, `.ra` accent) with left-border accents. Note paragraph wraps below. No horizontal scroll required. **Gate B confirmed.** |
| 08 | final | **PASS** | h1 26px centered, rule 32px, sub 13px sans dim wraps to two lines centered. Counter `8 / 8`. |

---

## System B markers verified across all captures

- **Palette (gold):** `#c9a96e` accent visible on labels / rules / em fragments / progress bar / counter divider / `.num` stat values / `.ra` row background; `#7d4e2d` copper visible on `.rcu` row background+border; `#fafaf8` warm cream background; `#141414` dark ink text. No terracotta `#c45a3c` (System A) anywhere.
- **Typography stack:** Playfair Display (display + h1 + h2 + brand + quote italic + stat .num); Georgia (body p, li); system-ui (utility — counter, label, sub, nav-hint, .lbl, table th/td).
- **Decorative `.rule` primitive:** 40×2 gold rectangle visible on slides 01 (cover, centered, large margin), 02 (after h2), 03 (divider, centered), 08 (final, centered). Mobile widths 32px.
- **`.stat-row + .stat` cards** with `.num / .lbl` triple — pitch-deck verbatim grammar.
- **Table colour rows** `.ra` (accent gold soft), `.rcu` (copper soft) — pitch-deck verbatim grammar; auxiliary palette tokens (`--accent-soft`, `--copper-soft`, `--danger-soft`, `--auto-soft`, `--green-soft`) declared in default/warm/night.
- **Counter format:** `n / 8` (no zero-pad) on every slide. Confirms editorial deck-nav.js System B canonical (replaced R2a `padStart` formatter).
- **Progress bar:** 2px gold thin line at slide bottom, width = `((current+1)/total)*100%`.
- **`align-items: center` on `.slide`:** confirmed visually — slide-inner sits centered horizontally on every desktop slide.

---

## Forbidden patterns absent

Verified via structural inspection of `index.html`:

- ✓ no `repeating-linear-gradient` (scanline overlay — terminal)
- ✓ no `body::after` overlay
- ✓ no `JetBrains Mono`, `monospace`, `Menlo`, `Consolas` font references
- ✓ no `cursor: crosshair`
- ✓ no `mermaid` references
- ✓ no `@keyframes blink`, `animation: blink`
- ✓ no `.code-block`, `.card-row`, `.layer-num` (R2a terminal-only primitives)
- ✓ no `.stat-box / .stat-number / .stat-label` (terminal stat-card variant — System B uses `.stat / .stat .num / .stat .lbl`)
- ✓ no `.eyebrow` (System A primitive — replaced by System B `.label`)
- ✓ no `--font-heading`, `--font-body`, `--font-mono` (System A token names — replaced by `--fh / --fb / --fu`)
- ✓ no `data:image/svg+xml` synthetic placeholder
- ✓ no `placeholder.jpg` literal anywhere

---

## Visual deck composition

The visual validation deck contains exactly 8 slides covering the 8-of-9 visual-gate layouts: title, title-body, divider, quote, two-column, stats, table, final. The image-text layout (9th in the closed vocabulary) is intentionally absent from the visual gate — pitch-deck has no `<img>` assets, so any image-text rendering would show a synthetic placeholder rectangle that the parity gate has no canonical reference to score against. The image-text layout retains its structural test coverage (manifest fields, template HTML, render smoke). The dossier `known_fidelity_gaps` entry in `profiles/h2t-editorial/sources/references.yaml` documents the gap and the visual-gate exclusion.

---

## Tally

|  | desktop | mobile | combined |
|--|---------|--------|----------|
| **PASS** | 8 | 8 | **16 / 16** |
| **ISSUE** | 0 | 0 | 0 |
| **BLOCKER** | 0 | 0 | 0 |

---

## Recommendation

The agent-level visual QA verdict is **all 16 captures match System B canonical (rejuve-pitch-deck) within editorial tolerance**. No issues, no blockers, no synthetic placeholder bleed-through. The two new layouts (`stats`, `table`) lifted from pitch-deck slides 3 and 10 render verbatim against their reference. Ready for human visual review against the same captures + the rejuve-pitch-deck reference HTML opened in a browser side-by-side.

Per the established R2 process and per the user's standing instruction (no agent-side visual pass claims), the **human approval gate remains open** — this report is evidence to support that review, not a substitute for it.

---

## Human visual verdict — 2026-05-07

**Approved for current validation content.** All 8 slides match System B
luxury-print editorial grammar against the rejuve-pitch-deck reference.

### Known risk — recorded, NOT blocking R2b

The `table` layout was visually approved against the *current* validation
recipe lifted verbatim from rejuve-pitch-deck slide 10 ("Три компетенции"
— 3 rows, short Russian cell text). Longer table cell content (multi-line
Russian/English copy, multi-paragraph cells) is NOT covered by today's
visual gate and may degrade on mobile (heavier cell wrapping, harder
scan, possible horizontal overflow with very long unbreakable strings).

**Status:** approved as-is for the current golden content. A long-text
stress test for the table layout is a follow-up item, NOT a release
blocker.

**Follow-up actions** (recorded in plan §15 "Source Arbitration Reset"
known-risks subsection — same plan that records the System A → System B
arbitration):

- author a stress recipe with long-form Russian + English table cells
  (e.g., 6+ rows, multi-clause cells, mixed code/links/em emphasis)
- visually verify the resulting capture at 1440 + 390 viewports
- decide: keep `<table>` semantic on mobile (current), convert to a
  stacked-card representation (R2a `.table-desktop / .table-mobile`
  precedent), or add a max-cell-content guidance to deck-author docs

The current `table` layout uses a real `<table>` on both viewports
(text-wrap inside cells, no representation switch). At pitch-deck-grade
content density this works; at heavy content density a representation
switch may be needed.

---

## Pointers

- Build: `dist/r2b-h2t-editorial-deck-system-b-validation/index.html`
- Captures: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-system-b-modular/{desktop,mobile}/`
- Reference golden: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-deck-golden/rejuve-pitch-deck.html`
- Source dossier: `plugins/h2t-creative/profiles/h2t-editorial/sources/references.yaml`
- Arbitration spec: `docs/superpowers/specs/2026-05-07-r2b-source-arbitration.md`
- Plan: `docs/superpowers/plans/2026-05-07-r2b-h2t-editorial-modularization.md` §15
- Tests: `plugins/h2t-creative/tests/test_r2b_legacy_fidelity_deck.py` (268 passed)
- Open in browser to validate: `file:///C:/dev/h2t-skills-r2b/dist/r2b-h2t-editorial-deck-system-b-validation/index.html`
