---
name: h2t-creative:style-create
description: "Wizard to scaffold a new h2t-creative design profile directory. Creates DESIGN.md, tokens.css, 5 component templates (nav, hero, section, cta, footer) with manifest.yaml files. Optionally adds fx/ with Three.js boilerplate. Triggers: 'create profile', 'new design style', 'scaffold profile', 'style-create', 'h2t-creative:style-create'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# h2t-creative: style-create

Scaffold a new visual profile for h2t-creative.

## Setup

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
PROFILES_DIR="$PLUGIN_ROOT/profiles"
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

Copy component HTML/CSS from `$PROFILES_DIR/h2t-default/components/` as starting point,
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
