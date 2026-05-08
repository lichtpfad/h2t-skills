# h2t-creative Visual QA

## Purpose

Visual QA verifies meaning, composition, rhythm, and responsive behavior. It is not a file-existence check and not a component-rendering check.

## Required Gates

### Gate A — Desktop Composition

Check:

- First screen communicates page intent.
- Grid alignment is intentional.
- Vertical rhythm is controlled.
- Dense and open sections alternate intentionally.
- Tables/media do not interrupt flow.
- CTA is visible at a useful decision point.
- The result matches the approved wireframe.

### Gate B — Mobile Usability

Check:

- Meaning is preserved.
- Multi-column sections collapse correctly.
- Tables use mobile representation when needed.
- No horizontal overflow for essential content.
- No clipped headings or text.
- CTA remains discoverable.
- The result matches the approved mobile wireframe.

### Gate C — Style Fidelity

Check:

- Profile typography is applied.
- Tokens/palette match source arbitration.
- Surfaces, borders, motion, and chrome match profile intent.
- No leakage from other profiles.

## Verdicts

Use:

- PASS
- PASS with ISSUE
- ISSUE
- BLOCKER

Every issue must include:

- Visible symptom
- Location
- Suspected cause
- Whether it is composition, style, responsive, content, or renderer

## Screenshot Rules

- Open screenshots visually before writing verdict.
- Confirm screenshot timestamps are newer than build output.
- Preserve failed screenshots as negative evidence when they reveal process errors.
- Do not claim PASS from non-zero PNG size.

## Renderer Pass Is Not Visual Pass

If a semantic recipe renders all blocks but the page reads as a technical proof, report:

- Semantic pipeline: PASS
- Landing/deck composition: FAIL or BLOCKED

This distinction is mandatory.
