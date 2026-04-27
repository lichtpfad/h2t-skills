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

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
PROFILES_DIR="$PLUGIN_ROOT/profiles"
```

## Usage

Invoked with profile name argument, e.g.: `h2t-creative:style-validate h2t-default`

## Checks

### 1. DESIGN.md required sections

Read `$PROFILES_DIR/<name>/DESIGN.md`. Must contain all headings:
- `## Brand Intent`
- `## Color Tokens`
- `## Typography`
- `## Restrictions`

### 2. tokens.css required variables

Read `$PROFILES_DIR/<name>/tokens.css`. Must define:
`--color-bg`, `--color-fg`, `--color-accent`, `--font-display`, `--font-body`

### 3. Components inventory

Each of the following must exist with all three files:
- `components/nav/nav.html`, `nav.css`, `manifest.yaml`
- `components/hero/hero.html`, `hero.css`, `manifest.yaml`
- `components/section/section.html`, `section.css`, `manifest.yaml`
- `components/cta/cta.html`, `cta.css`, `manifest.yaml`
- `components/footer/footer.html`, `footer.css`, `manifest.yaml`

### 4. fx/ contract (only if fx/ directory exists)

Read `fx/background.js`. Must contain:
- `export function init(` — exported init function
- `export function destroy(` — exported destroy function

## Output

Report PASS/FAIL per check. On any failure: print the exact missing item and stop.

Example passing output:
```
✓ DESIGN.md — all required sections present
✓ tokens.css — all required variables defined
✓ components/nav — complete
✓ components/hero — complete
✓ components/section — complete
✓ components/cta — complete
✓ components/footer — complete
Profile 'h2t-default' is valid.
```

Example failing output:
```
✓ DESIGN.md — all required sections present
✓ tokens.css — all required variables defined
✗ components/section — missing section.css
FAIL: profile 'my-profile' is incomplete. Fix the above before use.
```
