---
name: deck
description: "Generates a multi-file HTML presentation deck using the h2t-creative assembler pipeline. Keyboard navigation (←/→/Space), fixed slide menu, optional fx/. Performs mandatory Playwright QA per slide at 1440px. Delivery halted if Playwright unavailable. Triggers: 'deck', 'create presentation', 'make slides', 'презентация', 'h2t-creative:deck'"
compatibility: "Assembly needs the h2t-ops CLI (h2t-creative). The QA step runs h2t-creative:browser-qa, whose
  browser comes from npx @playwright/mcp — Node is the prerequisite, and its absence marks
  the result unverified rather than stopping delivery."
metadata:
  author: lichtpfad
  version: 1.3.0
---

# h2t-creative: deck

Generate a presentation deck via the assembler pipeline.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect 4.0.0 --json
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
   it there is no install: give the user `uvx --isolated --python 3.12.11 --managed-python -c "https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt" --from "h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl" h2t-setup sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `uvx --isolated --python 3.12.11 --managed-python -c "https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt" --from "h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl" h2t-setup sync`.
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

```bash
ls "$(h2t-creative profiles-dir)" "$(h2t-creative root)/profiles" 2>/dev/null
```

Read `<profile dir>/DESIGN.md` as context.

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

## Step 1c: Content source

If the deck is built from text the user has already approved, the text is content and
stays word for word; only layout is yours. Read `references/from-approved-text.md` before
Step 2: write the deck markdown with `verbatim_source`, split the text into blocks by its
two passes, propose cuts and emphasis and wait for the user's choice. Then let the CLI
build the recipe from that markdown instead of writing it by hand:

```bash
h2t-creative recipe --deck deck.md --out recipe.yaml [--profile <name>] [--assets <dir>]
```

`--assets` is where `![…](file.svg)` is inlined from, beside the deck's own directory.
Step 2 below is then the reference for what the recipe holds; Step 3b checks the result.

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

Available layouts: `cover`, `title-only`, `title-body`, `title-media`, `blank`.

Recipe options: `lang` (the page's `<html lang>`, default `en`), `menu: numbers` (slide
numbers in the menu with the title on hover — for long decks), `stylesheets` (URLs added to
`<head>`, e.g. the profile's web fonts).

### Blocks: the role of each piece of text

Instead of one HTML `body`, a `title-body` or `cover` slide can carry `blocks` — a list in
reading order, each with a `role`. The assembler writes the markup; `base/deck.css` styles
every role in every profile through `--role-*` aliases of the profile's tokens, and a
profile may add its own look in `profiles/<name>/deck.css`. Values are inline HTML.

```yaml
  - title: "Market"
    layout: title-body
    content:
      headline: "Market"
      kicker: ["1. Market and competitors", "Question: what is taken?"]   # above the headline
      blocks:
        - {role: thesis, text: "The one sentence this slide exists to say."}
        - {role: text, text: "A paragraph that explains it."}             # text: a string or a list
        - {role: cards, label: "Neighbours", items: ["Spa — a long ritual.", {title: "Doctor.", text: "When it hurts."}]}
        - {role: steps, items: ["Try.", "Talk to the expert.", "Choose."]}
        - {role: number, figures: ["44%", "72%"], items: ["Caption for 44%.", "Caption for 72%."]}
        - {role: number, figures: ["13 of 35"], text: "One figure, one caption: 13 of 35."}
        - {role: quote, label: "Came without a problem:", quotes: [{text: "«…»", by: "from a client interview"}]}
        - {role: table, header: ["Competitor", "Frame"], rows: [["North", "Premium"]]}
        - {role: figure, svg: "<svg …>"}                                  # or src + alt
        - {role: conclusion, text: "Conclusion: …"}
        - {role: note, text: "A caveat about the data."}
        - {role: html, html: "<div>…</div>"}                              # escape hatch
```

Two `quote` blocks in a row share a line. Which role a fragment gets is a decision about
the text, not the look: for a deck from approved text follow
`references/from-approved-text.md`.

## Step 3: Run assembler

```bash
h2t-creative assemble --profile <name> --type deck --recipe recipe.yaml --out ./dist
```

On error: print assembler's stderr and stop.

## Step 3b: Verify the content (deck from approved text)

```bash
h2t-creative verify --deck deck.md --page ./dist/index.html --json
```

Exit 1: `missing`, `misplaced` and `stale_omit` in the JSON say what is wrong; `omitted`
and `renamed` are the decisions to show the user. Fix the deck markdown and repeat from
Step 2; do not go on to QA with a failing verify.

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
