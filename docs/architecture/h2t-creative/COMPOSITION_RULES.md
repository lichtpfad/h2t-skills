# h2t-creative Composition Rules

## Purpose

This document defines composition constraints for generated visual outputs. It prevents a working renderer from producing an unusable landing, deck, report, or carousel.

## Swiss/Grid First

Every output must be planned from grid and rhythm before component selection.

Required grid decisions:

- Canvas or viewport
- Content max-width
- Column model
- Gutters
- Section spacing
- Inner padding
- Dense vs open sections
- Mobile collapse rules

Profile skins may change visual expression, but they must not erase grid discipline.

## Composition Before Recipe

No landing, deck, report, carousel, or interactive page recipe may be implemented before an approved wireframe/composition contract exists.

The contract must define:

- First screen or opening slide
- Section/slide/frame order
- Intent of each section
- Max density per section
- Table/gallery/video placement
- CTA placement
- Desktop representation
- Mobile representation
- Known omissions and placeholders

## Density Rules

Every output needs a density budget.

Default landing constraints:

- 5-8 primary sections
- At most 1-2 dense sections
- Dense tables must be followed by breathing room
- Cards should avoid orphan layouts unless intentionally approved
- CTA must be visually distinct but not stylistically alien
- Evidence should support the flow, not turn the page into an appendix

Default deck constraints:

- One primary idea per slide
- No desktop-only layout assumptions
- Tables require mobile strategy when deck is viewable on mobile
- Speaker/report detail belongs in notes or appendix-style slides

## Responsive Representation

Mobile is not passive resizing.

Required policies:

- Multi-column cards collapse to one column unless explicitly approved.
- Tables use dual representation when horizontal scroll would block usability.
- Video/interactive blocks require fallback.
- CTA remains reachable without becoming sticky unless explicitly approved.
- No hidden essential content.

## Visual QA Must Check Flow

Agent Visual QA must check:

- Does the first screen communicate intent?
- Is the page/slide sequence readable?
- Is vertical rhythm controlled?
- Does density vary intentionally?
- Does the table/media block interrupt the flow?
- Is the CTA located at a useful decision point?
- Does mobile preserve meaning, not just pixels?

## Current #119 Classification

The #119 semantic renderer pilot proves a technical path. The current landing candidate does not prove a landing composition. Treat the screenshots as negative evidence until a wireframe-driven candidate replaces them.
