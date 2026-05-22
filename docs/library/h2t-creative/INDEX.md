# h2t-creative Library Index

This is the canonical index for reusable h2t-creative roles, components, layouts, formats, and extension rules.

For post-reset reuse rules, see `docs/library/h2t-creative/RECOVERY_MAP.md`.

## Semantic Roles

Initial universal roles:

- `hero`
- `proof`
- `problem`
- `solution`
- `features`
- `process`
- `comparison`
- `gallery`
- `video`
- `case_study`
- `testimonials`
- `pricing`
- `faq`
- `evidence`
- `cta`
- `footer`

Roles describe intent, not implementation.

## Formats

Current and planned formats:

- Landing
- Deck / presentation
- Report / appendix
- Microsite
- Instagram carousel
- LinkedIn document carousel
- Story format
- One-page PDF
- Interactive explainer
- Video/script storyboard

Each format needs a format spec before production use.

## Component Categories

- Navigation/header
- Hero/page-header
- Proof/stats
- Card grids
- Comparison tables
- Process/flow
- Evidence/details
- CTA
- Media/gallery/video
- Interactive visuals
- Footer

## Governance

Before creating a new library entry:

1. Run reuse-before-create.
2. Define schema and behavior.
3. Define desktop/mobile policy.
4. Add tests.
5. Add visual QA checklist.
6. Add this index entry.

Human approval is required for new roles, new formats, and interactive primitives.

## Current Known Implementations

- h2t-graphs: mature landing component library from R1.
- h2t-mono: mature landing component library from R1.
- h2t-terminal deck: mature deck component/layout library from R2a.
- h2t-editorial deck: mature System B deck library from R2b.
- h2t-editorial landing primitives: partial evidence only; the #119 semantic landing candidate is rejected and must not be treated as a reusable semantic foundation.

## External Standards

- **Stitch DESIGN.md** (Apache 2.0, Google Labs 2026) — open-standard format that every profile `DESIGN.md` conforms to. Reference summary: `docs/superpowers/references/stitch-design-md-spec-reference.md`. Upstream repo: https://github.com/google-labs-code/design.md.
