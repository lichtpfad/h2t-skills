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

## Setup

```bash
PLUGIN_ROOT="$(h2t-creative root)"
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

## Step 2: Build recipe.yaml

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

## Step 3: Run assembler

```bash
h2t-creative assemble --profile <name> --type landing --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 4: Playwright QA

Use the `Agent` tool with `subagent_type: "h2t-creative:browser-qa"`. The agent ships with
this plugin and pulls its browser through `npx` on demand, so there is nothing to install
beyond Node.

Give it the absolute path to `dist/index.html`. It reports, per width:

1. **1440, 768 and 375** — screenshot plus `scrollWidth` against `clientWidth`
2. Console errors and warnings
3. Clipped text, collisions, elements wider than their container

The overflow numbers are the part that matters. Horizontal overflow does not show in a
screenshot — the page looks right and slides sideways under a finger.

**If the agent cannot run** (no Node, `npx` blocked, MCP refused to start): do not halt.
Deliver `dist/` and say plainly, in the same message, that it is **unverified** and at which
widths it was not checked. A page nobody looked at is worth more than a page nobody built;
what is not acceptable is delivering one and implying the other.

## Step 5: Review and iterate

Examine screenshots. If issues found: adjust recipe.yaml and repeat from Step 3.

Deliver `dist/` only when QA passes.
