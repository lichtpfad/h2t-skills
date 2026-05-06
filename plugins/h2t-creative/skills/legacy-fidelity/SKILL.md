---
name: legacy-fidelity
description: "Recovers a legacy h2t-creative profile (deck or landing) into the modular form-v2 structure with verified visual fidelity. Drives the work as TDD with two visual gates (Desktop Fidelity + Mobile Usability) and mandatory Agent Visual QA on every screenshot before human review. Triggers: 'recover profile', 'legacy fidelity', 'restore golden', 'h2t-creative:legacy-fidelity'. Reference exemplar: R2a (terminal deck, PR #95)."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# h2t-creative: legacy-fidelity

Recover a legacy profile from approved golden HTML/CSS sources into the modular
form-v2 layout (`profiles/<name>/{deck|landing}/...` + manifests + tests +
validation recipe), preserving desktop fidelity and producing a usable mobile
experience as a separate visual gate.

The canonical reference is **R2a** (terminal deck): plan
`docs/superpowers/plans/2026-05-05-r2a-h2t-terminal-deck-modularization.md`,
PR `lichtpfad/h2t-skills#95`, commits `da2f47f` (recovery) + `4c40973` (bump).

## Core principles

1. **TDD first.** Every contract (token list, layout coverage, frame chrome,
   forbidden patterns, mobile adaptation) ships as a test before the CSS / HTML
   / JS that satisfies it.
2. **Two visual gates, not one.** Desktop fidelity and mobile usability are
   independent gates with their own acceptance criteria. Mobile is **never** a
   passive baseline.
3. **Agent Visual QA is the first review layer, always.** Before any human
   visual review, the agent must open every screenshot itself with computer
   vision and write a per-slide PASS / ISSUE / BLOCKER trail. "All N PNGs
   exist with non-zero size" is not visual QA. If the model cannot see the
   screenshots, the gate is BLOCKED, not passed.
4. **No version bump until live confirmation.** Per `~/.claude/CLAUDE.md` the
   plugin minor version bumps in a separate `chore` commit, after a human has
   live-tested the build in a real browser.

## Pipeline

```
T0 caller-inventory → T1..Tn TDD slices → Tk visual capture
                    → Tk.5 Agent Visual QA → Tk+1 human review
                    → final commit (no bump) → live-verify → bump commit
```

### T0 — Caller inventory
Grep every consumer of `assemble_*` (or whatever public API you are about to
modify) before changing the signature. Capture argument order, return value,
and any side-effects callers depend on. Decide: preserve signature, or patch
all callers in the same slice.

### T1..Tn — TDD slices
Order each slice red → green → refactor. Slice boundaries used in R2a:
- Assembler form switch + helper unit tests
- File-based slide layout loader + dual-representation table helper
- Tokens + palette + frame primitives + scanlines
- Per-layout HTML/CSS/manifest (one slice per group of layouts is fine)
- Navigation JS exposing `window.showSlide(idx)` for deterministic capture
- Validation recipe covering every layout
- Source dossier (`references.yaml` + reference screenshots)
- Forbidden-pattern + frame-chrome + single-file output guards

Write tests **before** the file edits that satisfy them. Run them and confirm
they go RED, then implement, confirm they go GREEN.

### Tk — Visual capture
Build the validation deck/landing once. Capture all slides at the two
viewports (desktop = 1440×900, mobile = 390×844 with iPhone UA + touch). Use
`tools/deck-screenshot-all.py` for decks (drives `window.showSlide(i)`); for
landings, use `h2t-tools:screenshot` per page.

### Tk.5 — **Agent Visual QA (MANDATORY)**
Open every screenshot with the `Read` tool (computer-vision read). For each
slide write to `parity-notes.md`:

- desktop status: PASS / ISSUE / BLOCKER + the exact visible problem
- mobile  status: PASS / ISSUE / BLOCKER + the exact visible problem

If mobile is widely BLOCKED, propose a mobile adaptation contract before
implementing it (T14-style). If pressure-scenarios from the references file
apply, name them explicitly so they cannot drift quietly.

### Tk+1 — Human review
Hand the human the parity-notes + the live URL. Stop until they ack each gate.

### Tn+1 — Commit slice
Single squashed `feat(...)` commit. **No version bump.** Push only after
explicit instruction.

### Tn+2 — Live verify → bump
After the human has opened the build in a browser and confirmed keyboard +
swipe + hash + all slides + no regressions, bump the plugin version with
`scripts/bump_plugin.py <name> <next-minor>` in a separate
`chore: bump version after <slice> live verification` commit.

## Visual gates

**Gate A — Desktop fidelity.** All slides at 1440×900 must match the design
system and approved goldens. Token contract, typography scale, frame chrome,
component primitives all preserved.

**Gate B — Mobile usability.** All slides at 390×844 must render without:
- horizontal overflow (except inside explicitly scrollable containers like
  `.code-block pre` or a deliberate dual-representation card list)
- clipped text (no cut headlines, no off-screen content)
- multi-column layouts that produce 1-word-per-line stacks
- frame chrome covering content

Allowed and expected:
- profile-owned `@media (max-width: 480px)` rules in deck/landing CSS
- mobile-specific layout collapse (cards stack, layers stack, split → 1fr)
- alternative mobile representations rendered alongside desktop, toggled via
  CSS (e.g. dual-representation table — see references)

Forbidden:
- random mobile redesign that breaks desktop fidelity
- viewport-driven JS hacks (`matchMedia`, `innerWidth` reads)
- hiding essential slide content on mobile (`display: none` on .slide /
  .slide-inner / h1 / h2 / .body etc.)
- claiming a mobile pass without Agent Visual QA reading every PNG

## Test contract patterns

Mirror the structure used in R2a's
`plugins/h2t-creative/tests/test_r2_legacy_fidelity.py`:

| Group | Asserts |
|---|---|
| Source dossier | `references.yaml` exists, parses, lists golden source ids; reference screenshots exist |
| Token contract | All canonical tokens declared with exact values |
| Layout coverage | All N layouts present (HTML + CSS + manifest); manifest parses; recipe exercises every layout exactly once |
| Single-file / two-file output | Output is the expected file set, no extras |
| Frame contract | Required chrome IDs land in assembled output; `<html lang>` matches recipe |
| Forbidden patterns | No emoji in layout HTML, no mermaid refs, no `cursor: crosshair`, no slide-container `border-radius` |
| Mobile adaptation | Breakpoint exists; desktop core declarations live OUTSIDE `@media`; mobile rules cover slide padding + h1/h2 + horizontal-row primitives + table + chrome; selectors limited to known classes/ids |
| JS contract | Required key bindings + swipe + hash sync + `window.showSlide` exposed; no viewport branching |
| Render smoke | Each layout renders from minimal recipe content |

## Tooling

- **`tools/deck-screenshot-all.py`** — deterministic per-slide capture for
  deck-form profiles. Drives `window.showSlide(i)` after `document.fonts.ready`,
  waits for `.slide.active`, snapshots each viewport. Required because the
  generic `h2t-tools:screenshot` only captures the first slide.
- **`scripts/bump_plugin.py <plugin> <semver>`** — single source of truth for
  version bumps; updates both `plugins/<name>/.claude-plugin/plugin.json` and
  the root `marketplace.json`.

## Common drift / pressure scenarios

See [`references/pressure-scenarios.md`](references/pressure-scenarios.md) —
catalogued patterns where the agent or human is tempted to skip a step.
Re-read this list when an Agent Visual QA gate is about to close, not at the
end of the slice.

## Output (what landing this skill produces)

A single self-contained slice in branch `codex/<repo-short>-<slice-id>`:

- profile dir under `plugins/h2t-creative/profiles/<name>/{deck|landing}/`
- validation recipe at `plugins/h2t-creative/profiles/<name>/validation/recipe-*.yaml`
- source dossier at `plugins/h2t-creative/profiles/<name>/sources/`
- new test file `plugins/h2t-creative/tests/test_<slice-id>_legacy_fidelity.py`
- screenshots + `parity-notes.md` under `docs/visual-regression/<date>-<slice>/`
- one `feat(...)` commit + (after live confirm) one `chore(...)` bump

## Reference

- Reference exemplar: R2a / PR #95 / commits `da2f47f` + `4c40973`
- Plan: `docs/superpowers/plans/2026-05-05-r2a-h2t-terminal-deck-modularization.md`
- Process amendment that established the two-gate model:
  `parity-notes.md` § T12.5 history
- Pressure scenarios: `references/pressure-scenarios.md` (this skill)
