# ADR 2026-05-19: h2t-creative Architecture Reset

## Status

Accepted.

## Context

h2t-creative v2 attempted to evolve from working legacy landing/deck skills into a modular visual publishing system:

```text
raw context + materials -> structured story -> approved wireframe -> design-system skin -> responsive rendering -> visual/human QA -> publishable output
```

The useful parts of that direction are still valid:

- profile-owned typography, palettes, tokens, and components;
- `DESIGN.md` as machine-readable design-system memory;
- concrete HTML/CSS primitives with manifests and tests;
- wireframe and visual QA gates;
- legacy `sections:` and `slides:` recipes that already produced working references.

The failure was the abstraction-first semantic-CMS path:

```text
content schema -> semantic blocks -> presentation slots -> profile skin -> renderer
```

#119 showed the failure mode clearly. The semantic renderer generated files, but the editorial landing candidate did not work as a landing, did not prove a design system, and did not prove a usable semantic block system. The browser review found only partial visual evidence: fonts and colors survived; composition, responsive behavior, and page purpose failed.

## Decision

h2t-creative is reset to **legacy-first visual publishing**.

For real work, use the working legacy h2t-creative landing/deck assembler path:

```text
DESIGN.md profile
+ proven profile components
+ approved wireframe
+ concrete recipe.yaml
+ Playwright / screenshot QA
+ human review
= publishable output
```

The semantic-CMS / semantic-renderer direction is stopped as a product path. The existing semantic renderer code may remain as historical research evidence, but it must not drive new planning or implementation.

Reusable abstraction may return only after concrete success:

```text
2-3 human-approved outputs
-> identify repeated component and composition patterns
-> document a component/catalog contract
-> optionally extract semantic roles from those proven outputs
```

## Preserved

- Legacy `h2t:landing` / `h2t:deck` workflow and recipe shape.
- R1 h2t-graphs and h2t-mono landing evidence.
- R2a h2t-terminal deck evidence.
- R2b h2t-editorial deck evidence.
- Recovered typography, palettes, tokens, and concrete primitives.
- `DESIGN.md` profile files and Stitch DESIGN.md alignment.
- Wireframe gate and visual QA gate.
- Negative evidence archives and failed screenshots.

## Rejected

- Treating #119 semantic renderer v0 as product proof.
- Starting from a universal semantic block library before a concrete page succeeds.
- Building a private headless CMS inside h2t-skills.
- Using report/appendix structure as a landing structure.
- Claiming visual success from file generation, non-zero screenshots, or component render tests.

## Current Operating Mode

Use h2t-creative as an agentic visual publishing kit, not a CMS.

Rules:

1. Start from a concrete output target: landing, deck, report, carousel, or interactive explainer.
2. Read the profile `DESIGN.md` and known visual evidence.
3. Create a low-fidelity wireframe / composition contract before recipe or CSS work.
4. Get human approval for flow, first screen, density, table/media placement, CTA placement, and mobile strategy.
5. Implement through the simplest proven path, usually legacy `sections:` or `slides:`.
6. Run screenshot-based visual QA.
7. Extract reusable abstractions only after the result passes human review.

## Consequences

- Existing semantic renderer docs and plans are superseded.
- Any future semantic layer proposal must cite at least one human-approved output it was extracted from.
- New block/layout/format work stays possible, but must be concrete-first and governed by `EXTENSION_PROTOCOL.md`.
- The next cleanup step is archival, not implementation: preserve evidence, label superseded plans, and close or rewrite stale issues.

## Related Documents

- `docs/architecture/h2t-creative/EXTERNAL_RESEARCH_2026-05-22.md`
- `docs/archive/h2t-creative/INDEX.md`
- `docs/library/h2t-creative/RECOVERY_MAP.md`
- `docs/protocols/h2t-creative/WIREFRAME_GATE.md`
- `docs/protocols/h2t-creative/VISUAL_QA.md`
