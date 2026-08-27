---
name: landing
description: "Generates a multi-file landing page using the h2t-creative assembler pipeline. Reads DESIGN.md profile as context, collaborates on recipe.yaml content, runs assembler.py, then performs mandatory Playwright QA at 375px and 1440px. Delivery halted if Playwright unavailable. Triggers: 'landing', 'create landing', 'landing page', 'h2t-creative:landing'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: landing

Generate a landing page via the assembler pipeline with mandatory Playwright QA.

Before writing `recipe.yaml`, read:

- `docs/architecture/h2t-creative/ROOT_GUIDE.md`
- `docs/architecture/h2t-creative/COMPOSITION_RULES.md`
- `docs/protocols/h2t-creative/WIREFRAME_GATE.md`
- `docs/protocols/h2t-creative/VISUAL_QA.md`

For any production landing or candidate visual, the Wireframe Gate is mandatory.
Do not jump from content or components directly to recipe implementation.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
ASSEMBLER="$PLUGIN_ROOT/assembler.py"
RUN="uv run --no-project --with pyyaml python"
```

## Step 1: Choose profile

List available profiles:
```bash
ls "$PLUGIN_ROOT/profiles/"
```

Read `$PLUGIN_ROOT/profiles/<name>/DESIGN.md` as context before proceeding.

If no profile exists: offer to run `h2t-creative:style-create` first.

## Step 1b: Choose palette

Check for palettes in selected profile:
```bash
ls "$PLUGIN_ROOT/profiles/<name>/palettes/" 2>/dev/null
```

Three states:
- **No `palettes/` directory** (command fails): Skip. Do NOT add `palette:` to recipe.
- **Only `default.css` exists**: Skip silently. Do NOT add `palette:` to recipe.
- **Two or more `*.css` files**: List names and ask user: "Which palette? (Enter to use default)"
  Write `palette: <name>` to recipe only if user chooses a non-default palette.

## Step 2: Approve wireframe

Create a low-fidelity wireframe/composition proposal before writing the final
recipe. It must define:

- target reader and page intent
- section order
- first screen
- grid/max-width/rhythm expectations
- table/gallery/video placement
- desktop and mobile representation
- CTA placement

Stop until the human approves the wireframe. If this is only a throwaway smoke
test, label it clearly as such and do not claim visual/design pass.

## Step 3: Build recipe.yaml

Collaborate with user on content. Schema:

```yaml
type: landing
profile: <profile-name>
title: "Page Title"
sections:
  - component: nav
    content:
      brand_name: "Brand"
  - component: hero
    content:
      headline: "Main headline"
      subline: "Supporting text"
  - component: section
    content:
      title: "Section Title"
      body: "<p>HTML content allowed here</p>"
  - component: cta
    content:
      text: "Call to action"
      href: "https://example.com"
  - component: footer
    content:
      copy: "© 2026 Brand"
```

Save as `recipe.yaml` in the user's working directory (or a temp dir if unspecified).

## Step 4: Run assembler

```bash
$RUN "$ASSEMBLER" --profile <name> --type landing --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 5: Playwright QA

**Dependency check:** Verify `h2t-tools:playwright-agent` is available. If not:
> "ERROR: h2t-tools:playwright-agent plugin is required for delivery but is not installed.
> Install it from the Claude plugin store (search 'Playwright' by Microsoft), then retry.
> Delivery halted — dist/ is not ready until QA passes."
> **Stop here. Do not deliver dist/.**

If available, use the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`:

1. Open `dist/index.html` at 375px viewport → screenshot
2. Open `dist/index.html` at 1440px viewport → screenshot
3. Check for: text clipping, horizontal overflow, element collisions

## Step 6: Review and iterate

Examine screenshots against the approved wireframe and profile style. If issues
found: classify them as composition, style, responsive, content, or renderer.
Adjust only the layer responsible and repeat from Step 4.

Deliver `dist/` only when QA passes.
