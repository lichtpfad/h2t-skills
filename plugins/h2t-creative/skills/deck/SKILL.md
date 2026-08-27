---
name: deck
description: "Generates a multi-file HTML presentation deck using the h2t-creative assembler pipeline. Keyboard navigation (←/→/Space), fixed slide menu, optional fx/. Performs mandatory Playwright QA per slide at 1440px. Delivery halted if Playwright unavailable. Triggers: 'deck', 'create presentation', 'make slides', 'презентация', 'h2t-creative:deck'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: deck

Generate a presentation deck via the assembler pipeline.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
ASSEMBLER="$PLUGIN_ROOT/assembler.py"
RUN="uv run --no-project --with pyyaml python"
```

## Step 1: Choose profile

```bash
ls "$PLUGIN_ROOT/profiles/"
```

Read `$PLUGIN_ROOT/profiles/<name>/DESIGN.md` as context.

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

## Step 2: Build recipe.yaml

Deck schema uses `slides:` key (NOT `sections:`):

```yaml
type: deck
profile: <profile-name>
title: "Deck Title"
slides:
  - title: "Slide 1"
    layout: title-only
    content:
      headline: "Opening"
  - title: "Slide 2"
    layout: title-body
    content:
      headline: "Details"
      body: "<p>Body text or HTML.</p>"
      note: "Speaker note — not rendered, saved as HTML comment"
  - title: "Slide 3"
    layout: title-media
    content:
      headline: "Visual"
      media_url: "https://example.com/image.png"
  - title: "Blank"
    layout: blank
    content: {}
```

Available layouts: `title-only`, `title-body`, `title-media`, `blank`.

## Step 3: Run assembler

```bash
$RUN "$ASSEMBLER" --profile <name> --type deck --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 4: Playwright QA

**Dependency check:** Verify `h2t-tools:playwright-agent` is available. If not:
> "ERROR: h2t-tools:playwright-agent plugin is required for delivery but is not installed.
> Install it from the Claude plugin store (search 'Playwright' by Microsoft), then retry.
> Delivery halted — dist/ is not ready until QA passes."
> **Stop here. Do not deliver dist/.**

If available, use the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`:

1. Screenshot slide 1 at 1440px viewport
2. Press `→` key → screenshot slide 2 (keyboard nav smoke test)
3. Click menu link for slide 3 → screenshot (if ≥3 slides)

## Step 5: Review and iterate

Examine screenshots. If issues found: adjust recipe.yaml and repeat from Step 3.

Deliver `dist/` only when QA passes.
