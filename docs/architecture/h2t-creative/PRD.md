# h2t-creative PRD

## Product Definition

h2t-creative is an AI-copilot visual publishing system. Its purpose is to turn raw context, research, notes, images, tables, video, and project material into publishable visual representations in an approved H2T aesthetic.

The system must support:

- Landing pages
- Decks and presentations
- Reports and appendices
- Microsites
- Social/document carousels
- Interactive explainers
- WebGL/WebGPU/generative visual blocks

The product is not just an assembler, not just a style library, and not just a renderer. The renderer is one layer inside a larger workflow:

`raw context + materials -> structured story -> approved wireframe -> design-system skin -> responsive rendering -> visual/human QA -> publishable output`

## Core Workflows

### 1. Content To Representation

Input:

- Concept, project, research, transcript, notes, or raw docs
- Optional media: images, video, tables, numbers, diagrams
- Intent: explain, sell, teach, document, compare, pitch, or publish

Required flow:

1. Analyze content and extract narrative/information architecture.
2. Choose representation format: landing, deck, report, carousel, or interactive explainer.
3. Identify required materials: tables, images, video, diagrams, CTA, proof, evidence.
4. Create a low-fidelity wireframe/composition proposal.
5. Get human approval.
6. Implement recipe/skin/component changes within approved constraints.
7. Build desktop/mobile.
8. Run Agent Visual QA.
9. Run human live review.

### 2. Visual Reference To Design System

Input:

- Golden HTML/CSS
- Screenshots
- Existing sites or decks
- Brand references or moodboards

Required flow:

1. Source arbitration: choose canonical visual source and demote secondary sources.
2. Extract typography, color, grid, rhythm, surfaces, motion, components, and responsive rules.
3. Separate style source from layout target.
4. Create or update profile tokens, palettes, components, and tests.
5. Prove fidelity with desktop and mobile visual gates.

### 3. Existing Style To New Output

Input:

- Existing profile/skin
- New content
- Target output format

Required flow:

1. Run content analysis.
2. Reuse existing roles/components before creating new ones.
3. Create wireframe and obtain human approval.
4. Render through profile skin.
5. Validate composition and responsive behavior.

### 4. Library Extension

When a project requires a missing block, layout, or format, the system must extend the formal library instead of adding one-off HTML.

Every extension must define:

- Semantic purpose
- Fields/schema
- Desktop behavior
- Mobile behavior
- Grid/rhythm constraints
- Visual QA checklist
- Tests
- Library index entry

### 5. Interactive Visuals

Interactive visuals are first-class publishing primitives, not ad-hoc scripts.

Supported direction:

- WebGL/Three.js
- WebGPU
- Generative canvas
- Data visualization
- Interactive diagrams
- Video and gallery blocks

Every interactive primitive must have a fallback and mobile/performance policy.

## Non-Goals For v0

- Full CMS database
- WYSIWYG editor
- Arbitrary no-code page builder
- Unbounded user-provided JavaScript
- Pixel-perfect reproduction of every source page as a landing target

## Product Principle

Primitive extraction is not composition. A page is not approved because its components render. A page is approved only when its information architecture, wireframe, rhythm, responsive behavior, and visual style pass the agreed gates.
