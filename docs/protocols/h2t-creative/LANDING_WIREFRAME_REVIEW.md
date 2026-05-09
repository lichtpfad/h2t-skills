# h2t-creative Landing Wireframe Review

## Purpose

This is the human reviewer's pass/fail checklist for a landing wireframe submitted under `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`.

The reviewer does not author the wireframe. The reviewer verifies it. Approval is binary: every item passes, or the wireframe returns to the author.

## When To Run This Review

- Before any recipe / CSS / component work begins for a landing page.
- On every wireframe revision (re-approval is mandatory after changes).
- When a stakeholder challenges an in-flight implementation: roll back to the most recently approved wireframe.

## Checklist

For each item: PASS, FAIL, or N/A. Any FAIL returns the wireframe.

### A. Structural completeness

- [ ] **A1.** Mode declared, in `KNOWN_MODES` (`product`, `service`, `editorial`, `report`, `portfolio`, `deck-companion`).
- [ ] **A2.** Block sequence: 5–8 entries; every entry in `KNOWN_BLOCK_TYPES`.
- [ ] **A3.** First block (after optional `nav`) is `hero`.
- [ ] **A4.** At least one CTA-bearing block present.
- [ ] **A5.** Per-block intent stated for every block. Not "show stats" — what the stats argue and to whom.
- [ ] **A6.** Per-block density classified (`dense` / `medium` / `open`) for every block.
- [ ] **A7.** Desktop layout sketch present, with content max-width and column model declared.
- [ ] **A8.** Mobile representation declared per block (`stack` / `collapse-to-1col` / `collapse-to-cards` / `hide` / `media-fallback`).
- [ ] **A9.** Source classification stated for every block (`target` / `primitive source` / `negative`).
- [ ] **A10.** Asset inventory present: required + missing lists.

### B. Density and rhythm

- [ ] **B1.** Total block count: 5–8.
- [ ] **B2.** Dense blocks: ≤ 2.
- [ ] **B3.** Dense blocks not adjacent to other dense blocks (every dense followed by medium or open).
- [ ] **B4.** Hero is `open` density.
- [ ] **B5.** First-screen content (hero + first body block) communicates intent without scrolling.

### C. Forbidden content scan

- [ ] **C1.** No production / final copy locked into the wireframe. Representative draft copy (sample headline, CTA label, table column labels, one-line body per block) IS allowed — and recommended — provided each instance is explicitly marked `(non-final)`. A reviewer rejects only when the copy is presented as production-ready, not when it serves as load-bearing structural sample.
- [ ] **C2.** No specific hex colors or specific font sizes (profile `DESIGN.md` owns those).
- [ ] **C3.** No component implementation details (HTML class names, manifest field names).
- [ ] **C4.** No pixel-perfect layout — wireframe is intentionally low-fidelity.
- [ ] **C5.** No one-off CSS overrides described.
- [ ] **C6.** No JavaScript / interactive state machine implementation.

### D. Failure-mode awareness

- [ ] **D1.** If the project's negative-evidence record contains a relevant failure (e.g. `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/`), the wireframe acknowledges it under "Negative examples".
- [ ] **D2.** Block source classification is not entirely `primitive source` (would be a primitive showcase, the #88 failure mode).
- [ ] **D3.** Block sequence is not a verbatim copy of an appendix or report structure (per `WIREFRAME_GATE.md` § Forbidden Before Approval).

### E. Profile compatibility

- [ ] **E1.** Chosen profile's `DESIGN.md` Restrictions section is not violated by the proposed block density or content shape.
- [ ] **E2.** Chosen profile's `skins/landing.yaml` (if it exists yet) maps every block role in the sequence; or, if absent, the wireframe identifies which roles the skin will need to add and notes them as a prerequisite slice.
- [ ] **E3.** Required assets exist or have an explicit placeholder + deadline.

## Verdicts

- **APPROVED** — every item PASS or N/A. Recipe authoring may begin.
- **CHANGES REQUESTED** — at least one FAIL. Reviewer returns the wireframe with the failed-item numbers and a one-sentence note per failure. Author revises and resubmits.
- **SCOPE-CREEP REJECT** — the wireframe contains forbidden content (Section C). Reviewer returns it with "return to wireframe stage; this is implementation". No partial approval.

## Audit Trail

Record the verdict, the reviewer's name/handle, the wireframe revision identifier (commit SHA), and the date alongside the wireframe artefact. The recipe author cites this audit trail in the recipe PR description.

## Cross-References

- `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` — the contract this review verifies.
- `docs/protocols/h2t-creative/WIREFRAME_GATE.md` — the generic gate.
- `docs/protocols/h2t-creative/VISUAL_QA.md` — the next gate, run after the rendered page exists.
