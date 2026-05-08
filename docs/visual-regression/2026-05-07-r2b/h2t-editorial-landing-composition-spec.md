# h2t-editorial landing — composition spec

**Date:** 2026-05-07
**Phase:** R2b #88 Landing Intent Reset (post-Batch-C)
**Branch:** `codex/r2b-editorial-landing`
**Status:** APPROVED 2026-05-07 by human, with two amendments below.

**Amendment A (Block 10.5 — Editorial CTA).** A landing without a CTA
is wrong. CTA is added as a NEW System B-Landing extension component
named `editorial-cta`, with explicit visual grammar (see §4 row 10.5).
This is the first net-new primitive added since T1-T4 extraction —
allowed only by this written approval and only with the constraints in
§4.

**Amendment B (Mobile reclassification).** Mobile is NOT out of scope.
Replace the §2 "Mobile contract" row and §7 "OUT of scope" mobile entry
with:
- Mobile visual QA IS in scope: capture + Agent Visual QA cover
  desktop AND mobile in the next batch.
- Mobile-specific redesign is OUT of scope UNLESS desktop composition
  fails to adapt.
- Mobile acceptance: no horizontal overflow, no clipped text, no
  unreadable tables / cards. If a block fails this, the desktop
  composition decision (block primitive choice) is the first thing to
  revise — not a new mobile-only invention.

> **Source role.** The two locked landing goldens
> (`rejuve-appendix-competitive-report.html`,
> `rejuve-appendix-elpodium-decomposition.html`) are **PRIMITIVE SOURCES**
> per plan §16. They provide the System B-Landing visual vocabulary
> recovered in T1-T4. They are NOT a layout target — they are
> appendix/report pages, not landings, and reproducing their vertical
> composition produces a dense analyst document, not a landing.
>
> This spec defines the BLOCK INVENTORY for an editorial landing
> composed FROM those primitives. It is the contract that drives the
> recipe rewrite in the next batch.

---

## 1. Why this spec exists

T2 (component vocabulary extraction) already recovered the closed
primitive set. That document answers *"what primitives are there"*.
This spec answers a different question: *"in what order, density, and
purpose do we use them on a LANDING page"*.

Without this spec, the recipe author defaults to the goldens' layout
(every primitive is used, in the order the goldens use them). That
produces an appendix, not a landing. Batch C demonstrated this failure
mode:

- 15 sections, every primitive present, vertical density ≈ 367-line
  HTML
- No hero / value proposition — just `.ph` (page-header) + meta
- No conversion target — no CTA primitive in goldens, none in the build
- Tables and decomposition blocks render at appendix density (4 rows,
  6 cols) on the landing — overwhelming for a first-time visitor

The composition decisions below are landing-specific judgement calls
that the goldens cannot inform.

---

## 2. Landing intent

| Question | Answer |
|---|---|
| Who is the target reader? | A System B brand stakeholder evaluating the editorial form's visual language fit (internal review audience for now; external audience deferred to a later slice when content is owned). |
| What action does the landing drive? | A single primary action — review the deck form (#87 PR #102 / commit `31ac606`) which is the matching delivered output. Optionally a secondary "browse appendices" link to the sources directory. |
| What proof of value? | The System B-Landing primitive showcase — the landing is its own evidence that the visual system works for editorial content. |
| What density? | Editorial-density body (14 px, max-width 1100 px) — same baseline as goldens, but the page is SHORTER. Landing reads in ≤ 90 seconds; appendix reads in ≥ 10 minutes. |
| Mobile contract? | **In scope per Amendment B.** Mobile visual QA covers the same blocks as desktop. No mobile-specific redesign — composition must adapt naturally. Acceptance: no horizontal overflow, no clipped text, no unreadable cards/tables. Where desktop composition cannot adapt, the desktop primitive choice gets revised, not invented mobile-only logic. |

---

## 3. Approved primitives (closed contract)

Composition uses ONLY primitives from
[`h2t-editorial-landing-design-system.md`](h2t-editorial-landing-design-system.md)
§10 closed vocabulary. Concretely:

| Primitive group | OK to use |
|---|---|
| Page shell | `.tabs / .tab / .page / .ph / .ph-meta / .section` |
| Container + grids | `.card / .g2 / .g3 / .g4` |
| Stats / KPI | `.stat / .stat-n / .stat-l` (compact) — `.funnel` HERO variant deferred (overwhelming on a landing) |
| Categorized cards | `.mmap / .mmap-cell / .mmap-type / .mmap-brands / .mmap-note` — used at MOST once |
| Position cards | `.pos-grid / .pos / .pos-title / .pos-desc` — used at MOST once |
| Tables | `.bt` only (with row coloring `.deep / .rejuve / .w1 / .w2 / .w3`). `.dt` collapsible deferred (appendix-ish), `.proh-tbl` deferred (compliance-specific), `.wave-block` deferred (phase planning is appendix content). |
| Tags / chips | full family available inline (`.tag`, `.tag-fs/-md/-sm/-b2`, `.yes/.no/.part`, `.mod-tag`) |
| Specialized blocks | `.flow` allowed (process narratives are landing-shaped); `.comp-box / .disc / .meta-box` deferred (regulatory specifics, appendix material) |
| `.ck` family | OUT (image-bearing, deferred to a later slice with real assets) |

Forbidden additions:

- ❌ R1 generic primitives (`hero / cta / footer / nav / section`) — out
  of scope per design-system §10.
- ❌ A new "CTA" primitive unless the human approves it as a
  landing-specific extension. The goldens have no CTA. Adding one
  silently extends the System B-Landing vocabulary in the wrong place.
- ❌ Inline images. `.ck` and any other image-bearing block is excluded
  until image-asset policy is decided.

---

## 4. Proposed block inventory

10 blocks, top-to-bottom. Each block names the primitive(s) and its
purpose on the landing (NOT on the appendix).

| # | Block | Primitive(s) | Purpose | Density |
|---|---|---|---|---|
| 1 | **Editorial header** | `.tabs` (single tab "Form: Landing" — sticky strip is the System B-Landing brand chrome) + `.page.active` shell | Establishes that this IS a System B-Landing artefact. Tab strip is the System B identity signal. | 1 tab, no real navigation; lighter than goldens' 3-5 tabs. |
| 2 | **Page-header / title block** | `.ph` (h1 + `.ph-meta`) | h1 = profile+form name ("h2t-editorial — landing"). `.ph-meta` = build date + slice ID. Replaces the absent marketing hero — System B-Landing's editorial header IS the hero. | One headline, one meta line. |
| 3 | **Lead summary** | one `.section` h2 + a short paragraph (≤ 60 words) inside section body | One sentence stating what the System B-Landing form is for, one stating who it's for. Pure prose; NO primitive complexity here. | ≤ 4 lines of body copy. |
| 4 | **3 differentiator cards** | `.card-grid g3` of three `.card` blocks | Three claims about the System B-Landing form. Each card: short h3 + 1-paragraph body. Lifts content from existing dossier `notes:` fields, not invented copy. | 3 cards, each ≤ 35 words. |
| 5 | **Compact KPI strip** | `.stat-n / .stat-l` × 3 in `.g3` | Numeric facts about the recovered slice (e.g., "11 primitives", "545 contract tests", "0 R1 leaks"). Not the appendix's funnel hero — that primitive is OUT of this composition. | 3 stats, 1 line of label each. |
| 6 | **Primitive map** | `.mmap` (4 cells, 2-up grid) | The four primitive groups (shell / containers / tables / specialized) as map quadrants. Same pattern as appendix's "4 типа игроков", recomposed for our content. | 4 cells, ≤ 25 words each. |
| 7 | **Differentiation positions** | `.pos-grid` (4 cells max) | Four positions the form takes vs other h2t-creative profiles (terminal / graphs / mono / pfad). Each `.pos` = title + 1-sentence diff. | 4 positions, ≤ 30 words each. |
| 8 | **Profile comparison table** | `.bt` (≤ 5 rows × 5 cols) | Cross-profile comparison: editorial vs terminal vs graphs vs mono vs pfad on key dimensions (primary use / typography / palette / density). Row-coloring `.rejuve` for the editorial row. | ≤ 5 rows. NO `.deep / .w1-3` highlight on a landing — those imply analytical depth that is out of scope. |
| 9 | **Process flow** | `.flow` with 4 steps | The 4-step landing-author workflow: source → arbitrate → extract → compose. NOT the appendix's 6-step customer-journey. | 4 steps, ≤ 25 words each. |
| 10 | **Footnote / evidence** | one `.section` with body containing `<a>` to source dossier + design-system + composition spec (this file). No `.disc / .comp-box / .meta-box` (appendix material). | Audit trail: "this landing is governed by …" with three links. | 1 line of body. |

**Block 10.5 — Editorial CTA (Amendment A — APPROVED).**

| | |
|---|---|
| **Primitive** | NEW System B-Landing extension component `editorial-cta` (the FIRST net-new primitive since T1-T4 extraction; admitted only by Amendment A, governed by the visual grammar below). |
| **Visual grammar** | Warm cream / white card · 1 px `var(--bd)` border · small gold `.label` (uppercase letterspaced kicker, 11 px, `var(--ad)`) · Playfair-serif heading · short body text (≤ 25 words) · ONE primary text-style link/button using `var(--ac)` · OPTIONAL secondary muted link (`var(--mu)`) · NO gradients · NO big SaaS button · NO rounded pill · NO emoji. |
| **Purpose** | Conversion / action close — drives the reader to the deck (#87 / PR #102 / commit `31ac606`) as the matching delivered output. NOT a marketing banner. |
| **DOM contract** | `<div class="editorial-cta">` wrapping `<span class="editorial-cta__label">` + `<h3 class="editorial-cta__title">` + `<p class="editorial-cta__body">` + `<a class="editorial-cta__primary" href>` + optional `<a class="editorial-cta__secondary" href>`. |
| **Token contract** | `var(--ac)` (primary link), `var(--ad)` (label), `var(--bd)` (border), `var(--bg)` (card bg, NOT `var(--sf)` — distinct from `.card`/`.stat` so the CTA reads as a different surface), `var(--mu)` (secondary link), `var(--serif)` (heading), `var(--tx)` (body). |
| **What it is NOT** | Not the R1 `.cta` (different namespace, different shape). Not a `.card` (different border, different bg, different headline treatment). Not a `.disc` (no accent left-rail, no muted-only body). Not a `.meta-box` (no cool-blue tint). |

---

## 5. Density vs appendix — explicit comparison

| Dimension | Appendix golden | This landing |
|---|---|---|
| Page length | ≥ 1200 LOC HTML | ≤ 250 LOC HTML target |
| Primitive instances | every primitive multiple times (e.g. competitive-report has 3+ tables) | every primitive ≤ once |
| Tables | 3 distinct table primitives, dozens of rows | 1 table (`.bt`), ≤ 5 rows |
| Decomposition / collapsible | yes (`.dt-section`) | NO — appendix-only |
| Wave / phase blocks | yes (`.wave-block` × 3) | NO — appendix-only |
| Compliance / footnote blocks | yes (`.comp-box / .disc / .meta-box`) | minimal `.section` footnote, no compliance primitives |
| Read time | 10+ min | ≤ 90 s |
| Information mode | analyst depth | first-impression brand vehicle |

If the recipe drift produces a page longer than ~250 LOC HTML, the
composition is being violated — most likely because the author is
silently re-adopting the appendix structure. That's the same failure
mode as Batch C and is the gate this spec is meant to prevent.

---

## 6. Acceptance criteria for the recipe rewrite

A landing recipe satisfying THIS spec must:

1. Use only the primitives in §3. Forbid the ones explicitly excluded.
2. Render in ≤ 10 top-level recipe sections (one per block, possibly
   2-3 fewer if the editorial header / page header are merged into the
   tabs primitive).
3. Produce HTML ≤ 250 LOC after assembler (sentinel test in §LT-9 of
   the test file).
4. Carry NO `.dt / .proh-tbl / .wave-block / .comp-box / .disc / .meta-box`
   class fragments in the built `index.html`.
5. Carry no `<img>` tags (image-asset policy unresolved).
6. Capture into a FRESH dist path (`dist/r2b-h2t-editorial-landing-modular/`)
   so the Batch C audit trail and the new evidence don't co-mingle.

These six gates land as new tests under `§LT-9 Landing composition
contract` in the next batch — not now.

---

## 7. What is OUT of scope for this spec

- Mobile-specific redesign / breakpoint invention (Amendment B — mobile
  VISUAL QA stays in scope; mobile-NEW-design is out of scope).
- Image-asset policy for `.ck` family (separate slice).
- New components beyond the closed T1-T4 vocabulary, **except**
  `editorial-cta` (Amendment A approved).
- Agent Visual QA — the batch after this one handles QA. THIS batch
  handles recipe rewrite + fresh build + capture only.

---

## 8. Approval gate

This spec is **DRAFT** until the human:

1. Reads §4 block inventory and either approves it as proposed OR
   amends specific blocks (`"swap block 6 mmap for a second .card row"`,
   `"add a CTA at block 10.5 with this exact contract"`, etc.).
2. Confirms acceptance criteria in §6.
3. Greenlights the next batch (recipe rewrite + fresh build + capture).

Until that approval lands here as a recorded "approved 2026-05-NN by
{human}" line at the top, NO recipe rewrite, NO new build, NO
screenshots.

---

## 9. References

- Plan amendment: `docs/superpowers/plans/2026-05-07-r2b-h2t-editorial-modularization.md` §16.
- Primitive extraction: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-design-system.md` §10.
- Source dossier: `plugins/h2t-creative/profiles/h2t-editorial/sources/landing-references.yaml`.
- Source arbitration: `docs/superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md`.
- Batch C evidence (frozen): `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-system-b-modular/EVIDENCE.md`.
