# h2t-creative External Research: Agentic Visual Publishing

## Status

Research note for ADR 2026-05-19.

## Research Question

Which current tools or standards partially solve the architecture h2t-creative tried to build, and what should h2t adopt or avoid?

## Local Architecture Being Compared

h2t-creative mixed five product layers:

1. Agent workflow layer: skills, hooks, QA, gates.
2. Design-system memory: `DESIGN.md`, tokens, palettes, typography.
3. Component library: HTML/CSS primitives and manifests.
4. Content/composition model: recipes, wireframes, page/deck flow.
5. Renderer/CMS abstraction: semantic blocks, skins, adapters.

The reset keeps layers 1-4 and freezes layer 5.

## Findings

| Area | Existing solution | What it solves | h2t decision |
|---|---|---|---|
| Agent packaging | Claude Code plugins | Packages skills, slash commands, agents, hooks, MCP servers, and workflows. | Treat h2t-creative as a workflow plugin, not a CMS. |
| Agent guardrails | Claude Code hooks / subagents / skills | Enforces workflow boundaries and specialized task execution. | Use hooks for gate enforcement and skills for landing/deck/QA flows. |
| Design-system memory | Stitch DESIGN.md | Machine-readable design tokens plus markdown rationale. | Keep as canonical profile format. Do not invent a competing profile schema. |
| Design-code bridge | Figma MCP / Dev Mode / Code Connect | Gives agents access to design context and maps design components to code components. | Useful later if Figma becomes the design source of truth; too heavy for current solo workflow. |
| Open design canvas | Penpot MCP and Penpot design systems | Open-source visual canvas with components, assets, tokens, and agent access. | Candidate future canvas for wireframes and human approval. |
| Lightweight IDE design | Pencil.dev | Design canvas and `.pen` files close to code workflow. | Candidate for low-friction wireframe artifacts if markdown wireframes are not enough. |
| Visual prototyping | Figma Make and prompt-to-code tools | Fast generated prototypes. | Useful as disposable visual reference; not a production source of truth. |
| Headless content model | Storyblok / Contentful / Sanity Portable Text | Structured content, reusable blocks, validation, preview. | Prior art only. Do not rebuild a headless CMS inside h2t-skills. |
| Portable block schemas | Block Protocol | Formal block interoperability model. | Too heavy for now; revisit only after several approved outputs require cross-host portability. |
| Figma-to-code automation | Builder.io Visual Copilot / Locofy-style tools | Converts design files into code scaffolds. | Useful for reference and extraction experiments; not a replacement for human visual approval. |

## What To Adopt

### 1. Plugin as workflow container

Claude Code plugins match h2t-creative's natural shape. The plugin should package:

- `landing` and `deck` skills;
- `style-create` / `style-validate`;
- visual QA skill;
- optional hooks that block recipe/CSS work without an approved wireframe;
- optional MCP integrations later for Figma/Penpot.

### 2. DESIGN.md as profile source of truth

The profile should remain:

```text
DESIGN.md -> tokens.css / palettes.css / component constraints
```

`DESIGN.md` stores design memory. CSS is the runtime implementation. Profiles should not get a second competing schema.

### 3. Wireframe artifact as composition source

The current markdown wireframe contract is acceptable for now. If visual review needs a canvas, the likely next candidates are:

- Penpot MCP, when a real design canvas is useful;
- Pencil.dev / `.pen` files, when a lightweight code-adjacent artifact is enough;
- Figma MCP, only if Figma becomes the canonical workspace.

### 4. Screenshot evidence as hard gate

Mature systems have previews. h2t's equivalent is:

```text
build -> desktop/mobile screenshots -> agent visual QA -> human review
```

No file-generation pass can replace this.

## What Not To Adopt

- Runtime database, content store, localization, or GraphQL delivery from Storyblok/Contentful/Sanity.
- A universal block registry before h2t has several approved outputs.
- Figma/Code Connect ceremony before there is a stable design-system team workflow.
- Figma-to-code output as production truth without h2t visual QA.
- Arbitrary JS injection from recipes.

## Recommended h2t Shape

```text
Claude Code plugin
  skills/
    landing
    deck
    style-create
    style-validate
    visual-qa
  hooks/
    block-implementation-without-wireframe
  profiles/
    <profile>/DESIGN.md
    <profile>/tokens.css
    <profile>/components/*
  recipes/
    concrete sections/slides recipes
  evidence/
    screenshots + QA notes + negative evidence
```

This keeps h2t-creative small enough to use and strict enough to avoid the #119 failure mode.

## Sources

- Claude Code plugins: https://code.claude.com/docs/en/plugins
- Claude Code plugin reference: https://code.claude.com/docs/en/plugins-reference
- Stitch DESIGN.md: https://github.com/google-labs-code/design.md
- Figma MCP server: https://developers.figma.com/docs/figma-mcp-server/
- Figma Code Connect: https://developers.figma.com/docs/code-connect/
- Figma Make: https://developers.figma.com/docs/code/intro-to-figma-make/
- Penpot MCP: https://help.penpot.app/mcp/
- Pencil.dev docs: https://docs.pencil.dev/
- Storyblok content modeling: https://www.storyblok.com/docs/concepts/content-modeling
- Storyblok blocks: https://www.storyblok.com/docs/concepts/blocks
- Sanity block content / Portable Text: https://www.sanity.io/docs/studio/block-content
- Block Protocol spec: https://blockprotocol.org/spec/0.4/core
- Builder.io Visual Copilot: https://www.builder.io/c/docs/visual-copilot
- Locofy: https://www.locofy.ai/
