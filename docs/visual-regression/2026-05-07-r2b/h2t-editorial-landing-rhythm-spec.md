# h2t-editorial landing — rhythm spec

**Date:** 2026-05-07
**Phase:** R2b #88 — Landing Composition System Extraction (post Intent Reset, post composition-spec failure)
**Branch:** `codex/r2b-editorial-landing`
**Status:** DRAFT — awaiting human approval before recipe v2

---

## 0. Why this spec exists

Three artifacts already define **what primitives exist**:

- `landing-references.yaml` — locked source dossier (T0.5 arbitration verdict)
- `h2t-editorial-landing-design-system.md` — closed primitive vocabulary (T2 extraction)
- `h2t-editorial-landing-composition-spec.md` — block inventory (10 + CTA)

None of them define **how a page reads**. The Batch C and post-Intent-Reset captures both showed the same drift — formally correct primitive classes, but the page renders as "primitive showcase" rather than as a landing. Component tests pass; visual reading fails.

The missing layer is **rhythm + hierarchy + density budget**. For deck this is implicit (slide-by-slide composition is rigid). For landing it must be explicit.

This spec defines that layer.

Three inputs feed it:

1. **`profiles/h2t-editorial/DESIGN.md`** — the original editorial brand intent: Playfair headlines, Inter body, terracotta accent, generous whitespace, large leading, book-like aesthetic.
2. **Locked landing goldens (`rejuve-appendix-competitive-report.html`, `rejuve-appendix-elpodium-decomposition.html`)** — System B-Landing rhythm: 14 px body, `max-width:1100px`, `padding:28px 32px`, `.section{margin-bottom:36px}`, dense report layout.
3. **Failed landing screenshot (`docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-modular/unknown/desktop_20260507_211611.png`)** — what NOT to produce: 5 dense grids back-to-back, no first screen, table without narrative context, tab strip without real tabs, stats as floating numbers without contextual proof.

The brand identity (DESIGN.md) and the recovered system (goldens) describe **two different aesthetic positions** for the same profile. Both must be honoured: the goldens supply the recovered visual system; the brand intent supplies the landing-shaped composition discipline that the appendix goldens do not need.

---

## 1. Page rhythm — measured baseline

Lifted directly from
`rejuve-appendix-competitive-report.html` `<style>` block. These
metrics ARE the System B-Landing rhythm; the landing must inherit them
unchanged so the form reads as one product family.

| Metric | Value | Source |
|---|---|---|
| `body` background | `var(--bg)` (`#fafaf8`) | golden line 21 |
| `body` color | `var(--tx)` (`#1a1a18`) | line 21 |
| `body` font-family | `var(--sans)` (`-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif`) | line 21 |
| `body` font-size | **14 px** | line 21 |
| `body` line-height | **1.6** | line 21 |
| `.page` (and body equivalent) max-width | **1100 px** | line 30 |
| `.page` padding | **28 px / 32 px** (vertical / horizontal) | line 30 |
| `.page` centering | `margin: 0 auto` | line 30 |
| `h1` font / size / colour | `var(--serif)` Playfair · **28 px** · `var(--ad)` (`#8a6520`) | line 34 |
| `h1` margin-bottom | 6 px | line 34 |
| `h2` font / size / colour | `var(--serif)` Playfair · **20 px** · `var(--ad)` | line 35 |
| `h2` margin | **28 px above · 12 px below** | line 35 |
| `h3` font / size / colour | sans bold · **14 px** · `var(--tx)` | line 36 |
| `h3` margin-bottom | 6 px | line 36 |
| `.ph` block | flex baseline, gap 16 px, margin-bottom **24 px**, padding-bottom **16 px**, border-bottom 1 px `var(--bd)` | line 39 |
| `.section` | `margin-bottom: 36 px` (no padding, no background — pure rhythm spacer) | line 44 |
| `.card` | bg `var(--sf)`, 1 px border `var(--bd)`, radius `var(--r)` (6 px), padding **16 px** | line 47 |
| `.g2` gap | 16 px | line 50 |
| `.g3` gap | 16 px | line 51 |
| `.g4` gap | 12 px | line 52 |
| `.stat` | bg `var(--sf)`, padding **14 / 16 px**, centred | line 55 |
| `.stat-n` | Playfair **26 px** `var(--ad)`, line-height 1.1 | line 56 |
| `.stat-l` | sans **11 px** `var(--mu)`, line-height 1.4 | line 57 |
| `.bt` table | width 100 %, font-size **12 px** | line 84 |
| `.bt th` | bg `var(--sf)`, 1 px border, padding **8 / 10 px**, font 11 px bold `var(--ad)` uppercase | line 85 |
| `.bt td` | 1 px border, padding **8 / 10 px**, vertical-align middle | line 86 |

**Brand-intent override.** DESIGN.md asks for `--font-display:Playfair`
and `--font-body:Inter` with leading 1.75+. The goldens use Playfair for
headings (consistent) and **system-ui sans** for body at line-height
1.6 (divergent — denser than DESIGN.md). The landing inherits the
goldens' values because DESIGN.md was written for an older editorial
profile and the recovered System B is the canonical one (per T0.5
arbitration). DESIGN.md is updated to reflect this in the next slice.

---

## 2. Landing hierarchy

### 2.1 First-screen contract (above the fold at 1440×900)

**Mandatory.** A real editorial hero — not chrome, not admin text.

The hero block must be the FIRST visible content (no tab strip above it,
no helper text). Above-the-fold composition:

| Position | Element |
|---|---|
| 0–80 px from top | nothing — page padding only |
| 80–340 px | hero band: h1 (28 px Playfair) + lede paragraph (≤ 30 words, 14 px) + ONE quiet kicker line above h1 (`.ph-meta` style — 12 px `var(--mu)`) |
| 340–640 px | one supporting beat: a single proof primitive (`.stat × 3` strip OR one `.card-grid g3` of three short proof cards — NOT both) |

**Forbidden above the fold:**
- Sticky tab strip (`.tabs`) unless the landing actually has multiple real top-level pages — single-tab `.tabs` = visual lie.
- Admin / helper text such as "Form: Landing", "validation", build-system labels.
- More than one primitive type before the lede paragraph.

### 2.2 Body hierarchy

A landing has at most **6 main sections** between hero and CTA:

| Position | Block | Density |
|---|---|---|
| 1 | Hero (see §2.1) | 1 primitive + lede |
| 2 | First proof beat | 1 primitive |
| 3 | Narrative section (`.section h2` + ≤ 60 words prose) | TEXT only, no grids |
| 4 | Comparison block (`.bt` ≤ 4 × 4 OR a `.mmap` 2 × 2) — **never both** | 1 primitive |
| 5 | Process / sequence (`.flow`, ≤ 5 steps) OR a second narrative section | 1 primitive |
| 6 | Close-narrative (`.section h2` + ≤ 40 words, optional 1-line evidence link) | TEXT only |
| 7 | `editorial-cta` (Amendment A — composition spec §4 row 10.5) | the only conversion primitive |

**Hard cap.** Total non-CTA blocks: **≤ 6**. Total recipe sections including CTA: **≤ 7** (under the previous spec's 10-block budget — the 10-block target was what produced the showcase). Recipe-level test must enforce this.

### 2.3 What "no admin text above h1" means in practice

The Batch C build had `Form: Landing` in a tab strip above h1 and
`R2b · slice #88 · System B-Landing modular` in `.ph-meta` next to h1.
Both are admin-y. The landing reads to a reader, not a maintainer.
Replace with copy that is meaningful to the reader:

- `.ph-meta` slot: a short editorial-meta line (date, edition, author) — same shape as goldens use.
- No build-system metadata in visible HTML. If audit info is needed, put it in an HTML comment (`<!-- slice #88 · 2026-05-07 -->`) or in the `<title>`.

---

## 3. Primitive roles — landing-specific

Same primitives as composition spec §3, but with **explicit role each plays in a landing**, distinct from how the same primitive is used in an appendix.

| Primitive | Landing role | Appendix role (rejected here) |
|---|---|---|
| `.tabs / .page` | **Brand chrome ONLY when there is real multi-page navigation.** A single tab is visual debt. If there's only one page, omit the tabs primitive entirely. | Section pivots between Overview / Cards / Matrix / Signals — multi-tab navigation is the natural appendix shape. |
| `.ph` | **Compact editorial header** placed above the hero (`<h1>` + 1-line meta). Always carries the page's identity, never chrome. | Same shape; appendix uses it per-tab as the active page header. |
| `.section` | Pure rhythm spacer (`margin-bottom:36px`). Wraps an h2 + content. Use ONLY where a real h2 break is meaningful. **Do NOT wrap every primitive in `.section`** — that flattens hierarchy. | Wraps every block in the appendix because the appendix is uniformly section-paced. |
| `.card / .g3` | **Proof blocks.** Three short, parallel claims. Each card = h3 + ≤ 35 words. Never used to host primitives — a card with a table inside is a category mistake. | Mostly used for prose summaries between heavier primitives. |
| `.stat / .stat-n` | **Compact proof, ≤ 3 stats max.** Numbers must be reader-meaningful (not internal counts like "545 contract tests"). One stat strip per landing. | Hero KPI dashboards; the appendix can stack `.funnel` + `.g2 fn-detail` because that IS its content. Landing cannot. |
| `.bt` (`.comparison-table`) | **Focused comparison, max 4 rows × 4 cols.** Always preceded by an h2 narrating what the comparison answers. Row coloring `.rejuve` for the highlight row only — no `.deep / .w1-3` on a landing. | 10-row × 8-col sweeps with mixed row coloring; analyst-grade density. |
| `.flow` | **Process block, 3–5 steps.** Each step ≤ 25 words. Use to compress a multi-step narrative into one visual unit. | 6-step customer journey spanning 1–4 weeks of behaviour. |
| `.mmap` (`market-map cells`) | **Categorisation block, 4 cells max.** ALTERNATIVE to `.bt` — pick one per landing, not both. | Used per-section as a categorisation layer alongside other primitives. |
| `.pos-grid` | **Differentiation cards, 4 max.** Allowed once. ALTERNATIVE to `.card-grid g3` — overlaps in role. Pick one per landing. | Used as an additional layer below `.mmap` and above `.bt`. |
| `editorial-cta` | **The only conversion primitive.** Always the last block. Composition spec §4 row 10.5 visual grammar. | Not in goldens — landing-only. |
| `.dt / .proh-tbl / .wave-block / .comp-box / .disc / .meta-box / .funnel / .ck` | **Forbidden in landing recipe.** Appendix-only primitives. (Already enforced in §LT-9.) | Their natural habitat. |

---

## 4. Forbidden composition patterns

These patterns explain WHY the post-Intent-Reset build still failed.
Each one is a category-level mistake the recipe author can make even
while satisfying the previous spec.

### 4.1 Primitive showcase

> "Every primitive must appear at least once" → recipe ends up as a tour
> of primitives rather than a page that says something.

**Rule.** Recipe v2 includes ONLY the primitives that the landing
actually needs (max 6 of them). It does NOT need to exercise all 16
recovered primitives. The validation that all primitives RENDER lives
elsewhere — at the per-component test level (§LT-3 .. §LT-7). The
landing does not need to prove the primitive set is exhaustive.

### 4.2 Multiple dense grids back-to-back

> `card-grid g3 → stats g3 → mmap g2 → pos-grid g2` produces visual
> noise: four grid bands at the same vertical density with no
> contrast.

**Rule.** Between any two grid-style primitives there must be EITHER:
- a narrative `.section` (h2 + prose) acting as a breathing space, OR
- a primitive of a different shape (e.g. `.flow` linear vs grids; `.bt`
  table vs grids).

A landing recipe must not stack ≥ 2 grid primitives without an
intervening non-grid block.

### 4.3 Table before narrative context

> A comparison table that appears mid-page with no h2 explaining what
> the comparison answers reads as a data dump.

**Rule.** Every `.bt` and every `.mmap` is preceded by EITHER a
`.section h2` + 1-sentence intro paragraph, OR by an `.ph` if the table
IS the hero supporting beat. Naked tables are forbidden.

### 4.4 Tabs as navigation without real tabs

> A single tab labelled "Form: Landing" reads as broken navigation.

**Rule.** Use `.tabs` ONLY when the landing has ≥ 2 real top-level
pages. Otherwise omit. The brand identity signal does NOT depend on the
tab strip — it depends on Playfair + gold + cream + 14 px density.

### 4.5 Stats as internal counts

> "545 contract tests passing" is reader-irrelevant. The landing reader
> does not run `pytest`.

**Rule.** Every `.stat-n` value must be meaningful to the landing's
target reader (DESIGN.md / brand-stakeholder context). Internal-only
metrics belong in audit trail markdown, not visible HTML.

### 4.6 Footer rendered as `.section`

> An `.section h2 "Audit trail"` at the bottom inherits the same h2
> typographic weight as primary sections, breaking hierarchy.

**Rule.** Audit / footnote content goes into a small muted block at the
end OR into the `editorial-cta__secondary` link slot. No `.section h2`
for closing-meta content.

---

## 5. Table rule — desktop vs mobile

### 5.1 Desktop

Use `.bt` directly (verbatim from goldens). Cap **≤ 4 rows × 4 cols**.
Single highlight row using `.rejuve` class. No row coloring beyond
that.

### 5.2 Mobile (Amendment B — in scope per composition spec)

A 4-col `.bt` at 390 px viewport produces either horizontal scroll or
unreadable cell text. Both fail mobile acceptance from composition
spec Amendment B (no horizontal overflow, no clipped/unreadable text).

**Rule.** The landing comparison block uses **dual-representation**
(R2a precedent — `_render_table` in assembler.py + `.table-desktop /
.table-mobile` toggle in deck form). For landing this means:

- Both representations live in the DOM at all times (no JS branching).
- Desktop CSS shows `.bt` (table) and hides `.bt-cards` (stacked card
  list).
- Mobile CSS (`@media (max-width:480px)` in the comparison-table
  component CSS) hides `.bt`, shows `.bt-cards`.
- Each `.bt-card` = one row of the table rendered as a small `.card`
  variant: header (first column value as h3), then dl/dt/dd pairs for
  remaining columns.
- Recipe content is provided ONCE; the assembler (or the component
  template) emits both representations from the same data.

This is the ONLY mobile-specific representation switch admitted by
the rhythm spec. All other primitives must reflow naturally.

A new variant test (`§LT-10` in the next slice) enforces:

- comparison-table CSS contains both `.bt` and `.bt-cards` rules.
- mobile media query `@media (max-width:480px)` toggles them.
- recipe `comparison-table` content shape is unchanged from current
  contract (`thead_html`, `tbody_html`) — backward compatible.

If the dual-representation is too heavy for this slice, the alternative
is to drop `.bt` from the landing entirely and use `.mmap` instead
(which is already grid-based and reflows cleanly). Decision in §6.

---

## 6. Landing v2 wire order — proposal

Eight blocks total. All other primitives are admitted only if the
human approves a specific replacement.

| # | Block | Primitive | Density / Cap | Required |
|---|---|---|---|---|
| 1 | **Editorial hero** | `.ph` only (no `.tabs`) | h1 (28 px Playfair) + meta line + ≤ 30-word lede (in a `.section` body, no h2) | Yes |
| 2 | **Proof beat** | one of: `.stat × 3` strip OR `.card-grid g3` (3 cards) — **pick one** | 3 instances; each card / stat ≤ 35 words / ≤ 1-line label | Yes |
| 3 | **Narrative section** | `.section h2 + p` | h2 + ≤ 60 words prose, NO primitives inside body | Yes |
| 4 | **Categorisation** | one of: `.mmap` 2 × 2 OR `.pos-grid` 2 × 2 — **pick one** | 4 cells; each cell ≤ 25 words | Yes |
| 5 | **Comparison or process** | one of: `.comparison-table` 4 × 4 (with `.bt-cards` mobile fallback per §5.2) OR `.flow` 4–5 steps | one primitive only; preceded by a 1-sentence intro paragraph | Yes |
| 6 | **Close-narrative** | `.section h2 + p` | h2 + ≤ 40 words; optional 1 inline evidence link | Yes |
| 7 | **Editorial CTA** | `editorial-cta` | composition spec §4 row 10.5 contract | Yes |
| (8) | **Footer micro-meta** | small `<p style="font-size:11px;color:var(--mu);text-align:center">…</p>` — NOT a `.section` block | one line, ≤ 20 words, audit links allowed here | Optional |

**Decision points for human:**

- **D1.** Block 2: stats vs card-grid? *Recommended:* card-grid (three
  named claims read more landing-shaped than three numbers). Stats are
  a stronger "proof beat" but only when the numbers are reader-relevant.
- **D2.** Block 4: mmap vs pos-grid? *Recommended:* pos-grid
  (differentiation-style is more landing-shaped than market-map-style
  for a product page).
- **D3.** Block 5: comparison-table vs flow? *Recommended:* flow
  (avoids the dual-representation engineering cost; comparison-table
  becomes a future slice when assets justify it). If comparison-table
  is chosen, §5.2 dual-representation must be implemented in the same
  slice.
- **D4.** Footer micro-meta block 8 — include or omit? *Recommended:*
  omit; let the secondary link of `editorial-cta` carry the audit
  pointer.

---

## 7. Test surface (next slice — NOT this one)

Tests that codify this rhythm spec land in the next slice as `§LT-10
Rhythm contract`:

- R1. Recipe non-CTA section count ≤ 6.
- R2. Hero block (first non-tabs section) is `page-header` and the
  preceding section is NOT `tabs` (single-tab forbidden).
- R3. No two adjacent `card-grid / stats / mmap / pos-grid` sections in
  the recipe (anti-stack rule §4.2).
- R4. `comparison-table` and `mmap` are mutually exclusive (pick one
  per recipe per §6 D2).
- R5. Every `comparison-table` and `mmap` is preceded by a `section`
  with non-empty `body` (§4.3 narrative-context rule).
- R6. `stats` content has no admin keywords (`tests`, `passing`, `LOC`,
  `CSS`, `commits`, `slice`) — anti-internal-counts rule §4.5.
- R7. Footer is NOT a `section` block (§4.6).
- R8 (if §6 D3 picks comparison-table). `comparison-table.css`
  contains `@media (max-width:480px)` and a `.bt-cards` rule.

These DO NOT land now. The current slice's job is to land the spec.

---

## 8. What is OUT of scope for this spec

- Recipe v2 implementation (next slice).
- New components (no new components are needed; rhythm is a recipe-shape
  + per-component-CSS responsibility).
- The dual-representation comparison-table (admitted as a future slice
  if §6 D3 picks it; otherwise out of scope entirely).
- Updating DESIGN.md to reflect System B-Landing canonical typography
  (separate housekeeping commit).

---

## 9. Approval gate

This spec is **DRAFT** until the human:

1. Confirms or amends §6 wire order (block selection + the four
   D-decisions D1–D4).
2. Confirms §2.2 hard cap (max 6 main sections + CTA).
3. Confirms §5 table rule (dual-representation if `.bt` is in;
   otherwise drop `.bt`).
4. Greenlights the next batch (recipe v2 + fresh build path
   `dist/r2b-h2t-editorial-landing-v2/` + capture).

Until that approval lands as a recorded "approved 2026-05-NN by
{human}" line at the top: NO recipe rewrite, NO new build, NO
screenshots.

---

## 10. References

- Plan amendment: `docs/superpowers/plans/2026-05-07-r2b-h2t-editorial-modularization.md` §16.
- Composition spec (block inventory): `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-composition-spec.md`.
- Primitive vocabulary (T2 extraction): `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-design-system.md` §10.
- Source dossier: `plugins/h2t-creative/profiles/h2t-editorial/sources/landing-references.yaml`.
- Brand intent (older editorial profile, pre-System B): `plugins/h2t-creative/profiles/h2t-editorial/DESIGN.md`.
- Failed landing capture: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-modular/unknown/desktop_20260507_211611.png` (this spec's primary anti-evidence).
- Batch C frozen evidence: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-system-b-modular/EVIDENCE.md`.

---

# Appendix A — Landing v0 Block Standard (profile-agnostic)

**Status of this appendix:** triangulated 2026-05-08 against an
independent research run (h2t:research-agent, 19 sources, exa-ai
adapter — see `C:/Users/<user>/.h2t/research/h2t-creative-landing-block-
taxonomy-mobile-2026-05-07.sources.json`). The user-supplied initial
synthesis (Baymard + Leadpages, 4 sources) was **mostly confirmed**
with three additions and one demotion. Diff vs user hypothesis is in
§A.0a; full citation-backed taxonomy is in §A.1; the surfaced
decisions are in §A.9.

The appendix separates the **profile-agnostic landing vocabulary**
(this appendix — applies to any h2t-creative landing) from the
**editorial-specific rhythm + primitive roles** (§1–§7 above —
applies only to h2t-editorial / System B-Landing).

The two layers stack: a recipe author first satisfies the v0 standard
(below), THEN the editorial rhythm rules (above). When the recipe
violates either, the visual gate fails for a different reason — both
gates are needed.

## A.0a Research diff vs user hypothesis

**Confirmed (consensus across NN/g + Kleos + Replo + Unbounce + Growform):**

- Required set `hero / proof / features / comparison-or-process / cta` is supported by 4+ independent sources.
- 5–7 blocks density rule confirmed by Landerlab ("clutter = mistake #1") + Templately + NN/g "Keep Homepages Simple".
- Mobile-representation-declared-up-front rule confirmed by NN/g page-fold-manifesto: *"a responsive design may have 2, 3, 4, or more different folds, specific to the devices"* — folds are designed per-device, not discovered at QA.
- Comparison → cards on mobile is full consensus (NN/g mobile-tables + UX Movement + Foolproof). Horizontal scroll on mobile = anti-pattern.
- Hero compresses to one message on mobile (Woobox: "headlines that fit one line on desktop wrap to four on a phone").

**Added (research surfaced; user hypothesis missing):**

- **`problem` framing as separate Required block.** Kleos 8-block CRO study: dropping problem framing is part of the "missing 3+ sections" delta — landings with the full 8 blocks ran 5.2% median CVR vs 1.8% for landings missing 3+. User's `evidence` block does not cover this distinct copy role.
- **`footer_proof` as universal Required slot, distinct from top `proof`.** Kleos splits social-proof (logos/ratings near hero) and footer-proof (credibility/security/team near close) as TWO Required roles. User had one `proof` block.
- **`faq` as Required for objection-handling, separate from `comparison-or-process`.** Different mobile representation (accordion vs cards-or-vertical-flow) and different conversion role (objection close vs feature explanation).
- **`sticky_cta: bool` flag on the cta block.** Online Dialogue 33-test meta + Convertica 252% mobile lift case — sticky-bottom CTA produces measurable mobile conversion uplift, but ONLY in transactional contexts (cart, checkout, signup). Flag is OFF by default; landing recipe sets it explicitly when applicable.
- **`navigation` as Conditional (not Required, not Optional).** Required for full homepages (NN/g top-ten guidelines). Optional / omit for dedicated campaign LPs (Unbounce — distraction-free conversion). Recipe declares it explicitly per landing kind.

**Contradicted:**

- User listed `evidence` (sources/footnotes) as Required. No consensus source treats evidence as universally Required — it's either folded into `footer_proof` (Kleos) or treated as profile-specific (NN/g credibility principle for editorial/educational sites only). **Demote `evidence` to profile-specific Required** (Required only for h2t-editorial-style profiles where credibility-via-citation IS the brand promise; Optional for marketing/product profiles).

## A.1 Required vs optional semantic blocks (research-validated)

Roles, not primitives. A landing recipe declares `role:` per section;
the profile-specific rhythm spec maps the role to a primitive. Each
row carries the source(s) that establish it as Required / Conditional /
Optional.

### Required (universal — applies to every h2t-creative landing)

| Role | Desktop expectation | Mobile expectation | Anchor sources |
|---|---|---|---|
| `hero` | headline + subhead + primary CTA + optional media | one main message; media demoted below or omitted; CTA visible above the fold | NN/g [scrolling-and-attention](https://www.nngroup.com/articles/scrolling-and-attention-original-research/); Replo, Unbounce, Growform, Woobox |
| `proof` (top social-proof) | 3–4 KPI / logos / ratings horizontal | stack OR 2 × 2; no horizontal carousel | Kleos [landing-page-anatomy](https://kleos.cloud/signal/landing-page-anatomy-sections-that-convert/); Growform |
| `problem` framing | short paragraph or icon row | single column, terse | Kleos (8-block CRO study — dropping costs CVR points) |
| `solution` / value prop | visual + copy paired | stacked, copy first | Kleos; Replo; Unbounce |
| `features` | 3–6 cards in grid | single column; cap ~3 cards before fatigue | Replo, Growform, Unbounce; Woobox mobile-fatigue cap |
| `comparison` OR `process` | compact comparison-table / compare-grid OR horizontal/stepped flow | comparison → cards (no horizontal scroll); flow → vertical timeline | NN/g [mobile-tables](https://www.nngroup.com/articles/mobile-tables/); UX Movement; Foolproof |
| `faq` (objection handling) | accordion or list | accordion (single column) | Kleos (Required); Replo |
| `cta` (final action block) | distinct full-width contrasting section | full-width readable button; **`sticky_cta: bool`** flag for transactional pages | Kleos; Unbounce; Online Dialogue + Convertica (sticky lift) |
| `footer_proof` | compact credibility row (links, fine print, team/security) | same; tap targets ≥ 44 px | Kleos (split from `proof`); Growform |

### Conditional

| Role | Required when | Omit when | Anchor sources |
|---|---|---|---|
| `navigation` | full homepage / multi-page site | dedicated single-purpose campaign LP (distraction-free conversion) | NN/g top-ten guidelines; Unbounce |

### Optional

| Role | Trigger to include | Anchor sources |
|---|---|---|
| `gallery` | landing has a curated visual collection | Replo, Unbounce |
| `video` | product demo or testimonial video; requires poster | Replo |
| `testimonials` | quotable third-party endorsements available (separate from logo `proof`) | Replo, Unbounce |
| `pricing` | the landing converts on transactional intent | Replo, Unbounce |
| `evidence` | **profile-specific** — Required for editorial/educational profiles where credibility-via-citation IS the brand promise; Optional otherwise | NN/g credibility principle (profile-conditional) |

Every optional and conditional block carries the same desktop / mobile
contract pattern as the required blocks — declared in the role's slot
in the recipe, not invented at recipe-rewrite time.

## A.2 Density rule (research-validated)

**A landing validation recipe must NOT be primitive coverage.** It
contains **5–7 semantic blocks**, with **at most one dense block**
("dense" = a block carrying ≥ 5 sub-elements: a 5+-row table, a 6+
card grid, a 5+-step flow). The closed primitive vocabulary from T2
exists to be *available*, not to be exhausted on every landing.

Anchor sources:

- Landerlab [10 common LP mistakes](https://landerlab.io/blog/10-common-landing-page-mistakes) names "cluttered and overwhelming design" as **mistake #1**.
- Templately [visual-clutter](https://blog.templately.com/visual-clutter-on-a-website-and-how-to-fix-it/): *"visual clutter… silently killing your website's performance, driving visitors away, destroying trust and tanking your conversions"*.
- NN/g [keep-homepage-simple principle](https://www.nngroup.com/articles/homepage-design-principles/) supports the same ceiling.

**Tension with research consensus.** Kleos's measured 8-block model
(hero / social-proof / problem / solution / features / objections /
final-CTA / footer-proof) sits ABOVE the 5–7 cap. If the landing wants
to maximise CVR by Kleos's evidence (5.2% with all 8 vs 1.8% missing
3+), the cap relaxes to **6–8 main + CTA**. See §A.9 D5 for the
decision.

This rule complements §2.2 (≤ 6 main + CTA) and is stricter on the
"exhaust the vocabulary" failure mode. Both rules apply, with the
A.9 D5 outcome reconciling the cap.

## A.3 Mobile rule (research-validated)

**Every semantic block must declare its mobile representation BEFORE
visual QA.** A block's mobile representation is recorded in the recipe
section content (as a short metadata field or as a comment) and
encoded in the component CSS as either:

- natural reflow (column → stack, no special CSS), OR
- explicit `@media (max-width:480px)` rule producing a different
  representation (e.g. `.bt` → `.bt-cards`).

Visual QA never discovers mobile representation — it confirms the
declared one. If a block has no declared mobile representation, the
recipe is not ready for the visual gate.

Anchor sources:

- NN/g [page-fold-manifesto](https://www.nngroup.com/articles/page-fold-manifesto/): *"a responsive design may have 2, 3, 4, or more different folds, specific to the devices"* — folds are designed per-device, not discovered.
- NN/g [scrolling-and-attention](https://www.nngroup.com/articles/scrolling-and-attention-original-research/): only ~20% of attention goes below the fold — above-the-fold value is binding on mobile too.
- Woobox [mobile-landing-page-optimization](https://woobox.com/articles/mobile-landing-page-optimization): *"viewport is roughly 390 pixels wide and 600–700 pixels tall… headlines that fit one line on desktop wrap to four on a phone"* — confirms 390 px target and the headline-wrap failure mode.

### Sticky CTA (mobile-only behavior)

`cta` block carries a `sticky_cta: bool` flag. When `true`, mobile CSS
adds a sticky-bottom rendering of the primary action. Default `false`.

Anchor sources:

- Online Dialogue [sticky-CTA meta-analysis](https://www.onlinedialogue.nl/en/blogs/sticky-cta-guaranteed-conversion-uplift/): 33-test review — *"use a sticky element on mobile devices, at the bottom of the screen, and only in the cart or check-out"*. Sticky-everywhere ≠ uplift.
- Convertica [e-commerce sticky-CTA case study](https://convertica.org/ecommerce-case-study-sticky-cta/): documented **252% mobile conversion lift**.

For the h2t-editorial landing slice (no transactional intent — the
landing converts on "open the deck PR"), `sticky_cta: false` is the
default and recommended setting. The flag exists for future profiles
that DO have transactional intent.

The implication for this slice: §5 table rule is the FIRST instance of
this contract. The `comparison-table` component must ship `.bt-cards`
+ `@media` toggle BEFORE the recipe v2 capture, OR the recipe v2 must
omit `.bt` and use `.flow` (per §6 D3 recommendation).

## A.4 Comparison primitive — landing vs report (formalised)

The Baymard mobile-list research empirically supports §3's primitive-
role table for `.bt`:

> Mobile users need enough information to compare items, but the small
> screen makes element comparison difficult. — Baymard mobile
> product-list research

This translates into a hard rule:

| Page kind | Desktop comparison | Mobile comparison |
|---|---|---|
| **Landing** | compact table (`.bt`) OR compare-grid (`.card-grid g3`) — pick one | stacked cards (`.bt-cards`); horizontal scroll FORBIDDEN |
| **Report / appendix** | dense table (existing `.bt` 8+ cols) | horizontal scroll allowed ONLY when the human accepts report density on mobile (explicit ack in EVIDENCE.md) |

Landing comparison-table dual-representation IS mandatory if `.bt` is
in the recipe. No carve-outs.

## A.5 Visual / media role separation

Recipe declares the **role** of any visual asset; profile / skin
decides the **implementation**. This keeps the recipe profile-agnostic
and lets different skins (h2t-editorial vs h2t-graphs vs h2t-mono)
implement the same role differently.

```yaml
# recipe.yaml
sections:
  - role: hero
    visual:
      role: hero_media        # semantic role
      content_id: br-cover-01
      mobile_behavior: omit   # one of: omit | static_only | poster_only | full
```

Implementation choices admitted by `visual.role`:

| `visual.role` | Possible implementations |
|---|---|
| `hero_media` | static image · video poster · CSS animation · canvas · Three.js scene · WebGPU |
| `gallery` | static image grid · interactive carousel |
| `product_demo` | video with poster · animated SVG · canvas loop |
| `ambient_system` | CSS animation · WebGL background · Three.js scene |

**Visual-asset gate (always on):**

- No fake placeholders in the visual gate. If an asset is missing, the
  recipe omits the block OR uses a human-approved fallback declared
  inline.
- Video requires a poster. The poster IS the asset for first paint.
- Scripted visual (canvas / Three.js / WebGPU) requires a static fallback
  that renders at first paint and on mobile if `mobile_behavior` is
  `static_only` or `omit`.

For #88 specifically: NO visual assets are committed to the editorial
landing in this slice. All `visual` declarations resolve to `omit`
or are absent. The `.ck` family stays out per design-system §11. This
appendix's rules only kick in when a future slice introduces media.

## A.6 Reconciliation with §6 wire order (research-updated)

The pre-research §6 wire order needs three updates per A.0a:

1. The `evidence` role at §6 block 6 was Required-by-default. Research
   demoted it to profile-specific Required (Optional generally).
   Editorial-profile keeps it Required, BUT the role naming changes
   from "evidence" to **`footer_proof`** (universal slot) with
   editorial-specific `evidence` content lifted into it.
2. `problem` and `faq` are new Required roles. Either the cap relaxes
   to absorb them (D5) or they are deliberately omitted on this
   landing with explicit justification (e.g. profile audience already
   knows the problem, no objections cluster).
3. Block 3 (narrative-only space) is no longer "intentional negative
   space" — it is the natural slot for `problem` framing.

Updated §6 wire order under the **6-block tight regime** (§A.9 D5
keeps current cap):

| §6 Block | v0 role | Notes |
|---|---|---|
| 1 — Editorial hero | `hero` | unchanged |
| 2 — Proof beat | `proof` (top social-proof) | unchanged |
| 3 — Narrative section | `problem` | role renamed from "narrative" — must frame a real problem |
| 4 — Categorisation | `features` (`pos-grid`) | role unchanged |
| 5 — Comparison or process | `process` (recommended `.flow`) | comparison only with mandatory dual-rep — D3 |
| 6 — Close-narrative | `footer_proof` (was `evidence`) | universal slot; editorial fills with citations |
| 7 — CTA | `cta` (no sticky for editorial) | unchanged; `sticky_cta: false` |
| (8) — Footer micro-meta | folded into block 6 footer_proof | — |

Roles **omitted under the tight regime**: `solution`, `faq`. The
landing reader sees the problem (block 3) and the differentiation
(block 4) and is expected to infer the solution. No FAQ block — the
landing converts on a single action (open the deck), no objections
cluster expected.

Updated §6 wire order under the **8-block CRO regime** (§A.9 D5 picks
the Kleos cap):

| §6 Block | v0 role |
|---|---|
| 1 | `hero` |
| 2 | `proof` (top) |
| 3 | `problem` |
| 4 | `solution` |
| 5 | `features` |
| 6 | `comparison` OR `process` |
| 7 | `faq` |
| 8 | `cta` |
| 9 | `footer_proof` |

Total: 8 main + CTA = 9 sections. One dense block max. Editorial-
specific `evidence` content folds into `footer_proof`.

§6 D3 recommendation (`flow` over `comparison-table`) is reinforced
by A.4: choosing `.bt` here triggers mandatory dual-representation
implementation in this slice — non-trivial cost. Defer `.bt` until a
slice scoped to deliver `.bt-cards` + `@media` properly.

## A.7 Sources

### A.7.1 Initial human-supplied (4)

- Baymard mobile UX research — https://baymard.com/research/mcommerce-usability — partial (paywalled)
- Baymard mobile homepage behavior — https://baymard.com/blog/mobile-homepage-usability — partial (paywalled)
- Baymard mobile product-list comparison — https://baymard.com/mcommerce-usability/benchmark/mobile-page-types/product-list — partial (paywalled)
- Leadpages landing-elements overview — https://leadpages.com/landing-pages-guide/landing-page-elements

### A.7.2 Research-agent triangulation (19, 2026-05-08)

NN/g (research-grade UX evidence — 5 sources):
- https://www.nngroup.com/articles/scrolling-and-attention-original-research/ — fold attention split (80/20)
- https://www.nngroup.com/articles/page-fold-manifesto/ — multi-fold per responsive design
- https://www.nngroup.com/articles/homepage-design-principles/ — keep simple
- https://www.nngroup.com/articles/homepage-real-estate-allocation/ — 36 % wasted real estate baseline
- https://www.nngroup.com/articles/mobile-tables/ — table redesign rules
- https://www.nngroup.com/articles/top-ten-guidelines-for-homepage-usability — homepage navigation
- https://www.nngroup.com/articles/mobile-usability-2nd-study/ — mobile usability principles

Comparison-on-mobile (3 sources, full consensus):
- https://uxmovement.medium.com/the-best-mobile-layout-for-complex-data-tables-e3ced21ce425 — horizontal-scroll = anti-pattern
- https://foolproof.co.uk/journal/making-product-comparison-work-on-mobile — small-screen comparison failure mode

Sticky CTA evidence (2 sources, with measured CVR lift):
- https://www.onlinedialogue.nl/en/blogs/sticky-cta-guaranteed-conversion-uplift/ — 33-test meta
- https://convertica.org/ecommerce-case-study-sticky-cta/ — 252 % mobile lift

Block-anatomy consensus (5 sources):
- https://kleos.cloud/signal/landing-page-anatomy-sections-that-convert/ — 8-block model with measured CVR delta (5.2 % vs 1.8 %)
- https://replo.app/blog/anatomy-of-a-landing-page — top-down ordering
- https://unbounce.com/landing-page-articles/the-anatomy-of-a-landing-page/ — building-block model
- https://www.growform.co/anatomy-of-a-landing-page/ — structure beats offer
- https://woobox.com/articles/mobile-landing-page-optimization — 390 px viewport math + headline-wrap rule

Anti-pattern / clutter (2 sources):
- https://blog.templately.com/visual-clutter-on-a-website-and-how-to-fix-it/
- https://landerlab.io/blog/10-common-landing-page-mistakes — clutter = mistake #1

Research artifact:
- `C:/Users/<user>/.h2t/research/h2t-creative-landing-block-taxonomy-mobile-2026-05-07.sources.json` — full sources persistence (exa-ai adapter, 6 queries).

## A.8 Approval gate (additional)

Approving the v0 appendix (in addition to §9 main approval gate) means:

1. The required-block list (A.1) is the canonical landing role
   vocabulary for h2t-creative going forward, applied to all profiles
   (editorial / graphs / mono / pfad / future). Profile-specific specs
   inherit and refine, not redefine.
2. The density rule (A.2) and mobile rule (A.3) are hard gates, not
   guidelines.
3. The comparison primitive rule (A.4) makes `.bt` on landing mobile
   conditional on dual-representation shipping in the same slice.
4. The visual / media role separation (A.5) becomes the recipe
   contract for any future slice that adds visual assets. For this
   slice it changes nothing (no assets).
5. The research diff in §A.0a is accepted: `problem` / `faq` /
   `footer_proof` / Conditional-`navigation` are added; `evidence` is
   demoted to profile-specific.

Until both §9 AND A.8 are acked, no recipe v2.

## A.9 Open decisions surfaced by research

Research did not eliminate every choice — it surfaced new tensions.
Each below needs an explicit human verdict alongside D1–D4 from §6.

| ID | Decision | Options | Recommended (research-weighted) |
|---|---|---|---|
| **D5** | Section cap | (a) keep §2.2 tight cap **6 main + CTA = 7** (omit `problem` → fold into `hero` lede; omit `solution`; omit `faq`; rename `evidence` → `footer_proof`). (b) relax to **8 main + CTA = 9** matching Kleos 8-block CRO model. | **(a) tight regime** for h2t-editorial slice — landing audience is brand stakeholders evaluating visual-system fit, not a paying customer needing objection close. The Kleos delta (5.2 % vs 1.8 % CVR) is for transactional / lead-gen LPs; this landing is a brand-fit demo. Keep tight. Re-evaluate (b) when a transactional profile lands. |
| **D6** | `evidence` block | (a) drop entirely (covered by `footer_proof`). (b) keep as editorial-profile-specific Required. | **(b) keep editorial-specific** — h2t-editorial brand promise IS audit-trail credibility (citations to source dossier, design-system, arbitration spec). Folds INTO `footer_proof` slot but content is "here are my receipts", not "logos + fine print". |
| **D7** | `problem` block | (a) explicit `problem` block (Kleos Required). (b) fold into `hero` lede sentence (1 line summarising what the form solves). | **(b) fold into hero lede** under the D5(a) tight regime. The "what" of System B-Landing is fast to state ("editorial form for long analytical content"); a separate problem block would be padding. Re-evaluate (a) for landings with a more complex problem story. |
| **D8** | `faq` block | (a) include explicit FAQ (Kleos Required). (b) omit. | **(b) omit** — for this audience there is no objection cluster. Brand stakeholders have no FAQ-shape concerns about a recovered visual system. |
| **D9** | `sticky_cta` | (a) `true` (mobile sticky-bottom). (b) `false`. | **(b) false** — `editorial-cta` is "open the deck PR", not "buy now". No transactional intent → Online Dialogue rule "only in cart or check-out" rules out sticky here. The flag is reserved for h2t-graphs / future commerce-style landings. |
| **D10** | `navigation` block | (a) include (Required for full homepages). (b) omit (Optional / campaign-LP). | **(b) omit** — single-purpose landing for this slice. Single-tab `.tabs` chrome was the Batch C anti-pattern and stays out. |

Net effect of recommended D5–D10: §6 wire order under D5(a) stays at
**7 sections** (hero / proof / problem-via-hero-lede / features /
process / footer_proof-with-evidence / cta). Same number of recipe
sections as the rejected post-Intent-Reset build, but with research-
backed role assignments and explicit demotions/omissions.

If the human vetoes the recommended D5(a) and picks D5(b) (8-block
Kleos regime), the wire order grows to **9 sections** and the recipe
must add `solution` + `faq` blocks with their own copy. Plan for
~20–30 LOC HTML extra.
