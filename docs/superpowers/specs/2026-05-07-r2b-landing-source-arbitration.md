# R2b — Landing Source Arbitration Visual Gate (h2t-editorial landing, #88)

**Status:** Decision proposal — awaiting human approval before T1 implementation begins.
**Trigger date:** 2026-05-07
**Branch:** `codex/r2b-editorial-landing` (worktree `C:/dev/h2t-skills-r2b-landing`)
**Linked specs:**
- Deck arbitration spec: [`docs/superpowers/specs/2026-05-07-r2b-source-arbitration.md`](2026-05-07-r2b-source-arbitration.md) — establishes the System A vs System B classification used here.
- Legacy-fidelity skill: `plugins/h2t-creative/skills/legacy-fidelity/SKILL.md` — pipeline reference (T0.5 step is being introduced by this batch).

---

## 0. Why this step exists

R2b deck recovery (#87) hit a costly mid-flight reset: T1–T7 was built against the wrong primary source (pos-sprint editorial, System A), the conflict only surfaced after Batch C build + screenshots, and the entire styling layer had to be rebuilt against the actual canonical (rejuve-pitch-deck, System B). The lesson recorded in plan §15.7:

> "When two source HTMLs visibly disagree on palette, body typography, kicker class, and cover composition, the agent must surface the conflict at T0 dossier review and request human arbitration *before* T1 builds tokens."

**T0.5 — Source Arbitration Visual Gate** is the new step that operationalizes that lesson: between T0 (caller inventory + dossier locking) and T1 (TDD slice 1 — tokens), the agent compares all locked goldens for the slice and either confirms one shared visual system (proceed) or surfaces a conflict (stop and arbitrate).

This step is NOT yet codified in `legacy-fidelity/SKILL.md`. Codification lands as part of this slice (proposed amendment in §6 below).

---

## 1. Locked landing goldens

`docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-golden/`:

- `rejuve-appendix-competitive-report.html` — competitive-landscape long-form report (16-brand sortable table, 4-category cards, side-by-side criteria comparison, stat hero, footnotes)
- `rejuve-appendix-elpodium-decomposition.html` — decomposition long-form report (12-row priority-coded work-block table, responsibility matrix, wave-staged phasing)

Plus reference screenshots (4 PNGs):
- `screenshots-rejuve-appendix-competitive-report/unknown/{desktop,mobile}_20260507_013314.png`
- `screenshots-rejuve-appendix-elpodium-decomposition/unknown/{desktop,mobile}_20260507_013317.png`

---

## 2. Token + typography extraction

Both goldens declare the same `:root` block with one minor difference:

| Token | competitive-report | elpodium-decomposition |
|-------|--------------------|------------------------|
| `--bg`     | `#fafaf8`           | `#fafaf8` ✓             |
| `--sf`     | `#f5f3ee`           | `#f5f3ee` ✓             |
| `--bd`     | `#e0dbd3`           | `#e0dbd3` ✓             |
| `--ac`     | `#c9a96e` (gold)    | `#c9a96e` ✓             |
| `--ad`     | `#8a6520` (gold-dark)| `#8a6520` ✓            |
| `--tx`     | `#1a1a18`           | `#1a1a18` ✓             |
| `--mu`     | `#666`              | `#666` ✓                |
| `--gr`     | `#3d6b4a` (green)   | `#3d6b4a` ✓             |
| `--dn`     | `#cc2222` (danger)  | `#cc2222` ✓             |
| `--bl`     | `#2255aa` (blue)    | `#2255aa` ✓             |
| `--pu`     | (absent)            | `#882299` (purple)      |
| `--r`      | `6px`               | `6px` ✓                 |
| `--serif`  | `'Playfair Display', Georgia, serif` | same ✓ |
| `--sans`   | `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | same ✓ |

Typography baseline (both files):
- body: `var(--sans)` 14px lh 1.6
- h1: `var(--serif)` 28px `var(--ad)` accent-dark
- h2: `var(--serif)` 20px `var(--ad)`
- stat number: `var(--serif)` 26–28px `var(--ad)`

**The `--pu` purple token in elpodium is a content-driven extension** (one extra category in the 12-row decomposition table needed a fifth semantic colour; competitive-report only needed four). Adding the token does NOT diverge the visual system — it extends the existing palette pattern (gold-dark accent + green/danger/blue + extra purple) within the same shape.

---

## 3. Visual system classification

**Both goldens belong to the same visual system: System B-Landing.**

System B-Landing extends the deck System B brand identity (gold accent + Playfair serif headings + warm cream background, established in [`2026-05-07-r2b-source-arbitration.md`](2026-05-07-r2b-source-arbitration.md) §2) with:

- **Denser landing-density type scale.** h1 28 vs deck h1 42; body 14 vs deck body 16.5. Article reading vs slide projection.
- **Sans body, not serif body.** Landing body uses `var(--sans)` (system-ui chain — `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`). Deck body uses `var(--fb)` (Georgia serif chain). This is a deliberate form-specific choice: landing pages need fast scan-ability, decks need printed-book pacing.
- **Short token names.** Landing uses `--ac/--ad/--tx/--mu/--bd/--sf/--gr/--dn/--bl/--pu/--r`; deck uses full names (`--accent/--accent-text/--text/--text-dim/--copper/--border` + `--fh/--fb/--fu`). Each form owns its CSS namespace; collisions are impossible.
- **Wider semantic palette.** Landing has named greens / dangers / blues / purples for table colour-row variants and pillar tagging. Deck uses a similar set (`--accent-soft/--copper/--danger/--auto/--green` + corresponding `*-soft` tints).

### Component-level signature

| Primitive | competitive-report | elpodium-decomposition |
|-----------|--------------------|------------------------|
| Top nav bar | links right-aligned, sans 14px dim | same |
| Page header | h1 serif gold-dark + meta line below | same (centered variant) |
| Hero stats | 3-up flex row of `.stat-n` cards (gold serif number + dim label) | 4-up grid of `.fn-n` cards (same primitive, different variant) |
| Sectioned cards | gold-bordered cards with criteria | same |
| Side-by-side columns | criteria-comparison 2-col grid | (not used) |
| Sortable table | 16-row competitor table with badges | (not used) |
| Priority-coded table | (not used) | 12-row table with cell-tinted criticality |
| Responsibility matrix | (not used) | full-width matrix table |
| Footnotes | dim sans 11–12px | dim sans 11–12px |

Both share the **base primitives** (nav, h1, h2, stat-card, card, table, footnote) and differ in **which primitives each page uses** — that's content variation, not system divergence.

---

## 4. Mobile inspection (initial Gate B observation, NOT a verdict)

Reference mobile captures show:
- **competitive-report mobile:** stats stack 1×3, 4-category cards stack 2-up, side-by-side columns stay 2-col but narrower, 16-row competitor table preserves desktop layout (would scroll horizontally at 390px).
- **elpodium-decomposition mobile:** hero metrics stack 2×2, 12-row decomposition table preserves all desktop columns densely, responsibility matrix below preserves desktop layout.

**Editorial-print signature.** Both landing goldens accept some content density on mobile rather than hiding columns or representation-switching. This sets the Gate B contract for landing form: tables stay semantic + dense, with horizontal scroll allowed if needed (deliberate authoring choice, NOT a deck-style dual-representation collapse). Final Gate B contract decided at T6 of landing slice; this is a forward observation only.

---

## 5. Arbitration decision proposal

**No source conflict.** Both landing goldens encode the same System B-Landing visual system. The single token-set difference (`--pu` purple in elpodium) is a content-driven palette extension within the existing shape, NOT a system divergence.

### Proposed canonical roles

| Source | Proposed role | Reasoning |
|--------|---------------|-----------|
| `rejuve-appendix-competitive-report` | **PRIMARY** | Wider primitive coverage: page header + stat hero (3-up) + categorized cards (4 categories) + side-by-side criteria columns + 16-row sortable competitor table + footnotes. Exercises every component-level primitive of System B-Landing in a single page. |
| `rejuve-appendix-elpodium-decomposition` | SECONDARY (alternate / table-heavy variant) | Same visual system; complements primary by exercising priority-coded tables + responsibility matrix + the `--pu` palette extension. Use as a recipe-content reference for table-heavy landing pages, NOT as a separate visual baseline. |

`rejuve-pitch-deck.html` (committed in `h2t-editorial-deck-golden/`, used as DECK primary) stays a **CONTRACT-ONLY brand reference** for landing — confirms the gold + Playfair + warm-cream identity but its type scale is deck-only. Do not lift its body typography or component sizing into landing CSS.

### Token namespace

Landing form keeps the short-name landing token shape (`--ac/--ad/--tx/--mu/--bd/--sf/--gr/--dn/--bl/--pu/--r/--serif/--sans`) lifted verbatim from goldens. Deck form keeps its full-name shape. The two namespaces never overlap because each form has its own CSS scope (deck inlines its own; landing has its own component CSS).

**However, R1 landing-form tokens currently in `profiles/h2t-editorial/tokens.css` use `--color-*` prefixes (R1 contract from pre-R2b).** That contract's relationship to the landing System B short names needs explicit decision in T1: either rename the existing R1 `--color-*` tokens to System B-Landing short names (breaking R1 landing fidelity to make landing form System B-canonical), or layer System B-Landing tokens alongside the R1 namespace inside `landing/`-scoped CSS. **This is the only real decision deferred from T0.5 to T1.**

---

## 6. Proposed legacy-fidelity skill amendment (lands with this slice)

Add to `plugins/h2t-creative/skills/legacy-fidelity/SKILL.md` between current T0 and T1 sections:

```
### T0.5 — Source Arbitration Visual Gate (MANDATORY)
After T0 locks the goldens, BEFORE T1 builds tokens:

1. Extract `:root` token block + typography baseline from every locked
   golden HTML.
2. Side-by-side compare: accent colour, body font family, kicker class,
   header / cover composition, decorative-rule grammar.
3. Classify visual systems. If goldens disagree on accent / body font /
   kicker class / cover composition → STOP and request human arbitration.
   Do NOT pick a primary unilaterally.
4. If goldens share one system → propose primary by primitive coverage
   (the golden that exercises the most component-level primitives) and
   document the secondary as content-grammar reference.
5. Document the arbitration in
   `docs/superpowers/specs/<date>-<slice>-source-arbitration.md` and wait
   for human approval before starting T1.

The R2b deck retrospective (PR #102) shows the cost of skipping this
step: T1–T7 implementation against the wrong primary, full styling
rebuild against actual canonical. T0.5 catches the conflict before
tokens are written.
```

Add to `pressure-scenarios.md` as a new entry:

```
## 11. "These goldens look similar enough — pick a primary and start"
The agent has T0 inventory locked, all sources are visually editorial,
and the temptation is to pick whichever golden was named first as
primary and start T1. Then mid-slice, after T1–Tk, a screenshot reveals
the actual canonical was a different golden — the one whose accent,
body font, or cover composition differs from the one chosen. The agent
just rebuilt the styling layer twice.

**Antidote.** Run T0.5 Source Arbitration Visual Gate explicitly. Open
every golden's `:root` and compare token-by-token. Surface ANY
disagreement on accent / body font / kicker class / cover composition
to the human. Wait for written canonical-primary approval before T1.
The arbitration spec is the audit trail.
```

---

## 7. Stop

Per current batch scope: **no implementation until canonical landing primary is approved.**

This document is the proposal. Awaiting human ack on §5:
- Confirm `rejuve-appendix-competitive-report` as PRIMARY for landing form
- Confirm `rejuve-appendix-elpodium-decomposition` as SECONDARY / table-heavy variant
- Confirm token namespace decision (rename existing R1 `--color-*` → System B-Landing short names, OR layer alongside) deferred to T1 with explicit decision required at T1

If the human disagrees with any of the above, stop and re-arbitrate. If approved as written, start T1 (locked dossier + tokens + palettes + base typography for landing form).
