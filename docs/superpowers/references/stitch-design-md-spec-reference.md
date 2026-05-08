# Stitch DESIGN.md — open-standard reference

## Why this exists

Future agents working on h2t-creative profiles, design-system migration, or any tool that emits or validates a `DESIGN.md` file should read this reference **before** opening or modifying a profile design-system doc.

Google Labs released **DESIGN.md** as an open Apache-2.0 standard in 2026, alongside Stitch. It is the design counterpart to `AGENTS.md` — a plain-text design-system file with YAML frontmatter (machine-readable design tokens) and a markdown body (human-readable design rationale). Coding agents read it to generate consistent UI without re-deriving brand decisions every session.

For h2t-creative this matters because each profile already ships a `profiles/<name>/DESIGN.md`, and we want those files to be portable across agent ecosystems (Claude Code, Cursor, Kiro, Windsurf, Stitch) rather than locked to our internal shape.

## YAML frontmatter schema

```yaml
---
version: <string>          # current: "alpha"
name: <string>
description: <string>      # optional
colors:
  <token-name>: <Color>    # hex SRGB, e.g. "#1A1C1E"
typography:
  <token-name>:
    fontFamily: <string>
    fontSize: <Dimension>  # px | em | rem
    fontWeight: <number>
    lineHeight: <Dimension | unitless number>
    letterSpacing: <Dimension>
    fontFeature: <string>     # CSS font-feature-settings
    fontVariation: <string>   # CSS font-variation-settings
rounded:
  <scale>: <Dimension>      # sm/md/lg/xl/full
spacing:
  <scale>: <Dimension | number>
components:
  <component-name>:
    <property>: <value | {token.reference}>
---
```

## Markdown body — section order

Each section uses an `## ` H2 heading. Order is normative; duplicate headings reject the file.

1. **Overview** (also accepted as "Brand & Style")
2. **Colors**
3. **Typography**
4. **Layout** (also accepted as "Layout & Spacing")
5. **Elevation & Depth**
6. **Shapes**
7. **Components**
8. **Do's and Don'ts**

## Token reference syntax

Tokens are referenced inline by curly-brace path, inspired by the W3C Design Token JSON spec:

```
{colors.primary-60}
{typography.label-md}
{rounded.lg}
{spacing.md}
{components.button.background}
```

A reference resolves to the value at that path inside the YAML frontmatter. References may appear inside `components` properties.

## Recommended (non-normative) token names

These names are conventions, not requirements — consumers preserve unknown names without error.

- **Colors:** `primary`, `secondary`, `tertiary`, `neutral`, `surface`, `on-surface`, `error`
- **Typography:** `headline-display`, `headline-lg`, `headline-md`, `body-lg`, `body-md`, `body-sm`, `label-lg`, `label-md`, `label-sm`
- **Rounded:** `none`, `sm`, `md`, `lg`, `xl`, `full`

## Consumer behaviour

| Situation | Required behaviour |
|---|---|
| Unknown markdown section | Preserve without error (forward-compat) |
| Unknown token name | Preserve without error |
| Unknown YAML key | Preserve without error |
| Duplicate section heading | Reject the file |
| Missing required frontmatter (`version`, `name`) | Reject the file |
| Token reference points at non-existent path | Implementation-defined; recommend warn |

The forward-compatibility rule is the reason additive sections (h2t-creative's `Brand Intent`, `Available Palettes`, `Restrictions`) can coexist with the spec body sections without the file becoming invalid.

## Compatible consumers

Any agent or tool that reads project files can consume DESIGN.md. Documented consumers include:

- **Claude Code** (this environment)
- **Cursor**
- **Kiro**
- **Windsurf**
- **Google Stitch** (the reference implementation)
- Plus any custom agent that loads project markdown for context

## Conversion targets

DESIGN.md is the source of truth. It can be deterministically converted to:

- **`tokens.json`** (W3C Design Tokens spec) — for design-tool import / cross-team handoff
- **Figma variables** — via Figma's variables API or a token import plugin
- **Tailwind theme config** — `tailwind.config.js` `theme.extend.{colors,fontFamily,borderRadius,spacing}`
- **CSS custom properties** — the route h2t-creative uses today (`tokens.css` + `palettes/*.css`)

## How h2t-creative consumes this standard

- Per-profile `profiles/<name>/DESIGN.md` files conform to the Stitch spec (YAML frontmatter + the eight-section body).
- The existing CSS multi-file model (`tokens.css` + `palettes/*.css`) sits **below** Stitch — it is the runtime/implementation layer that consumes the tokens declared in the frontmatter.
- `WIREFRAME_GATE.md`, `VISUAL_QA.md`, and `COMPOSITION_RULES.md` sit **above** Stitch — they are process-layer docs that govern how a recipe uses the design system, not what the design system contains.
- The `/style-create` wizard emits Stitch-conformant frontmatter when scaffolding a new profile.
- `/style-validate` checks frontmatter shape (required keys, recognised section order, no duplicate headings).
- The Stitch standard is **additive**: pre-existing markdown sections (Brand Intent, Available Palettes, Restrictions) coexist with the spec body sections under the forward-compatibility rule, so adopting Stitch does not break authoring habits or remove h2t-creative-specific guidance.

## Sources

- Repo: https://github.com/google-labs-code/design.md
- Spec: https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
- Stitch docs: https://stitch.withgoogle.com/docs/design-md/overview
- Blog announcement: https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/
- Curated examples: https://github.com/VoltAgent/awesome-design-md

## Maintenance

- Re-verify URLs and the `version:` value annually OR when an agent reports a Stitch spec change.
- When the spec leaves `alpha`, update both this file and `/style-validate` to reflect the new version string.
- Keep this file under 200 lines. If conversion-target details grow, split into per-target reference files.
