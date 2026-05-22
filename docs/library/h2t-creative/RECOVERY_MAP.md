# h2t-creative Recovery Map

## Purpose

This map says what to keep, what to freeze, and what to avoid after the 2026-05-19 architecture reset.

It is a practical companion to `docs/architecture/h2t-creative/ADR-2026-05-19-creative-reset.md`.

## Keep And Use Now

| Asset | Location | Why |
|---|---|---|
| Legacy landing recipe flow | `plugins/h2t-creative/skills/landing/SKILL.md` and `assembler.py` `sections:` path | Known working production path. |
| Legacy deck recipe flow | `plugins/h2t-creative/skills/deck/SKILL.md` and `assembler.py` `slides:` path | Known working deck path. |
| h2t-graphs profile | `plugins/h2t-creative/profiles/h2t-graphs/` | Mature landing profile from R1. |
| h2t-mono profile | `plugins/h2t-creative/profiles/h2t-mono/` | Mature landing profile from R1. |
| h2t-terminal deck profile | `plugins/h2t-creative/profiles/h2t-terminal/deck/` | Successful deck/mobile precedent. |
| h2t-editorial deck profile | `plugins/h2t-creative/profiles/h2t-editorial/deck/` | Successful System B deck precedent. |
| `DESIGN.md` profile docs | `plugins/h2t-creative/profiles/*/DESIGN.md` | Canonical design-system memory. |
| Visual QA protocol | `docs/protocols/h2t-creative/VISUAL_QA.md` | Required guard against false PASS. |
| Wireframe gate | `docs/protocols/h2t-creative/WIREFRAME_GATE.md` | Required guard against implementation before composition. |

## Keep But Freeze

| Asset | Location | Rule |
|---|---|---|
| Semantic renderer code | `plugins/h2t-creative/renderer/` | Do not extend unless extracted from concrete approved output. |
| Editorial landing skin | `plugins/h2t-creative/profiles/h2t-editorial/skins/landing.yaml` | Historical / partial evidence. Do not use as foundation. |
| Semantic tests | `plugins/h2t-creative/tests/test_semantic_*`, `test_skin_loader.py`, `test_field_mapper.py` | Preserve for context; do not treat as product acceptance. |
| 2026-05-08 semantic spec and plan | `docs/superpowers/specs/2026-05-08-h2t-creative-semantic-rendering-architecture.md`, `docs/superpowers/plans/2026-05-08-h2t-creative-semantic-renderer-v0.md` | Superseded; read only for history. |

## Keep As Partial Evidence

| Asset | Location | Reuse condition |
|---|---|---|
| h2t-editorial landing primitives | `plugins/h2t-creative/profiles/h2t-editorial/components/` | Reuse only after an approved concrete landing wireframe. |
| h2t-editorial tokens/palettes | `plugins/h2t-creative/profiles/h2t-editorial/tokens.css`, `palettes/` | Visual ingredients only; not a page system. |
| Source dossiers | `plugins/h2t-creative/profiles/*/sources/` | Use for source arbitration, not layout copying. |

## Do Not Use As A Target

| Asset | Reason |
|---|---|
| #119 semantic landing candidate | Failed as landing, design system, and semantic block proof. |
| #88 editorial landing attempt | Report/appendix structure drifted into landing implementation. |
| Semantic-CMS architecture as implementation plan | Superseded by browser review and ADR reset. |
| Component render tests alone | They do not prove page composition or mobile behavior. |

## Minimal Future Path

For the next real landing:

1. Pick a real target page and audience.
2. Pick an existing working profile: likely `h2t-graphs` or `h2t-mono`.
3. Draft a low-fidelity wireframe.
4. Get human approval.
5. Implement with legacy `sections:` recipe.
6. Build and capture desktop/mobile.
7. Run visual QA and human review.
8. Only then extract any reusable abstraction.

For the next real deck:

1. Pick `h2t-terminal` or `h2t-editorial` deck profile.
2. Use `slides:` recipe.
3. Capture slide screenshots and keyboard/menu navigation.
4. Keep abstractions inside the deck profile until repeated by multiple approved decks.

## Cleanup Queue

- Mark remaining creative-v2 / modularization plans as superseded where applicable.
- Close or rewrite issues that still assume semantic-CMS as the target.
- Remove stale worktrees only after their evidence is indexed.
- Keep negative evidence archives reachable from `docs/archive/h2t-creative/INDEX.md`.
