# h2t-creative Wireframe Gate

## Purpose

The Wireframe Gate prevents agents from jumping from content or extracted primitives directly to recipe/CSS implementation.

It is mandatory for:

- Landing pages
- Decks and presentations
- Reports and appendices
- Carousels
- Interactive explainers
- New formats
- Significant redesigns

## Inputs

- Target audience
- Output format
- Content/context summary
- Available materials
- Profile/style target
- Required actions or CTA
- Known constraints

## Required Wireframe Artifact

The agent must produce a low-fidelity wireframe/composition contract before implementation.

It must include:

- Format and canvas/viewport
- Section/slide/frame order
- Intent of each block
- Desktop layout
- Mobile layout
- Grid and max-width decisions
- Vertical rhythm expectations
- Dense sections and density budget
- Table/gallery/video/interactive placement
- CTA placement
- Required assets and missing assets
- Explicit "not this" negative examples when relevant

For landing pages specifically, the format-specialised shape of this artefact is defined in `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`. Reviewers run the checklist at `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md`. Sibling format-specific contracts (deck, report, carousel, interactive) follow the same pattern as they are added.

## Human Approval

The human must approve the wireframe before recipe, CSS, component, or layout work begins.

Approved means the human accepts:

- Flow
- First screen/opening slide
- Block order
- Density
- Table/media placement
- CTA placement
- Mobile strategy

Without approval, implementation is blocked.

## Forbidden Before Approval

- Writing final recipe
- Editing production CSS for the target page
- Adding new component/layout for the target page
- Claiming visual direction is accepted
- Copying a source appendix/report structure as a landing structure

## Outputs After Approval

The approved wireframe becomes:

- Recipe implementation checklist
- Visual QA checklist
- Test guardrails where practical
- Reference for human review

## Current #119 Lesson

#119 proved the semantic renderer path but failed as a landing candidate because recipe implementation happened before an approved landing wireframe. Future work must classify that result as a technical proof and negative composition evidence.
