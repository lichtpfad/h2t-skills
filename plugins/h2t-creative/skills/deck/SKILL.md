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
PLUGIN_ROOT="$(h2t-creative root)"
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
h2t-creative assemble --profile <name> --type deck --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 4: Playwright QA

Use the `Agent` tool with `subagent_type: "h2t-creative:browser-qa"`. The agent ships with
this plugin and pulls its browser through `npx` on demand, so there is nothing to install
beyond Node.

1. Screenshot slide 1 at 1440px
2. Press `→` → screenshot slide 2, and confirm the slide actually changed
3. Click the menu link for slide 3 → screenshot (if there are three or more)

**If the agent cannot run** (no Node, `npx` blocked, MCP refused to start): do not halt.
Deliver `dist/` and say plainly that it is **unverified**, and what was not checked.

## Step 5: Review and iterate

Examine screenshots. If issues found: adjust recipe.yaml and repeat from Step 3.

Deliver `dist/` only when QA passes.
