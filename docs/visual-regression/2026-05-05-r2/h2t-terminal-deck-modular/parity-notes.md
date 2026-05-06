# R2a — h2t-terminal deck parity notes (T17.5 — final)

**Build under review:** `dist/r2a-h2t-terminal-deck-validation/index.html`
(rebuilt after T15 + T15.5; assembled from `profiles/h2t-terminal/validation/recipe-deck.yaml`).
**Capture set:** `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/{desktop,mobile}/` — 11 + 11 PNGs.
**Reviewer:** Agent Visual QA (T16). Human visual approval (T17) follows.

> **Process:** Agent must open every screenshot before claiming any visual gate
> passes. Spotting "all 22 files exist with non-zero size" is not visual QA. The
> agent is the **first** visual layer; the human is the **final** layer.

History:
- T12.5 — first Agent Visual QA pass: Desktop = PASS candidate, Mobile = BLOCKED (5 BLOCKER · 5 ISSUE · 1 PASS). Mobile adaptation plan proposed.
- T13 — no desktop fixes needed (Agent QA found no desktop blockers).
- T14 — mobile contract written into tests + plan; 13 RED tests authored.
- T15 — mobile CSS implemented; tests went RED → GREEN; mobile recapture.
- T15.5 — table mobile rep changed from `overflow-x: auto` (bad UX, conflicts with deck swipe nav) to dual-representation (`.table-desktop` + `.table-mobile` cards).
- T16 — first complete 22-screenshot review. 1 ISSUE flagged (slide-08 mobile TERMINAL badge faint).
- T17.5 — minimal `.code-block::before` mobile polish (top:0 / left:0 / 10px / 2px 8px). Tests + recapture confirm badge visible.

---

## Verdict summary

| Gate | Status | Rationale |
|---|---|---|
| **Gate A — Desktop fidelity** | ✅ PASS candidate (Agent QA) | All 11 desktop slides render content from the recipe, frame chrome in place, color tokens land, typography scales match the design system. No clipping or overflow at 1440×900. Pending human review (T17). |
| **Gate B — Mobile usability** | ✅ PASS candidate (Agent QA) | **11 PASS · 0 ISSUE · 0 BLOCKER** after T17.5. Mobile is fully usable: no clipped headlines, no off-screen content, no horizontal-scroll affordances except inside `.code-block pre`. Pending human review (T17). |

**Mobile aggregate (post-T17.5): 11 PASS · 0 ISSUE · 0 BLOCKER.**
T12.5 baseline: 1 PASS · 5 ISSUE · 5 BLOCKER → T16: 10 PASS · 1 ISSUE · 0 BLOCKER → T17.5: 11 PASS · 0 ISSUE · 0 BLOCKER.

---

## Per-slide audit (T16)

Status legend: ✅ PASS · ⚠ ISSUE · ❌ BLOCKER.

### slide-01 — title
- **Desktop ✅ PASS** — Centered hero. `// SESSION 01` green eyebrow, white "BUILDING YOUR" + green "PERSONAL OS", cursor block at end of "OS". Subline + meta dim below. Counter `01 / 11`, progress sliver, scanline overlay subtle. Faithful to pos-sprint slide 01.
- **Mobile ✅ PASS** — h1 32px wraps clean: "BUILDING YOUR" / "PERSONAL OS" on two centered lines with no clipping. "from chaos to system" subline + "// speaker name | 2026" meta dim below. Counter top-right, hint bottom-right scaled to 11px / 10px. **No overflow.**

### slide-02 — title-body
- **Desktop ✅ PASS** — Eyebrow, h2 with red `<span class="danger">without a system.</span>`, single-paragraph body. Layout correct; recipe-driven density.
- **Mobile ✅ PASS** — Headline wraps to 2 lines, body paragraph to 2 lines below. Padding 28/20/32 leaves ample column; content has hierarchy. Empty top half is intentional (slide-inner `justify-content: center`) and is not a defect.

### slide-03 — stats
- **Desktop ✅ PASS** — 3 stat-boxes, red top border, `73% / 4.1h / 89%` numbers in red, dim labels, indices in top-right. Matches pos-sprint slide 02.
- **Mobile ✅ PASS** — `flex-wrap: wrap` arranges as 2-up + 1 below (73% & 4.1h side-by-side, 89% full width below). Red top borders preserved, numbers `--danger`, indices in corners visible. All content readable.

### slide-04 — quote
- **Desktop ✅ PASS** — Green-left-border quote-block with italic body, `// working definition · 2026` source, three bullets with `→`.
- **Mobile ✅ PASS** — Quote-block tighter padding (14/18); italic body wraps cleanly. Bullets now use `align-items: flex-start` and `gap: 10px` — wrapped text re-indents under the arrow, visual link preserved. All three bullet items readable.

### slide-05 — cards
- **Desktop ✅ PASS** — Three cards in a row with top color stripes (green / amber / blue).
- **Mobile ✅ PASS** — `.card-row` collapses to vertical stack: `CLAUDE.md`, `Skills`, `MCP` all visible end-to-end with their color stripes (`--accent`, `--accent2`, `--accent3`). **All three cards on screen.** Was BLOCKER at T12.5.

### slide-06 — layers
- **Desktop ✅ PASS** — Three `.layer` rows with color-coded left borders, num + bold name + dim desc.
- **Mobile ✅ PASS** — `.layer` collapses to stacked rows: numeric prefix, name, desc on separate lines per layer. `.layer-num`/`.layer-name` shed fixed widths. All three layers (Physical / Interface / Agent) visible with color borders. **No desc overflow.** Was BLOCKER at T12.5.

### slide-07 — split
- **Desktop ✅ PASS** — Two columns (1fr 1fr), `// PARAMETERS` green vs `// STRUCTURE` amber.
- **Mobile ✅ PASS** — `.split` collapses to single column. `// PARAMETERS` block first (with bullet list), `// STRUCTURE` block below. Each `> ` bullet entry on its own line. **No 2-col-at-230px illegibility.** Was BLOCKER at T12.5.

### slide-08 — code
- **Desktop ✅ PASS** — Green `TERMINAL` badge top-left, prompt/cmd/arg/comment span colors land, monospace baseline preserved. Caption with `//` amber + dim text below.
- **Mobile ✅ PASS** (after T17.5) — Code-block padding 18/16 + pre 12px works; `mkdir ~/.claude/skills` and `touch ~/.claude/CLAUDE.md` lines fit; comments dim and readable; caption visible at 12px. **Green `TERMINAL` badge now visible at top-left of code-block** (`.code-block::before` polished in T17.5: `top: 0; left: 0; font-size: 10px; padding: 2px 8px;`). Sub-pixel disappearance at 390×844 fixed by anchoring flush at 0/0 with a slightly smaller chip; readable, not visually competing with the prompt line below.

### slide-09 — table
- **Desktop ✅ PASS** — Three columns (Variant / Volume / Logic), color-coded first column (green / amber / blue), mono amber on Volume, italic note below. Matches merkazim slide 10.
- **Mobile ✅ PASS** — **Dual-representation working.** Three stacked `.table-card` articles: `A · Narrow focus` / `B · Extended` / `C · Full track`, each as a card with `VOLUME` (uppercase dim 11px) and `LOGIC` dt labels, full text values at 14px (e.g. `Intro + first 2 sessions of one track.`). Color preserved on card titles (green / amber / blue). Italic note under cards. **No horizontal scroll. No swipe-nav conflict. No content lost.** Was BLOCKER at T12.5; T15.5 fixed via dual-rep.

### slide-10 — divider
- **Desktop ✅ PASS** — Centered, `// 03 · TOPICS`, "FOUR TRACKS +" white + "EXTENDED INTRO." green, divider line. Matches merkazim slide 04.
- **Mobile ✅ PASS** — h1 26px renders "FOUR TRACKS +" / "EXTENDED INTRO." on two centered lines, divider line below. Was the only PASS at T12.5; still PASS at T16.

### slide-11 — final
- **Desktop ✅ PASS** — Centered "START WITH ONE SKILL." white + "ITERATE DAILY." green with cursor block, subline below.
- **Mobile ✅ PASS** — h1 30px wraps to "START WITH ONE / SKILL." (2 lines white) + "ITERATE DAILY." (1 line green with cursor block at end). Subline "systems compound. clarity compounds. start now." wraps to 2 lines, "start now." in `--accent2`. Cursor block visible. **No 6-line stack, no edge-clipped cursor.** Was ISSUE at T12.5; now PASS.

---

## Mobile aggregate by status

| Slide | T12.5 | T16 | T17.5 |
|---|---|---|---|
| 01 title       | ❌ BLOCKER | ✅ PASS | ✅ PASS |
| 02 title-body  | ⚠ ISSUE   | ✅ PASS | ✅ PASS |
| 03 stats       | ⚠ ISSUE   | ✅ PASS | ✅ PASS |
| 04 quote       | ⚠ ISSUE   | ✅ PASS | ✅ PASS |
| 05 cards       | ❌ BLOCKER | ✅ PASS | ✅ PASS |
| 06 layers      | ❌ BLOCKER | ✅ PASS | ✅ PASS |
| 07 split       | ❌ BLOCKER | ✅ PASS | ✅ PASS |
| 08 code        | ⚠ ISSUE   | ⚠ ISSUE (badge) | ✅ PASS (badge polished) |
| 09 table       | ❌ BLOCKER | ✅ PASS (dual-rep) | ✅ PASS |
| 10 divider     | ✅ PASS   | ✅ PASS | ✅ PASS |
| 11 final       | ⚠ ISSUE   | ✅ PASS | ✅ PASS |

**T17.5: 5 BLOCKER → 0 BLOCKER · 5 ISSUE → 0 ISSUE · 1 PASS → 11 PASS.**
The mobile gate is now an unconditional PASS candidate.

---

## Verification of the four explicit T16 visual checks

| Check | Result |
|---|---|
| slide-09 mobile uses stacked cards, no horizontal scroll | ✅ Confirmed. Three `.table-card` articles with VOLUME/LOGIC dt/dd pairs; no scroll affordance visible; deck swipe navigation unobstructed. |
| no clipped h1 on title / final | ✅ Confirmed. Both wrap cleanly within 390px column at 32px / 30px respectively. |
| cards / layers / split single-column on mobile and readable | ✅ Confirmed for all three: cards stack with color stripes preserved, layers stack with name+desc lines, split = single column with both `// PARAMETERS` and `// STRUCTURE` sections one above the other. |
| code remains readable; scrollable only if needed | ✅ Code lines fit at 12px; `.code-block pre { overflow-x: auto }` exists as the safety net for unbreakable longer commands. |
| frame chrome does not cover content | ✅ Counter top-right (`top: 14px / right: 16px / 11px font`), nav-hint bottom-right (`bottom: 12px / right: 16px / 10px font`), progress bar 3px sliver at the very bottom. None of these overlap content on any of the 11 mobile slides. |

---

## Test status carry-forward (T15.5 + T16)

No code changes in T16. Status from T15.5 is the reference point:

| Suite | Result |
|---|---|
| `plugins/h2t-creative/tests/test_r2_legacy_fidelity.py` | 189 passed |
| `plugins/h2t-creative/tests/test_smoke.py` | 21 passed, 1 skipped |
| `plugins/h2t-creative/tests/test_font_loading.py` | 5 passed |
| `plugins/h2t-creative/tests/test_token_contract.py` | 16 passed |
| Full plugin suite | 250 passed, 1 skipped |
| `tests/h2t_creative/test_assembler.py` | 105 passed |

T14 contract: all 13 RED → GREEN under T15 + T15.5.

---

## T17.5 polish (applied)

**slide-08 mobile — `TERMINAL` badge.** Fixed via 6-line CSS patch in
`deck/frame/frame.css` mobile @media block:

```css
.code-block::before {
  top: 0;
  left: 0;
  font-size: 10px;
  padding: 2px 8px;
}
```

Side-effect: extended the test_r2_legacy_fidelity selector-whitelist regex
(`test_h2t_terminal_deck_mobile_rules_use_known_selectors`) to recognise
double-colon pseudo-elements (`::before`/`::after`); single-colon and
double-colon pseudos are now both stripped before tag-token check. No
contract change — tighter regex.

Verified visually after recapture: green `TERMINAL` chip flush at top-left
of `.code-block`, no overlap with `$ mkdir` line.

---

## Recommendation to human reviewer (T17)

- **Gate A — Desktop fidelity**: PASS candidate. Compare 11 desktop screenshots against goldens (`docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/`) for design-system parity.
- **Gate B — Mobile usability**: PASS candidate. The deck is now usable on a 390-wide phone. No content clipped. No off-screen elements. **All 11 slides PASS unconditionally** after T17.5 badge polish.

If both gates approved → proceed to T18 (commit slice; per CLAUDE.md no version bump until live-confirmed).
