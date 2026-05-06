# Pressure scenarios — legacy-fidelity skill

These are the patterns where the agent or human is tempted to skip a step in
the legacy-fidelity pipeline. Each scenario lists: the temptation, why it
fails, and the rule that closes it. Read this BEFORE closing any visual gate,
not at the end of the slice.

The catalog grew out of R2a — every entry below was either a near-miss or an
actual mistake during PR #95 that the process had to recover from.

---

## 1. "Files exist with non-zero size, capture is done"

**Temptation:** the screenshot tool printed `OK: 22 screenshots written.`
Tasks marked completed. Move on to the human review handoff.

**Why it fails:** filesystem state ≠ visual state. The agent never sees
whether content overflows, clips, stacks 1-word-per-line, or hides the chrome.
In R2a this exact step skipped detection of:
- mobile cards 2 + 3 entirely off-screen (slide-05)
- layer-desc overflow with word-by-word vertical reflow (slide-06)
- table reflow producing 6 visual rows per data row (slide-09)

**Rule:** Agent Visual QA is mandatory before any human review. Open every
screenshot with the `Read` tool. The agent is the FIRST visual review layer;
the human is the FINAL layer. Counting files is not visual QA.

---

## 2. "Mobile is just baseline for #92, not our gate"

**Temptation:** mobile screenshots look bad, but the plan says "mobile is
baseline-only, deferred to #92." Note the breakage in `parity-notes.md` and
move on.

**Why it fails:** "baseline" is not a synonym for "broken". A baseline that
documents catastrophic overflow is not a useful artefact — it just delays the
work. R2a's first parity-notes pass marked 5 BLOCKER + 5 ISSUE + 1 PASS as
"mobile baseline" and almost shipped. That call was wrong.

**Rule:** Two gates. Gate A = desktop fidelity. Gate B = mobile usability.
Mobile gets its own design pass (T14 in R2a) and its own implementation slice
(T15). If mobile widely BLOCKERS, the gate is BLOCKED, not "baseline noted".
The R2a plan had to adopt a two-gate amendment mid-flight; future slices
should plan for both gates from T0.

---

## 3. "@media is forbidden in this profile"

**Temptation:** the test contract bans `@media (max-width:` in deck CSS. So
the deck must adapt without media queries — somehow.

**Why it fails:** without media queries the ONLY way to adapt is JS viewport
branching (banned) or design that ignores narrow viewports (also banned). The
ban itself was the wrong rule. R2a authored this ban in T4 and had to retire
it in T12.5; the right rule is below.

**Rule:**
- Allowed and required: profile-owned `@media (max-width: 480px)` rules in
  deck CSS.
- Forbidden: random mobile redesign that breaks desktop, JS viewport
  branching, hiding essential content, claiming pass without Agent QA.
- Tests enforce the desktop invariants (canonical declarations live OUTSIDE
  `@media`) instead of banning media queries entirely.

---

## 4. "Horizontal scroll is fine for tables"

**Temptation:** mobile tables don't fit. Easy fix: `overflow-x: auto` on the
table wrapper. Test passes, capture passes.

**Why it fails:** in a deck the swipe/keyboard nav already owns horizontal
gestures. A horizontally-scrollable table inside a slide creates two competing
horizontal gesture handlers. On touch devices the user can't tell whether
they're scrolling the table or paginating slides. Bad UX, even though
technically all content is reachable.

**Rule:** prefer **dual-representation** for tables and other inherently
horizontal primitives:
- desktop: `<table>` inside `.table-desktop`
- mobile: stacked `.table-card` articles with `<h3>` (first cell) +
  `<dl><dt><dd>` pairs for the rest
- CSS toggles which representation is visible per viewport
- both reps are always in the DOM — no content hidden, only one rendering
  shown

R2a applied this in T15.5; reference: `_render_table` in `assembler.py`.

---

## 5. "Recipe content can be padding placeholder"

**Temptation:** the validation recipe needs to exercise every layout. Some
layouts are awkward to fill, so use `lorem ipsum` / "TODO: real copy" /
synthetic strings for now.

**Why it fails:** placeholder copy hides layout problems. Real golden content
has specific lengths, line breaks, and emphasis spans (`<span class="accent">…
</span>`) that stress the layout in ways lorem ipsum never does. Catastrophic
mobile breakage in R2a slide-09 was visible only because real merkazim copy
("Intro + first 2 sessions of one track.") was used.

**Rule:** every recipe slide must use content lifted from approved goldens or
from the plan §4 recipe contract. A test (`_no_synthetic_copy`) scans for
banned phrases (`lorem ipsum`, `todo`, `placeholder`, `synthetic`, etc.) so
this can't drift.

---

## 6. "Single-file output means everything inline"

**Temptation:** "single-file deck" means index.html should have zero `<link>`
elements. Strip the Google Fonts preconnect/link too.

**Why it fails:** terminal deck cannot self-host JetBrains Mono inline at any
acceptable size — the woff2 alone is hundreds of KB. The web font has to load
from a CDN. The single-file rule is about **app code**, not about font assets
or browser-affordance hints.

**Rule:**
- Allowed: `<link rel="preconnect" href="https://fonts.googleapis.com">`,
  `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`,
  `<link rel="stylesheet" href="https://fonts.googleapis.com/...">` (Google
  Fonts only)
- Forbidden: `<link rel="stylesheet" href="base.css">`,
  `<link rel="stylesheet" href="profile.css">`, any non-fonts CSS link, any
  `<script src="...">` whatsoever

Tests scope to "non-Google-Fonts stylesheet links" specifically.

---

## 7. "Layout owns its wrapper" (or does it?)

**Temptation:** the recipe author is comfortable with HTML, so let the
recipe's `code_html` field include the outer `<pre>` itself for explicitness.

**Why it fails:** if some recipes include `<pre>` and others don't, the
layout HTML can't decide whether to wrap. Either it always wraps (causes
nested `<pre><pre>` for the verbose recipes) or it never wraps (silently
breaks the formatting of the terse ones).

**Rule:** the layout owns the structural wrapper; the recipe owns inner
content only. For the code layout: `code/code.html` has `<pre>{{ code_html | safe }}</pre>`,
recipe `code_html` is inner code lines / spans only. Tests assert exactly one
`<pre>` per code slide and zero nested-`<pre>` sequences.

R2a established this in T5.1 after recipe-author confusion.

---

## 8. "Test the agent's intent, not its output"

**Temptation:** the agent says "tokens declared correctly". Mark the contract
test as passing.

**Why it fails:** the test framework doesn't read agent self-reports. A
declarative test must scan the actual artefact (CSS file, HTML output,
manifest YAML) for the exact substring or structure it requires. R2a had two
near-misses where the agent wrote the test based on the agent's own claim
about what was implemented; both had to be re-grounded against the real file.

**Rule:** every contract test reads bytes from disk or strings from
assembled output. Substring / regex / parsed-structure assertions only. No
`assert agent_said_so`.

---

## 9. "I already opened similar screenshots, this batch will be the same"

**Temptation:** previous capture set passed; this re-capture is just a tweak.
Skip opening the new PNGs.

**Why it fails:** even single-rule CSS changes can introduce surprising
regressions (font fallback chain shift, cascade order change, sub-pixel
clipping at different viewports). R2a's T16 captured 22 fresh PNGs after T15
mobile CSS landed; only by opening them did the agent notice the TERMINAL
badge was missing on mobile (slide-08), which was then fixed in T17.5.

**Rule:** every capture round triggers a fresh Agent Visual QA pass. No
"trust the previous round". Open every screenshot from the current build.

---

## 10. "Ship now, polish later"

**Temptation:** the slice is mostly done. Outstanding ISSUE on one slide is
small. File a follow-up, ship, fix later.

**Why it fails:** in legacy fidelity work the cost of the polish is usually
6-line CSS + one recapture (R2a's T17.5 was exactly that), and the cost of
shipping with the ISSUE is a parity-notes entry that humans will read at
review time and ask "why didn't you just fix it?". The follow-up almost
always lands inside the same review cycle anyway, with extra coordination
overhead.

**Rule:** if the fix is local (≤10 lines, no contract changes, no test
churn), apply it before commit. If the fix requires a design decision (e.g.
"change the desktop default left inset"), file it as a separate follow-up
deliberately — that's a different decision class, not "polish".

R2a applied this rule: T17.5 (badge polish) was bundled in; T17.6
(infrastructure handle for inset tuning) was bundled in but with default
unchanged; T21 (actual default inset change) was filed as separate
follow-up because it is a visual-tuning decision.

---

## How to use this catalog

- During TDD slices: skim the relevant scenario before writing the test for
  that area (e.g. scenario #4 before writing the table mobile test).
- Before Agent Visual QA gate: re-read scenarios #1, #2, #9.
- Before commit: re-read scenarios #5, #7, #10.
- When tempted to "just" do something: pause, find the matching scenario,
  apply the rule.
