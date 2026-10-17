---
name: style-validate
description: "Validates a h2t-creative profile directory for completeness. Checks DESIGN.md required sections, tokens.css required variables, all 5 components exist with manifest.yaml, fx/ exports contract if present. Triggers: 'validate profile', 'check style', 'style-validate', 'h2t-creative:style-validate'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: style-validate

Validate a profile directory for completeness before use.

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
   `reason: path` it is a command for the user to decide on. `result.reason` names the
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

A profile is looked up first among the user's profiles, then among the shipped ones:

```bash
h2t-creative profiles-dir          # profiles you created: ~/.h2t/creative/profiles
echo "$(h2t-creative root)/profiles" # profiles shipped with the CLI
```

`$PROFILES_DIR` below is the first of the two that holds `<name>/`.

## Usage

Invoked with profile name argument, e.g.: `h2t-creative:style-validate h2t-default`

## Checks

### 1. DESIGN.md required sections

Read `$PROFILES_DIR/<name>/DESIGN.md`. Must contain these sections:
- `## Brand Intent`
- `## Color Tokens`
- `## Available Palettes`
- `## Typography`
- `## Restrictions`

If `## Available Palettes` is absent: print warning (not failure) when `palettes/` dir has ≥ 2 files.
If only `palettes/default.css` exists: skip this warning.

### 2. tokens.css — font vars required, no color vars

Read `$PROFILES_DIR/<name>/tokens.css`. Must define at least one of: `--font-display`, `--font-body`, `--font`.
If any `--color-*` variable is found in `tokens.css`: print warning (not failure):
`⚠ tokens.css defines --color-* variables — move them to palettes/default.css`

### 3. palettes/default.css — colors required

If `palettes/` directory exists:
- `palettes/default.css` MUST exist and define `--color-bg`, `--color-fg`, `--color-accent`
- Check all other `*.css` files in `palettes/` define the same set of `--color-*` vars as `default.css`; warn on mismatch

If `palettes/` directory does NOT exist:
- Check `tokens.css` defines `--color-bg`, `--color-fg`, `--color-accent` (legacy path)
- Print info: `ℹ Legacy profile (no palettes/ dir) — colors expected in tokens.css`

### 4. Components inventory

Each of the following must exist with all three files:
- `components/nav/nav.html`, `nav.css`, `manifest.yaml`
- `components/hero/hero.html`, `hero.css`, `manifest.yaml`
- `components/section/section.html`, `section.css`, `manifest.yaml`
- `components/cta/cta.html`, `cta.css`, `manifest.yaml`
- `components/footer/footer.html`, `footer.css`, `manifest.yaml`

### 5. fx/ contract (only if fx/ directory exists)

Read `fx/background.js`. Must contain:
- `export function init(` — exported init function
- `export function destroy(` — exported destroy function

## Output

Report PASS/FAIL per check. On any failure: print the exact missing item and stop.

Example passing output:
```
✓ DESIGN.md — all required sections present (incl. ## Available Palettes)
✓ tokens.css — font vars present, no color vars
✓ palettes/default.css — --color-bg, --color-fg, --color-accent defined
✓ components/nav — complete
✓ components/hero — complete
✓ components/section — complete
✓ components/cta — complete
✓ components/footer — complete
Profile 'h2t-graphs' is valid.
```

Example failing output:
```
✓ DESIGN.md — all required sections present (incl. ## Available Palettes)
✓ tokens.css — font vars present, no color vars
✓ palettes/default.css — --color-bg, --color-fg, --color-accent defined
✗ components/section — missing section.css
FAIL: profile 'my-profile' is incomplete. Fix the above before use.
```
