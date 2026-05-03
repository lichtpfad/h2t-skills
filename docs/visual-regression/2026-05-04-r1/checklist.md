# h2t-creative R1 Visual Gate

**Status:** PENDING HUMAN REVIEW
**Date:** 2026-05-04

---

## h2t-graphs

**Reference:** `docs/visual-regression/reference/graphs.lichtpfadstudio.com/desktop_20260504_000404.png`
**Candidate:** `h2t-graphs-desktop.png`, `h2t-graphs-mobile.png`

- [ ] HUD panels use 4-corner bracket grammar (L-shaped pseudo-elements, accent color)
- [ ] Grid background is visible but subtle (40px repeating lines)
- [ ] Stats bar is segmented, dense, and uses accent glow on numbers
- [ ] Chips are monospace bordered labels, not pills or rounded cards
- [ ] Mermaid/code/screenshot blocks sit inside HUD frames
- [ ] Typography: Inter headings (700–800) + JetBrains Mono labels/body
- [ ] `cursor: crosshair` visible on hover
- [ ] No generic shared pricing/testimonial/features-grid aesthetic is visible

---

## h2t-mono

**Reference:** `docs/visual-regression/reference/specdesigner.netlify.app/desktop_20260504_000404.png`
**Candidate:** `h2t-mono-desktop.png`, `h2t-mono-mobile.png`

- [ ] Page is near-black (#0d0d0d), sparse, monospace-only
- [ ] Two-column comparison resembles specdesigner structure (1px separator)
- [ ] Comparison table uses sparse borders and colored states (is-good green/red, is-bad strikethrough)
- [ ] Red accent is restrained and singular
- [ ] No HUD brackets, glow panels, rounded cards, or shadows
- [ ] No generic shared pricing/testimonial/features-grid aesthetic is visible

---

## Release Gate

- [ ] **Human confirmed** R1 visual match for h2t-graphs
- [ ] **Human confirmed** R1 visual match for h2t-mono

If any structural item above is marked `[!]` or remains unchecked:
- Do NOT bump minor version
- Do NOT mark R1 as complete
- File an issue describing the discrepancy and return to implementation

**Minor version bump:** only after both profiles are human-confirmed.
