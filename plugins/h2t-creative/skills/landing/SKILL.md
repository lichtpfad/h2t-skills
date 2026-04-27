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
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
ASSEMBLER="$PLUGIN_ROOT/assembler.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Step 1: Choose profile

List available profiles:
```bash
ls "$PLUGIN_ROOT/profiles/"
```

Read `$PLUGIN_ROOT/profiles/<name>/DESIGN.md` as context before proceeding.

If no profile exists: offer to run `h2t-creative:style-create` first.

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
$H2T_PYTHON "$ASSEMBLER" --profile <name> --type landing --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 4: Playwright QA

**Dependency check:** Verify `h2t-tools:playwright-agent` is available. If not:
> "ERROR: h2t-tools:playwright-agent plugin is required for delivery but is not installed.
> Install it from the Claude plugin store (search 'Playwright' by Microsoft), then retry.
> Delivery halted — dist/ is not ready until QA passes."
> **Stop here. Do not deliver dist/.**

If available, use the `Agent` tool with `subagent_type: "h2t-tools:playwright-agent"`:

1. Open `dist/index.html` at 375px viewport → screenshot
2. Open `dist/index.html` at 1440px viewport → screenshot
3. Check for: text clipping, horizontal overflow, element collisions

## Step 5: Review and iterate

Examine screenshots. If issues found: adjust recipe.yaml and repeat from Step 3.

Deliver `dist/` only when QA passes.
