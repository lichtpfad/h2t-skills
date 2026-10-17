---
name: style-create
description: "Wizard to scaffold a new h2t-creative design profile directory. Creates DESIGN.md, tokens.css, 5 component templates (nav, hero, section, cta, footer) with manifest.yaml files. Optionally adds fx/ with Three.js boilerplate. Triggers: 'create profile', 'new design style', 'scaffold profile', 'style-create', 'h2t-creative:style-create'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: style-create

Scaffold a new visual profile for h2t-creative.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` and follow it before going on.
   `result.reason` names the case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Setup

New profiles go to the user's profile directory, outside every install, so an update of
the CLI or the plugins never touches them:

```bash
h2t-creative profiles-dir          # $PROFILES_DIR: ~/.h2t/creative/profiles
echo "$(h2t-creative root)/profiles" # $SHIPPED_PROFILES: the profiles shipped with the CLI
```

Create `$PROFILES_DIR` if it does not exist. Never write under `h2t-creative root`: that
directory belongs to the installed CLI and is replaced on every update.

**A profile made before this change** was written into the plugin cache
(`~/.claude/plugins/cache/lichtpfad/h2t-creative/<version>/profiles/<name>/`). It is still
there, and nothing moves it. To keep using it, copy that directory once into the one
`h2t-creative profiles-dir` prints — the user does it, or approves it, since it names a
path in their plugin cache:

```text
~/.claude/plugins/cache/lichtpfad/h2t-creative/<version>/profiles/<name>/  →  ~/.h2t/creative/profiles/<name>/
```

## Wizard Steps

Ask one question at a time, wait for each answer:

1. "Profile name?" (slug, e.g. `h2t-dark`, `workshop-2026`)
2. "Brand intent in 1-2 sentences? (aesthetic, mood, use case)"
3. "Primary color palette? (bg, fg, accent hex values — or describe and I'll generate)"
4. "Add Three.js/WebGL fx/ background? (y/n)"

## Scaffold

Create `$PROFILES_DIR/<name>/` with this structure:

```
DESIGN.md
tokens.css         ← fonts, spacing, radii, z-index (NO colors)
palettes/
  default.css      ← all --color-* variables
components/
  nav/nav.html + nav.css + manifest.yaml
  hero/hero.html + hero.css + manifest.yaml
  section/section.html + section.css + manifest.yaml
  cta/cta.html + cta.css + manifest.yaml
  footer/footer.html + footer.css + manifest.yaml
fx/                ← only if user said yes
  background.js
```

### DESIGN.md template

```markdown
# <Profile Name>

## Brand Intent
<one paragraph describing visual character>

## Color Tokens

### default
- `--color-bg`: ...
- `--color-fg`: ...
- `--color-accent`: ...

## Available Palettes
- `default` — <description>

## Typography
- `--font-display`: ...
- `--font-body`: ...

## Restrictions
- ...
```

### tokens.css — fonts, spacing, radii, z-index ONLY

Generate from wizard answers. Must define: `--space-xs/sm/md/lg/xl`, `--radius-sm/md/lg`,
`--font-display` and/or `--font-body` (or `--font` for mono-stack profiles), `--z-bg/base/nav`.
Do NOT include any `--color-*` variable.

### palettes/default.css — all color variables

Generate from wizard color palette answers. Must define:
`--color-bg`, `--color-fg`, `--color-accent`, `--color-accent-hover`,
`--color-muted`, `--color-surface`, `--color-border`

### Component stubs

Copy component HTML/CSS from `$SHIPPED_PROFILES/h2t-default/components/` as starting point,
then update color references to match the new tokens.css palette.

### fx/ boilerplate (if requested)

```javascript
// fx/background.js
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js';

let renderer, scene, camera, animId;

export function init(canvas) {
  renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
  camera.position.z = 2;
  // TODO: add geometry here
  animate();
}

function animate() {
  animId = requestAnimationFrame(animate);
  renderer.render(scene, camera);
}

export function destroy() {
  cancelAnimationFrame(animId);
  renderer.dispose();
}
```

## After Scaffold

Ask: "Want to add alternative color palettes now? (y/n)"
If yes: ask "Palette name and colors (bg, fg, accent hex values)?"
Write as `palettes/<name>.css` defining the same set of `--color-*` vars as `default.css`.
Repeat until user says no.

Then run `h2t-creative:style-validate <name>` to confirm the profile is complete.
