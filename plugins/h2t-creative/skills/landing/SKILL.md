---
name: landing
description: "Generates a multi-file landing page using the h2t-creative assembler pipeline. Reads DESIGN.md profile as context, collaborates on recipe.yaml content, runs h2t-creative assemble, then performs mandatory Playwright QA at 375px and 1440px. Delivery halted if Playwright unavailable. Triggers: 'landing', 'create landing', 'landing page', 'h2t-creative:landing'"
compatibility: "Assembly needs the h2t-ops CLI (h2t-creative). The QA step runs h2t-creative:browser-qa, whose
  browser comes from npx @playwright/mcp — Node is the prerequisite, and its absence marks
  the result unverified rather than stopping delivery."
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: landing

Generate a landing page via the assembler pipeline with mandatory Playwright QA.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Setup

Profiles live in two places, and a profile is looked up in that order:

```bash
h2t-creative profiles-dir          # profiles you created (= h2t-ops paths get data:creative/profiles)
echo "$(h2t-creative root)/profiles" # profiles shipped with the CLI
```

Below, `<profile dir>` is `<first>/<name>` when the profile is in the first directory, else
`<second>/<name>`. A profile of yours shadows a shipped one of the same name, and
`h2t-creative assemble` resolves it the same way.

## Step 1: Choose profile

List available profiles:
```bash
ls "$(h2t-creative profiles-dir)" "$(h2t-creative root)/profiles" 2>/dev/null
```

Read `<profile dir>/DESIGN.md` as context before proceeding.

If no profile exists: offer to run `h2t-creative:style-create` first.

## Step 1b: Choose palette

Check for palettes in selected profile:
```bash
ls "<profile dir>/palettes/" 2>/dev/null
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
