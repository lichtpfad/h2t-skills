# h2t-creative ROOT GUIDE

This is the first document to read before any h2t-creative task.

h2t-creative is an AI-copilot visual publishing system. It is not just an HTML generator and not just a component library. The product turns raw context and materials into approved visual representations: landings, decks, reports, carousels, and interactive explainers.

## Required Reading By Task

For any h2t-creative task:

1. Read this guide.
2. Read `docs/architecture/h2t-creative/PRD.md`.
3. Read `docs/architecture/h2t-creative/CORE_SYSTEM.md`.
4. Read the relevant protocol:
   - Landing/deck/page work: `docs/protocols/h2t-creative/WIREFRAME_GATE.md`
   - Visual review: `docs/protocols/h2t-creative/VISUAL_QA.md`
   - New block/layout/format: `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md`
5. Read the profile `DESIGN.md` and source dossier for the affected profile.

## Canonical Architecture Docs

- `docs/architecture/h2t-creative/PRD.md` — product intent and workflows.
- `docs/architecture/h2t-creative/CORE_SYSTEM.md` — runtime, profiles, recipes, renderer, and evidence taxonomy.
- `docs/architecture/h2t-creative/COMPOSITION_RULES.md` — Swiss grid, rhythm, density, and composition constraints.
- `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md` — adding blocks, layouts, formats, and interactive primitives.
- `docs/library/h2t-creative/INDEX.md` — library index stub for roles, components, formats, and governance.

## Evidence Taxonomy

Do not treat every historical artifact as a target.

- Canonical source: approved architecture, profile docs, source dossiers, and current successful visual evidence.
- Historical: old plans and specs that explain why a decision was made, but do not override current protocol.
- Negative evidence: failed attempts that must not be copied as positive examples.
- Runtime source: code and tests on disk always override handoff notes.

## Current Known Evidence

- R1 graphs/mono landing recovery: useful component and style evidence.
- R2a terminal deck: successful fidelity and mobile adaptation precedent.
- R2b editorial deck: successful System B deck precedent.
- #119 semantic renderer v0: useful technical renderer proof.
- #119 editorial semantic landing visual candidate: failed landing composition; keep as negative evidence until replaced by an approved wireframe-driven candidate.

## Non-Negotiable Gates

- Source arbitration before design-system extraction.
- Wireframe/composition approval before landing, deck, report, carousel, or interactive recipe implementation.
- Visual QA after screenshots, not just after build.
- Human review before minor version bump or publishable visual claim.
- Reuse-before-create before adding a new block, layout, or format.

## Worktree Notes

Worktrees can contain newer context than the main checkout. Verify the real branch and files before acting. Runtime state, git log, and issues are more reliable than memory or handoff text.
