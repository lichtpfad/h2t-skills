# h2t-creative semantic rendering — prior art references

## Why this exists

Future agents working on the h2t-creative semantic renderer (v0 and beyond) should read this document **before T1 / T2** and before opening the architecture spec.

The architecture spec (`docs/superpowers/specs/2026-05-08-h2t-creative-semantic-rendering-architecture.md`) contains the same prior-art appendix in §15, but burying it inside a 565-line spec hurts discoverability. This standalone reference exists so a future agent can `grep` or `Read` it directly without having to know which spec to open.

When you find this file via grep / Skill discovery / search:

1. Start here, not the architecture spec.
2. After 5 minutes of skimming this, decide if you need the full architecture spec.
3. Don't re-research these systems unless this reference is older than 12 months from the date you're reading it.

## Sources

| System | Purpose / what it teaches | Reference |
|---|---|---|
| **Storyblok** content modeling / blocks | Headless CMS with `component` (block) + `schema` (key-value field map) + `is_root` / `is_nestable` distinctions; canonical "block as self-contained reusable element" model. | `https://www.storyblok.com/docs/concepts/content-modeling`, `https://www.storyblok.com/docs/concepts/blocks` · Context7: `/websites/storyblok` (1287 snippets, score 69, verified 2026-05-08). |
| **Contentful** content model / fields / references | Headless CMS with `ContentType` carrying a `Fields` list; field types (Text / Symbol / Asset / Link / Array / RichText / …) and per-field validators (`MimeTypeValidator`, `LinkContentTypeValidator`, regex). Best evidence that "structure separated from frontend" is a workable pattern. | `https://www.contentful.com/help/content-model-and-content-type/`, `https://www.contentful.com/help/fields/` · Context7: `/websites/contentful_developers` (7370 snippets, score 88.3, verified 2026-05-08). |
| **Gutenberg** (WordPress Block Editor) `block.json` / edit-save separation | `registerBlockType({edit, save})` separates the editor experience from the persisted render output. Also `block.json` `attributes:` map matches our slot-contract shape. | `https://developer.wordpress.org/block-editor/getting-started/fundamentals/registration-of-a-block`, `…/block-json` · Context7: `/websites/developer_wordpress_block-editor` (5246 snippets, score 71.35, verified 2026-05-08). |
| **Portable Text** custom blocks | Sanity's structured-block JSON format with custom block types and portable rendering. Confirms that block content can be authored as data and rendered anywhere. | `https://www.portabletext.org/` · Context7: `/portabletext/react-portabletext` (resolved, niche, not queried in detail). |
| **Block Protocol** (idea, when later available) | Blocks as interoperable units receiving structured data from a host application. Direct Context7 library not present at the time of writing; revisit if it becomes available. | `https://blockprotocol.org/spec` · Context7: NO direct match (2026-05-08); Gutenberg used as the closest queryable substitute. |

## Mapping table

| External concept | h2t-creative term |
|---|---|
| Component / block | semantic block |
| Content type / story / page | semantic recipe |
| Fields / attributes | slots |
| Theme / frontend renderer | skin |
| Validation rules | slot validators |
| Asset / link fields | asset model |
| Editor preview | visual QA (Agent Visual QA + screenshots) |

## Adopted

- **Schema-as-data.** Slot contracts live in `profiles/<p>/skins/<format>.yaml`, not in Python. Same shape principle as Storyblok's `schema: {field: {type, pos}}` and Gutenberg's `attributes: {field: {type}}`.
- **Edit / render separation.** Recipe is the persisted "save" output; the renderer's interpretation is the "edit-time-equivalent" — same separation principle as Gutenberg's `edit` / `save`.
- **Field validation as data, not code.** Per-slot validators expressed in the skin YAML. Shallow in v0 (required / optional, asset existence); architecture leaves room for richer validators by extending the skin schema with a `validations:` key. Same data-not-code principle as Contentful's `Validations: [LinkContentTypeValidator, MimeTypeValidator, …]`.
- **Root vs nestable distinction.** Storyblok's `is_root` (top-level content type) vs `is_nestable` (block usable inside others) maps to v0's "only top-level recipe entries are blocks; nested HTML inside a slot is rendered HTML, not a block".
- **Reference / link fields as a future extension.** Contentful's `Link` field with `linkContentType: ["page"]` is the precedent for "this CTA block references a deck PR entry". Architecture preserves the option (block content stays a typed dict), but v0 does NOT implement it.

## Not adopted in v0

| Pattern | Why not |
|---|---|
| Editor UI (Storyblok Visual Editor, Gutenberg admin, Builder.io drag-and-drop) | Authoring is YAML + the editorial-author skill; no GUI. The Agent Visual QA gate IS the preview equivalent. |
| Runtime DB / CMS (Contentful Spaces, Storyblok content store) | Recipes live in git; assembler is static. |
| GraphQL / REST content delivery (Contentful CDA, Storyblok CDN, Sanity GROQ) | We compile to flat HTML / CSS / JS files. No runtime API. |
| Localisation workflow (Contentful `Localized: bool`, Storyblok translation layer) | Out of scope for v0. Adds via slot-level `localizable: bool` if it becomes a requirement. |
| Asset CDN with image transformations (Storyblok image service, Contentful Images API) | Asset model handles assets as static file references; transformations are out of scope. |
| Arbitrary block host protocol (Block Protocol's host-application contract) | We don't have a host application — the renderer IS the host. Pattern noted, not implemented. |
| Content versioning (Contentful entries with version history, Storyblok stories) | Git provides versioning; recipes are git-tracked. |

## Design consequences

These are the v0 implementation choices that fall out of "adopt selected patterns, do not copy any system":

- **Skin mapping stays YAML.** No DSL, no Python configuration. A maintainer reads / edits a `landing.yaml` file by hand.
- **Parser validates schema shallowly in v0.** Required-vs-optional + asset existence + role-in-block-library. Richer validators (regex, MIME type, content-type link, range) are a v1 evolution path; the skin schema is forward-compatible with `validations:` extension.
- **Recipes remain portable content, not CSS/HTML templates.** A recipe knows nothing about Tailwind, BEM, styled-components, deck slides, etc. Skin maps it to whatever the profile's primitive layer renders.
- **Visual QA remains mandatory** because external CMS patterns do not solve fidelity. Storyblok / Contentful / Gutenberg all defer rendering to the host frontend; they cannot guarantee that the rendered page LOOKS right. Agent Visual QA + screenshots is the h2t-creative answer to that gap.
- **The semantic renderer does not introduce a new authoring tool.** It introduces a new RECIPE FORMAT (`blocks:`) that the existing assembler can route. Authoring is still done via the existing landing / deck skills (or by hand). Future authoring-side improvements (a skill that walks a user through producing a `blocks:` recipe interactively) are downstream of v0, not part of it.

## Cross-references

- Architecture spec §15 prior-art appendix — `docs/superpowers/specs/2026-05-08-h2t-creative-semantic-rendering-architecture.md`. Same content as this file; THIS file is the discoverable entry point, the spec section is the embedded copy.
- Plan §13 References — `docs/superpowers/plans/2026-05-08-h2t-creative-semantic-renderer-v0.md`. Cites this file as a primary input.
- Legacy-fidelity skill — `plugins/h2t-creative/skills/legacy-fidelity/SKILL.md`. Slated for an additive note: "when planning a landing semantic renderer (v0 or later), read this prior-art reference before T1".

## Maintenance

- Update this file when a new external system becomes relevant (e.g. when Block Protocol's library lands in Context7, OR when a new headless CMS introduces a pattern worth lifting).
- Re-verify Context7 IDs and snippet counts annually OR when an agent reports stale results.
- Keep this file under 200 lines. If it grows, split into per-system reference files.
- Synchronise non-trivial changes here with architecture spec §15 — DO NOT let the two diverge silently.
