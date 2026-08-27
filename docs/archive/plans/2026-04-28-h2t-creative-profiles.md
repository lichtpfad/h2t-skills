---
title: "h2t-creative Phase 1 — Profiles Implementation Plan"
status: "draft"
date: "2026-04-28"
milestone: ""
---
# h2t-creative Phase 1 — Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement palette-aware profile system, migrate h2t-default, extract 5 new design profiles, update style-create/style-validate and skill wizards.

**Architecture:** `tokens.css` holds fonts/spacing/radii/z-index only. `palettes/*.css` hold all `--color-*` vars. `_build_profile_css` merges tokens + active palette + component CSS. Legacy profiles (no `palettes/` dir) fall back to reading colors from `tokens.css`. Palette precedence: `--palette CLI flag > recipe.palette > "default"`.

**Tech Stack:** Python 3.11 (`assembler.py`), CSS custom properties, YAML (recipe + manifest), pytest

**Shell contract:** All commands run in **bash** (git bash on Windows). Python and pytest use `$H2T_PYTHON`:

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
PLUGIN_ROOT="C:/dev/h2t-skills/plugins/h2t-creative"
```

Run tests as: `$H2T_PYTHON -m pytest tests/h2t_creative/test_assembler.py -v`
Run assembler as: `$H2T_PYTHON "$PLUGIN_ROOT/assembler.py" ...`

---

### Task 1: Palette-aware assembler

**Files:**
- Modify: `plugins/h2t-creative/assembler.py`
- Modify: `tests/h2t_creative/test_assembler.py`

- [ ] **Step 1: Add palette fixture and tests to `test_assembler.py`**

Append to end of `tests/h2t_creative/test_assembler.py`:

```python
# --- palette support ---

def _make_palette_profile(tmp_path: Path):
    """Profile with palettes/ directory — new schema."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    for f in ["reset.css", "grid.css", "typography.css", "animations.css"]:
        (base_dir / f).write_text(f"/* {f} */")

    profile_dir = tmp_path / "profiles" / "test-palette"
    (profile_dir / "components" / "hero").mkdir(parents=True)
    (profile_dir / "palettes").mkdir()
    (profile_dir / "tokens.css").write_text(":root { --font-body: sans-serif; }")
    (profile_dir / "palettes" / "default.css").write_text(
        ":root { --color-bg: #fff; --color-fg: #000; --color-accent: #00f; }"
    )
    (profile_dir / "palettes" / "blue.css").write_text(
        ":root { --color-bg: #001; --color-fg: #aaf; --color-accent: #44f; }"
    )
    (profile_dir / "components" / "hero" / "manifest.yaml").write_text(
        "component: hero\nfields:\n  headline:\n    type: text\n    required: true\n"
        "  subline:\n    type: text\n    required: false\n    default: ''\n"
    )
    (profile_dir / "components" / "hero" / "hero.html").write_text(
        '<section class="hero"><h1>{{ headline }}</h1></section>'
    )
    (profile_dir / "components" / "hero" / "hero.css").write_text(
        ".hero { color: var(--color-fg); }"
    )
    return profile_dir, base_dir


def test_palette_default_loads_palette_file(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    css = assembler._build_profile_css(profile_dir, [], palette="default")
    assert "--font-body" in css
    assert "--color-bg: #fff" in css
    assert "--color-bg: #001" not in css


def test_palette_blue_loads_blue_file(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    css = assembler._build_profile_css(profile_dir, [], palette="blue")
    assert "--color-bg: #001" in css
    assert "--color-bg: #fff" not in css


def test_palette_unknown_raises_with_available_list(tmp_path):
    profile_dir, _ = _make_palette_profile(tmp_path)
    with pytest.raises(ValueError, match="Palette 'purple' not found"):
        assembler._build_profile_css(profile_dir, [], palette="purple")


def test_legacy_profile_no_palettes_dir_falls_back(tmp_path):
    profile_dir, _ = _make_minimal_profile(tmp_path)
    # _make_minimal_profile has no palettes/ dir — legacy fallback
    css = assembler._build_profile_css(profile_dir, [])
    assert "--color-bg" in css


def test_assemble_landing_with_blue_palette(tmp_path):
    profile_dir, base_dir = _make_palette_profile(tmp_path)
    recipe = {
        "type": "landing", "title": "T", "palette": "blue",
        "sections": [{"component": "hero", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "dist"
    assembler.assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir, palette="blue")
    assert "--color-bg: #001" in (out_dir / "profile.css").read_text()


def test_assemble_deck_uses_build_profile_css_not_raw_tokens(tmp_path):
    """Deck must use _build_profile_css — not read tokens.css directly."""
    profile_dir, base_dir = _make_palette_profile(tmp_path)
    recipe = {
        "type": "deck", "title": "D",
        "slides": [{"title": "S", "layout": "title-only", "content": {"headline": "Hi"}}],
    }
    out_dir = tmp_path / "deck_dist"
    assembler.assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir, palette="blue")
    css = (out_dir / "profile.css").read_text()
    assert "--color-bg: #001" in css
    assert "--font-body" in css
```

- [ ] **Step 2: Run tests — verify they fail**

```
$H2T_PYTHON -m pytest tests/h2t_creative/test_assembler.py -v -k "palette"
```
Expected: FAIL — `TypeError: _build_profile_css() got an unexpected keyword argument 'palette'`

- [ ] **Step 3: Replace `_build_profile_css` in `assembler.py` (lines 120–130)**

```python
def _build_profile_css(profile_dir: Path, sections: list, palette: str = "default") -> str:
    palettes_dir = profile_dir / "palettes"
    if palettes_dir.exists():
        palette_path = palettes_dir / f"{palette}.css"
        if not palette_path.exists():
            raise ValueError(
                f"Palette '{palette}' not found in profile '{profile_dir.name}'. "
                f"Available: {[p.stem for p in palettes_dir.glob('*.css')]}"
            )
        color_css = palette_path.read_text(encoding="utf-8")
    else:
        color_css = ""

    parts = [(profile_dir / "tokens.css").read_text(encoding="utf-8")]
    if color_css:
        parts.append(color_css)

    seen: set = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
            seen.add(name)
    return "\n".join(parts)
```

- [ ] **Step 4: Update `assemble_landing` signature and call**

Add `palette: str = "default"` parameter. Change the `_build_profile_css` call at line 163:
```python
def assemble_landing(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    ...
    (out_dir / "profile.css").write_text(
        _build_profile_css(profile_dir, sections, palette=palette), encoding="utf-8"
    )
```

- [ ] **Step 5: Fix `assemble_deck` — replace direct tokens.css read (lines 276–279)**

```python
def assemble_deck(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    ...
    (out_dir / "profile.css").write_text(
        _build_profile_css(profile_dir, [], palette=palette), encoding="utf-8"
    )
```

- [ ] **Step 6: Update `main_assemble` and `main()`**

```python
def main_assemble(
    output_type: str,
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    if output_type == "landing" and "slides" in recipe:
        print("ERROR: type=landing recipe must not contain 'slides:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "deck" and "sections" in recipe:
        print("ERROR: type=deck recipe must not contain 'sections:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "landing":
        assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette)
    else:
        assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette)
```

In `main()`, add after `parser.add_argument("--dry-run", ...)`:
```python
    parser.add_argument("--palette", default=None, help="Palette override (flag > recipe.palette > 'default')")
```

And replace the `main_assemble` call:
```python
    palette = args.palette if args.palette else recipe.get("palette", "default")
    if args.dry_run:
        dry_run(recipe, args.type, profile_dir, out_dir)
        return
    main_assemble(args.type, recipe, profile_dir, out_dir, palette=palette)
```

- [ ] **Step 7: Run all tests — verify all pass**

```
$H2T_PYTHON -m pytest tests/h2t_creative/test_assembler.py -v
```
Expected: all PASS (27+ tests).

- [ ] **Step 8: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/assembler.py tests/h2t_creative/test_assembler.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): palette-aware assembler — _build_profile_css, deck fix, --palette flag"
```

---

### Task 2: style-validate SKILL.md update

**Files:**
- Modify: `plugins/h2t-creative/skills/style-validate/SKILL.md`

- [ ] **Step 1: Replace check 2 in SKILL.md**

Find and replace the current "### 2. tokens.css required variables" section with:

```markdown
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
```

- [ ] **Step 2: Add DESIGN.md `## Available Palettes` check**

In the existing "### 1. DESIGN.md required sections" check (currently validates `## Brand Intent`, `## Typography`, `## Restrictions`), add `## Available Palettes` to the required-sections list:

```markdown
### 1. DESIGN.md required sections

Read `$PROFILES_DIR/<name>/DESIGN.md`. Must contain these sections:
- `## Brand Intent`
- `## Color Tokens`
- `## Available Palettes`
- `## Typography`
- `## Restrictions`

If `## Available Palettes` is absent: print warning (not failure) when `palettes/` dir has ≥ 2 files.
If only `palettes/default.css` exists: skip this warning.
```

- [ ] **Step 3: Renumber subsequent sections**

"### 2. tokens.css required variables" → becomes the block from Step 1 (already renumbered above as 2 + 3)
"### 3. Components inventory" → "### 4. Components inventory"
"### 4. fx/ contract" → "### 5. fx/ contract"

Update passing output example:
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

- [ ] **Step 3: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/skills/style-validate/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): style-validate — palettes/default.css checks, warn on colors in tokens"
```

---

### Task 3: style-create SKILL.md update

**Files:**
- Modify: `plugins/h2t-creative/skills/style-create/SKILL.md`

- [ ] **Step 1: Update scaffold structure diagram**

Replace current scaffold block with:
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

- [ ] **Step 2: Update tokens.css template description and DESIGN.md template**

Replace current description (which puts colors in tokens.css) with:

```
### tokens.css — fonts, spacing, radii, z-index ONLY

Generate from wizard answers. Must define: `--space-xs/sm/md/lg/xl`, `--radius-sm/md/lg`,
`--font-display` and/or `--font-body` (or `--font` for mono-stack profiles), `--z-bg/base/nav`.
Do NOT include any `--color-*` variable.

### palettes/default.css — all color variables

Generate from wizard color palette answers. Must define:
`--color-bg`, `--color-fg`, `--color-accent`, `--color-accent-hover`,
`--color-muted`, `--color-surface`, `--color-border`
```

Add `## Available Palettes` section to the generated `DESIGN.md` template. Full DESIGN.md template to generate:

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

- [ ] **Step 3: Replace "## After Scaffold" section**

```markdown
## After Scaffold

Ask: "Want to add alternative color palettes now? (y/n)"
If yes: ask "Palette name and colors (bg, fg, accent hex values)?"
Write as `palettes/<name>.css` defining the same set of `--color-*` vars as `default.css`.
Repeat until user says no.

Then run `h2t-creative:style-validate <name>` to confirm the profile is complete.
```

- [ ] **Step 4: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/skills/style-create/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): style-create — colors to palettes/default.css, palette offer step"
```

---

### Task 4: h2t-default migration

**Files:**
- Modify: `plugins/h2t-creative/profiles/h2t-default/tokens.css`
- Create: `plugins/h2t-creative/profiles/h2t-default/palettes/default.css`

- [ ] **Step 1: Create `palettes/default.css`**

```css
:root {
  --color-bg: #ffffff;
  --color-fg: #0a0a0a;
  --color-accent: #1a1aff;
  --color-accent-hover: #0000cc;
  --color-muted: #6b7280;
  --color-surface: #f5f5f5;
  --color-border: #e5e7eb;
}
```

- [ ] **Step 2: Strip colors from `tokens.css`**

New content of `plugins/h2t-creative/profiles/h2t-default/tokens.css`:

```css
:root {
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;

  --font-display: system-ui, sans-serif;
  --font-body: system-ui, sans-serif;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  background-color: var(--color-bg);
  color: var(--color-fg);
  font-family: var(--font-body);
}
```

- [ ] **Step 3: Run full test suite — verify all pass**

```
$H2T_PYTHON -m pytest tests/h2t_creative/test_assembler.py -v
```
Expected: all PASS (existing tests cover the legacy fallback path via `_make_minimal_profile`).

- [ ] **Step 4: Smoke test assembler with h2t-default**

Write this recipe to `C:/tmp/default_test.yaml`:
```yaml
type: landing
profile: h2t-default
title: "Default Test"
sections:
  - component: hero
    content:
      headline: "Hello"
```

```
$H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
  --profile h2t-default --type landing \
  --recipe C:/tmp/default_test.yaml --out C:/tmp/default_dist
```
Expected: `Built landing -> C:/tmp/default_dist`

Verify `C:/tmp/default_dist/profile.css` contains both `--font-display` (from tokens) and `--color-bg: #ffffff` (from palette).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-default/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): h2t-default — migrate colors to palettes/default.css"
```

---

### Task 5: Skill wizard palette step

**Files:**
- Modify: `plugins/h2t-creative/skills/landing/SKILL.md`
- Modify: `plugins/h2t-creative/skills/deck/SKILL.md`

- [ ] **Step 1: Insert palette step into `landing/SKILL.md` after Step 1**

After the "## Step 1: Choose profile" section, add:

```markdown
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
```

- [ ] **Step 2: Update assembler call in landing Step 3**

The assembler call does NOT change — palette always comes from recipe.yaml (which Step 1b already wrote):

```bash
$H2T_PYTHON "$ASSEMBLER" --profile <name> --type landing --recipe recipe.yaml --out ./dist
```

Palette field in recipe.yaml is the single source of truth. Never pass `--palette` from the wizard.

- [ ] **Step 3: Apply identical changes to `deck/SKILL.md`**

Same palette step (Step 1b) and assembler call unchanged (`--type deck`).

- [ ] **Step 4: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/skills/landing/SKILL.md plugins/h2t-creative/skills/deck/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): landing+deck wizard — palette selection step (3 states)"
```

---

### Task 6: h2t-graphs profile

Source: `C:/dev/h2t-landings/graphs/index.html` — read this file first for exact tokens.

**Files:** Create `plugins/h2t-creative/profiles/h2t-graphs/` with full profile structure.

- [ ] **Step 1: Read source file for exact tokens**

Use Read tool: `C:/dev/h2t-landings/graphs/index.html` (limit 150 lines, offset 0).
Confirm the `:root {}` block. Expected exact values from spec are listed below.

- [ ] **Step 2: Create `DESIGN.md`**

```markdown
# h2t-graphs

## Brand Intent
Bold typographic hierarchy with mono labels. Data-rich product landing aesthetic — extracted from lichtpfad graphs landing page. Inter for headlines (700–800 weight), JetBrains Mono for nav/labels/captions.

## Color Tokens

### default (red)
- `--color-bg`: `#060609`
- `--color-bg2`: `#0a0a10`
- `--color-surface`: `#0e0e16`
- `--color-accent`: `#e94560`
- `--color-accent-glow`: `rgba(233,69,96,0.4)`
- `--color-green`: `#00ff88`
- `--color-blue`: `#4a9eff`
- `--color-amber`: `#ffb800`
- `--color-text`: `#a0a0b8`
- `--color-text-hi`: `#d0d0e0`
- `--color-text-dim`: `#3a3a50`
- `--color-border`: `rgba(233,69,96,0.12)`

### blue
Swap accent: `--color-accent: #4a9eff`, `--color-accent-glow: rgba(74,158,255,0.4)`, `--color-border: rgba(74,158,255,0.12)`

### green
Swap accent: `--color-accent: #00ff88`, `--color-accent-glow: rgba(0,255,136,0.4)`, `--color-border: rgba(0,255,136,0.12)`

## Available Palettes
- `default` — red accent
- `blue` — blue accent
- `green` — green accent

## Typography
- `--font-sans`: Inter, system-ui
- `--font-mono`: JetBrains Mono, monospace

## Restrictions
- Headlines only in Inter; all other text in JetBrains Mono
- Corner bracket decorations for badges and nav
- All spacing via CSS tokens only
```

- [ ] **Step 3: Create `tokens.css`**

```css
:root {
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-mono);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 4: Create `palettes/default.css`**

```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #e94560;
  --color-accent-glow: rgba(233,69,96,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(233,69,96,0.12);
}
```

- [ ] **Step 5: Create `palettes/blue.css`**

```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #4a9eff;
  --color-accent-glow: rgba(74,158,255,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(74,158,255,0.12);
}
```

- [ ] **Step 6: Create `palettes/green.css`**

```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #00ff88;
  --color-accent-glow: rgba(0,255,136,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(0,255,136,0.12);
}
```

- [ ] **Step 7: Create `components/nav/manifest.yaml`**

```yaml
component: nav
fields:
  brand_name:
    type: text
    required: true
  home_href:
    type: url
    required: false
    default: "/"
```

- [ ] **Step 8: Create `components/nav/nav.html`**

```html
<nav class="section nav">
  <div class="nav-inner">
    <a href="{{ home_href }}" class="nav__brand">
      <span class="nav__brand-text">{{ brand_name }}</span>
    </a>
  </div>
</nav>
```

- [ ] **Step 9: Create `components/nav/nav.css`**

```css
.nav {
  position: sticky; top: 0; z-index: var(--z-nav);
  background: rgba(6,6,9,0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-md) var(--space-xl);
}
.nav-inner { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; }
.nav__brand { text-decoration: none; }
.nav__brand-text {
  font-family: var(--font-mono);
  font-size: 0.7rem; font-weight: 600;
  color: var(--color-text-hi);
  letter-spacing: 0.2em; text-transform: uppercase;
}
```

- [ ] **Step 10: Create `components/hero/manifest.yaml`**

```yaml
component: hero
fields:
  headline:
    type: text
    required: true
  subline:
    type: text
    required: false
    default: ""
  badge:
    type: text
    required: false
    default: ""
```

- [ ] **Step 11: Create `components/hero/hero.html`**

```html
<section class="section hero">
  <div class="hero-inner">
    <div class="hero__badge">{{ badge }}</div>
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subline">{{ subline }}</p>
  </div>
</section>
```

- [ ] **Step 12: Create `components/hero/hero.css`**

```css
.hero { padding: var(--space-xl); background: var(--color-bg); }
.hero-inner { max-width: 1200px; margin: 0 auto; }
.hero__badge {
  font-family: var(--font-mono); font-size: 0.6rem;
  color: var(--color-accent); letter-spacing: 0.25em; text-transform: uppercase;
  display: inline-block; border: 1px solid var(--color-border);
  padding: 0.2rem 0.6rem; margin-bottom: var(--space-md); position: relative;
}
.hero__badge::before { content: ''; position: absolute; top: -1px; left: -1px; width: 6px; height: 6px; border-top: 1px solid var(--color-accent); border-left: 1px solid var(--color-accent); }
.hero__badge::after  { content: ''; position: absolute; bottom: -1px; right: -1px; width: 6px; height: 6px; border-bottom: 1px solid var(--color-accent); border-right: 1px solid var(--color-accent); }
.hero__headline {
  font-family: var(--font-sans); font-size: clamp(2.5rem, 6vw, 5rem);
  font-weight: 800; color: var(--color-text-hi); line-height: 1.05; margin-bottom: var(--space-md);
}
.hero__subline { font-family: var(--font-mono); font-size: 0.875rem; color: var(--color-text); line-height: 1.7; max-width: 600px; }
```

- [ ] **Step 13: Create section, cta, footer components**

`components/section/manifest.yaml`:
```yaml
component: section
fields:
  title:
    type: text
    required: true
  body:
    type: html
    required: true
```

`components/section/section.html`:
```html
<section class="section content-section">
  <div class="section-inner">
    <div class="section__label">// SECTION</div>
    <h2 class="section__title">{{ title }}</h2>
    <div class="section__body">{{ body | safe }}</div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content-section { padding: var(--space-xl); background: var(--color-bg2); border-top: 1px solid var(--color-border); }
.section-inner { max-width: 1200px; margin: 0 auto; }
.section__label { font-family: var(--font-mono); font-size: 0.55rem; color: var(--color-text-dim); letter-spacing: 0.25em; text-transform: uppercase; margin-bottom: var(--space-sm); }
.section__title { font-family: var(--font-sans); font-size: clamp(1.5rem, 3vw, 2.5rem); font-weight: 700; color: var(--color-text-hi); margin-bottom: var(--space-lg); }
.section__body { font-family: var(--font-mono); font-size: 0.875rem; color: var(--color-text); line-height: 1.8; }
```

`components/cta/manifest.yaml`:
```yaml
component: cta
fields:
  text:
    type: text
    required: true
  href:
    type: url
    required: true
```

`components/cta/cta.html`:
```html
<section class="section cta-section">
  <div class="cta-inner">
    <a href="{{ href }}" class="cta-btn">{{ text }}</a>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta-section { padding: var(--space-xl); background: var(--color-surface); border-top: 1px solid var(--color-border); text-align: center; }
.cta-inner { max-width: 1200px; margin: 0 auto; }
.cta-btn {
  display: inline-block; font-family: var(--font-mono); font-size: 0.75rem;
  font-weight: 600; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--color-bg); background: var(--color-accent);
  padding: 0.75rem 2rem; text-decoration: none; transition: box-shadow 0.2s;
}
.cta-btn:hover { box-shadow: 0 0 24px var(--color-accent-glow); }
```

`components/footer/manifest.yaml`:
```yaml
component: footer
fields:
  copy:
    type: text
    required: true
```

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="footer-inner">
    <span class="footer__copy">{{ copy }}</span>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { padding: var(--space-lg) var(--space-xl); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.footer-inner { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
.footer__copy { font-family: var(--font-mono); font-size: 0.65rem; color: var(--color-text-dim); letter-spacing: 0.1em; }
```

- [ ] **Step 14: Smoke test all three palettes**

Write `C:/tmp/graphs_recipe.yaml`:
```yaml
type: landing
profile: h2t-graphs
title: "Graphs Test"
sections:
  - component: nav
    content:
      brand_name: "LICHTPFAD"
  - component: hero
    content:
      headline: "Data Visualization"
      subline: "Built for technical audiences"
      badge: "v2.0"
  - component: footer
    content:
      copy: "© 2026 lichtpfad"
```

```
for palette in default blue green; do
  $H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
    --profile h2t-graphs --palette $palette --type landing \
    --recipe C:/tmp/graphs_recipe.yaml --out C:/tmp/graphs_$palette
done
```
Expected: 3 × `Built landing -> ...`

Verify `C:/tmp/graphs_blue/profile.css` contains `--color-accent: #4a9eff`.

- [ ] **Step 15: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-graphs/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-graphs profile — Inter+Mono, red/blue/green palettes"
```

---

### Task 7: h2t-pfad profile

Source: `C:/Users/<user>/.claude/plugins/cache/lichtpfad/h2t/2.14.1/skills/design/SKILL.md` (PFAD design system tokens already extracted).

**Files:** Create `plugins/h2t-creative/profiles/h2t-pfad/` with full profile structure + `fx/background.js`.

- [ ] **Step 1: Create `DESIGN.md`**

```markdown
# h2t-pfad

## Brand Intent
Elegant tactical dashboard aesthetic — small, monospace, red accent. Extracted from PFAD design system (lichtpfad internal dashboard). Corner bracket tags, `// SECTION` labels, micro-type scale at 12px base. Canvas2D dot-field particle network as background fx.

## Color Tokens

### default (red)
- `--color-bg`: `#0c0c0c`
- `--color-bg-card`: `#111111`
- `--color-fg`: `#eeeeee`
- `--color-fg-dim`: `#6e6e6e`
- `--color-fg-muted`: `#444444`
- `--color-accent`: `#d63030`
- `--color-accent-dim`: `rgba(214,48,48,0.4)`
- `--color-accent-glow`: `rgba(214,48,48,0.18)`
- `--color-border`: `rgba(255,255,255,0.10)`

## Available Palettes
- `default` — red accent (original PFAD)

## Typography
- `--font`: JetBrains Mono, IBM Plex Mono, monospace
- Base: 12px, labels: 8px, nano: 7.5px — no sans-serif

## Restrictions
- All text monospace only
- No border-radius (sharp edges)
- Corner brackets via CSS ::before/::after on key elements
- fx/ background: Canvas2D dot-field particle network
```

- [ ] **Step 2: Create `tokens.css`**

```css
:root {
  --font: 'JetBrains Mono', 'IBM Plex Mono', monospace;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 12px;
  background-color: var(--color-bg);
  color: var(--color-fg);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 3: Create `palettes/default.css`**

```css
:root {
  --color-bg: #0c0c0c;
  --color-bg-card: #111111;
  --color-fg: #eeeeee;
  --color-fg-dim: #6e6e6e;
  --color-fg-muted: #444444;
  --color-accent: #d63030;
  --color-accent-dim: rgba(214,48,48,0.4);
  --color-accent-glow: rgba(214,48,48,0.18);
  --color-border: rgba(255,255,255,0.10);
}
```

- [ ] **Step 4: Create `fx/background.js`**

Canvas2D dot-field particle network (follows h2t-creative `export function init(canvas)` / `export function destroy()` contract):

```javascript
let ctx, dots = [], animId;
const DOT_COUNT = 50, MAX_DIST = 120;

export function init(canvas) {
  ctx = canvas.getContext('2d');
  _resize(canvas);
  _createDots(canvas);
  _draw(canvas);
  window.addEventListener('resize', () => { _resize(canvas); _createDots(canvas); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(animId); animId = null; }
    else if (!animId) { _draw(canvas); }
  });
}

export function destroy() {
  cancelAnimationFrame(animId);
  dots = [];
}

function _resize(canvas) {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.cssText = 'position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:0.5;';
}

function _createDots(canvas) {
  dots = Array.from({ length: DOT_COUNT }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.12,
    vy: (Math.random() - 0.5) * 0.12,
    size: Math.random() < 0.5 ? 1 : 2,
    alpha: 0.03 + Math.random() * 0.21,
  }));
}

function _draw(canvas) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  dots.forEach(d => {
    d.x = (d.x + d.vx + canvas.width)  % canvas.width;
    d.y = (d.y + d.vy + canvas.height) % canvas.height;
  });
  for (let i = 0; i < dots.length; i++) {
    for (let j = i + 1; j < dots.length; j++) {
      const dx = dots[i].x - dots[j].x, dy = dots[i].y - dots[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < MAX_DIST) {
        ctx.beginPath();
        ctx.moveTo(dots[i].x, dots[i].y);
        ctx.lineTo(dots[j].x, dots[j].y);
        ctx.strokeStyle = `rgba(214,48,48,${0.06 * (1 - dist / MAX_DIST)})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }
  }
  dots.forEach(d => {
    ctx.fillStyle = `rgba(214,48,48,${d.alpha})`;
    ctx.fillRect(Math.round(d.x), Math.round(d.y), d.size, d.size);
  });
  animId = requestAnimationFrame(() => _draw(canvas));
}
```

- [ ] **Step 5: Create all 5 components**

`components/nav/manifest.yaml`:
```yaml
component: nav
fields:
  brand_name:
    type: text
    required: true
  home_href:
    type: url
    required: false
    default: "/"
```

`components/nav/nav.html`:
```html
<nav class="section nav">
  <div class="nav-inner">
    <a href="{{ home_href }}" class="nav__brand">
      <span class="nav__pfad">PFAD</span>
      <span class="nav__sep"> // </span>
      <span class="nav__name">{{ brand_name }}</span>
    </a>
  </div>
</nav>
```

`components/nav/nav.css`:
```css
.nav { position: sticky; top: 0; z-index: var(--z-nav); background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: 12px var(--space-lg); }
.nav-inner { max-width: 1400px; margin: 0 auto; }
.nav__brand { text-decoration: none; font-size: 8px; letter-spacing: 0.18em; text-transform: uppercase; display: inline-flex; gap: 4px; align-items: center; }
.nav__pfad { color: var(--color-accent); }
.nav__sep { color: var(--color-fg-muted); }
.nav__name { color: var(--color-fg-dim); }
```

`components/hero/manifest.yaml`:
```yaml
component: hero
fields:
  headline:
    type: text
    required: true
  subline:
    type: text
    required: false
    default: ""
  badge:
    type: text
    required: false
    default: ""
```

`components/hero/hero.html`:
```html
<section class="section hero">
  <div class="hero-inner">
    <div class="hero__label">{{ badge }}</div>
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subline">{{ subline }}</p>
  </div>
</section>
```

`components/hero/hero.css`:
```css
.hero { padding: var(--space-xl) var(--space-lg); background: var(--color-bg); position: relative; }
.hero::before { content: ''; position: absolute; top: 36px; left: 36px; width: 16px; height: 16px; border-top: 1px solid var(--color-fg-muted); border-left: 1px solid var(--color-fg-muted); }
.hero::after  { content: ''; position: absolute; bottom: 36px; right: 36px; width: 16px; height: 16px; border-bottom: 1px solid var(--color-fg-muted); border-right: 1px solid var(--color-fg-muted); }
.hero-inner { max-width: 1200px; margin: 0 auto; }
.hero__label { font-size: 8px; color: var(--color-fg-dim); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: var(--space-md); }
.hero__label::before { content: '// '; color: var(--color-accent); }
.hero__headline { font-size: 2.5rem; font-weight: 400; color: var(--color-fg); line-height: 1.15; margin-bottom: var(--space-md); }
.hero__subline { font-size: 11px; color: var(--color-fg-dim); line-height: 1.6; max-width: 600px; }
```

`components/section/manifest.yaml`:
```yaml
component: section
fields:
  title:
    type: text
    required: true
  body:
    type: html
    required: true
```

`components/section/section.html`:
```html
<section class="section content-section">
  <div class="section-inner">
    <div class="section__label">{{ title }}</div>
    <div class="section__body">{{ body | safe }}</div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content-section { padding: var(--space-xl) var(--space-lg); background: var(--color-bg-card); border-top: 1px solid var(--color-border); }
.section-inner { max-width: 1200px; margin: 0 auto; }
.section__label { font-size: 8px; color: var(--color-fg-muted); letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: var(--space-md); border-bottom: 1px solid var(--color-border); padding-bottom: var(--space-sm); }
.section__label::before { content: '// '; color: var(--color-accent); }
.section__body { font-size: 11px; color: var(--color-fg-dim); line-height: 1.7; }
```

`components/cta/manifest.yaml`:
```yaml
component: cta
fields:
  text:
    type: text
    required: true
  href:
    type: url
    required: true
```

`components/cta/cta.html`:
```html
<section class="section cta-section">
  <div class="cta-inner">
    <a href="{{ href }}" class="cta-btn"><span class="cta-btn__inner">{{ text }}</span><span class="corner-b"></span></a>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta-section { padding: var(--space-xl) var(--space-lg); background: var(--color-bg); border-top: 1px solid var(--color-border); text-align: center; }
.cta-inner { max-width: 1200px; margin: 0 auto; }
.cta-btn { display: inline-block; position: relative; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--color-accent); text-decoration: none; padding: var(--space-sm) var(--space-lg); border: 1px solid var(--color-accent-dim); transition: background 0.2s; }
.cta-btn:hover { background: var(--color-accent-glow); }
.cta-btn::before { content: ''; position: absolute; top: -1px; left: -1px; width: 6px; height: 6px; border-top: 1px solid var(--color-accent); border-left: 1px solid var(--color-accent); }
.cta-btn .corner-b { position: absolute; inset: 0; pointer-events: none; }
.cta-btn .corner-b::after { content: ''; position: absolute; bottom: -1px; right: -1px; width: 6px; height: 6px; border-bottom: 1px solid var(--color-accent); border-right: 1px solid var(--color-accent); }
```

`components/footer/manifest.yaml`:
```yaml
component: footer
fields:
  copy:
    type: text
    required: true
```

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="footer-inner">
    <span class="footer__pfad">PFAD</span>
    <span class="footer__sep"> // </span>
    <span class="footer__copy">{{ copy }}</span>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { padding: 12px var(--space-lg); background: var(--color-bg-card); border-top: 1px solid var(--color-border); }
.footer-inner { max-width: 1400px; margin: 0 auto; display: flex; align-items: center; gap: 4px; }
.footer__pfad { font-size: 8px; color: var(--color-accent); letter-spacing: 0.18em; text-transform: uppercase; }
.footer__sep { font-size: 8px; color: var(--color-fg-muted); }
.footer__copy { font-size: 8px; color: var(--color-fg-muted); letter-spacing: 0.1em; }
```

- [ ] **Step 6: Smoke test**

Write `C:/tmp/pfad_recipe.yaml`:
```yaml
type: landing
profile: h2t-pfad
title: "PFAD Test"
sections:
  - component: nav
    content:
      brand_name: "LICHTPFAD"
  - component: hero
    content:
      headline: "Tactical Dashboard"
      subline: "Focus architecture for deep work"
      badge: "v3.0"
  - component: footer
    content:
      copy: "© 2026 lichtpfad"
```

```
$H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
  --profile h2t-pfad --type landing \
  --recipe C:/tmp/pfad_recipe.yaml --out C:/tmp/pfad_dist
```
Expected: `Built landing -> C:/tmp/pfad_dist`. Check that `C:/tmp/pfad_dist/fx.js` exists.

- [ ] **Step 7: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-pfad/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-pfad profile — PFAD design system, dot-field fx"
```

---

### Task 8: h2t-terminal profile

Source: `h2t:deck` SKILL.md STYLE 1 (tokens already extracted above).

**Files:** Create `plugins/h2t-creative/profiles/h2t-terminal/` full profile.

- [ ] **Step 1: Create `DESIGN.md`**

```markdown
# h2t-terminal

## Brand Intent
Dark hacker aesthetic — monospace only, green accent, CSS scanline overlay. Extracted from h2t:deck STYLE 1. Uppercase labels, blinking cursor motif, crosshair cursor.

## Color Tokens

### default (green)
- `--color-bg`: `#0d1117`
- `--color-bg-light`: `#161b22`
- `--color-bg-card`: `#1c2129`
- `--color-text`: `#e6edf3`
- `--color-text-dim`: `#8b949e`
- `--color-accent`: `#00ff41`
- `--color-border`: `#30363d`

### amber
Same bg, `--color-accent: #d4a843`

### cyan
Same bg, `--color-accent: #4488cc`

## Available Palettes
- `default` — terminal green
- `amber` — amber
- `cyan` — blue-cyan

## Typography
- `--font`: JetBrains Mono, Fira Code, Menlo, monospace

## Restrictions
- No sans-serif
- CSS scanline overlay always present (in tokens.css body::after)
- Crosshair cursor
```

- [ ] **Step 2: Create `tokens.css`** (includes scanline overlay — part of aesthetic, not color)

```css
:root {
  --font: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 15px;
  background-color: var(--color-bg);
  color: var(--color-text);
  cursor: crosshair;
  -webkit-font-smoothing: antialiased;
}

body::after {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px
  );
  pointer-events: none;
  z-index: 9998;
}
```

- [ ] **Step 3: Create `palettes/default.css`**

```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #00ff41;
  --color-border: #30363d;
}
```

- [ ] **Step 4: Create `palettes/amber.css`**

```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #d4a843;
  --color-border: #30363d;
}
```

- [ ] **Step 5: Create `palettes/cyan.css`**

```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #4488cc;
  --color-border: #30363d;
}
```

- [ ] **Step 6: Create all 5 components**

`components/nav/manifest.yaml` — identical to h2t-graphs

`components/nav/nav.html`:
```html
<nav class="section nav">
  <div class="nav-inner">
    <a href="{{ home_href }}" class="nav__brand">&gt; {{ brand_name }}</a>
  </div>
</nav>
```

`components/nav/nav.css`:
```css
.nav { position: sticky; top: 0; z-index: var(--z-nav); background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: var(--space-md) var(--space-lg); }
.nav-inner { max-width: 1200px; margin: 0 auto; }
.nav__brand { text-decoration: none; font-size: 0.75rem; color: var(--color-accent); letter-spacing: 0.1em; }
```

`components/hero/manifest.yaml` — identical to h2t-graphs

`components/hero/hero.html`:
```html
<section class="section hero">
  <div class="hero-inner">
    <div class="hero__prompt">{{ badge }}</div>
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subline">{{ subline }}</p>
  </div>
</section>
```

`components/hero/hero.css`:
```css
.hero { padding: var(--space-xl) var(--space-lg); background: var(--color-bg); }
.hero-inner { max-width: 1200px; margin: 0 auto; }
.hero__prompt { font-size: 0.75rem; color: var(--color-text-dim); margin-bottom: var(--space-md); }
.hero__prompt::before { content: '$ '; color: var(--color-accent); }
.hero__headline {
  font-size: clamp(2rem, 5vw, 4rem); font-weight: 700; color: var(--color-text);
  text-transform: uppercase; letter-spacing: 2px; line-height: 1.1; margin-bottom: var(--space-md);
}
.hero__headline::after { content: '\2588'; animation: blink 1s step-end infinite; color: var(--color-accent); margin-left: 4px; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
.hero__subline { font-size: 0.875rem; color: var(--color-text-dim); line-height: 1.6; max-width: 600px; }
```

`components/section/manifest.yaml` — identical to h2t-graphs

`components/section/section.html`:
```html
<section class="section content-section">
  <div class="section-inner">
    <div class="section__label">{{ title }}</div>
    <div class="section__body">{{ body | safe }}</div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content-section { padding: var(--space-xl) var(--space-lg); background: var(--color-bg-light); border-top: 1px solid var(--color-border); }
.section-inner { max-width: 1200px; margin: 0 auto; }
.section__label { font-size: 0.7rem; color: var(--color-accent); text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: var(--space-md); }
.section__label::before { content: '// '; }
.section__body { font-size: 0.875rem; color: var(--color-text-dim); line-height: 1.8; }
```

`components/cta/manifest.yaml` — identical to h2t-graphs

`components/cta/cta.html`:
```html
<section class="section cta-section">
  <div class="cta-inner">
    <a href="{{ href }}" class="cta-btn">{{ text }}</a>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta-section { padding: var(--space-xl) var(--space-lg); background: var(--color-bg); border-top: 1px solid var(--color-border); text-align: center; }
.cta-inner { max-width: 1200px; margin: 0 auto; }
.cta-btn { display: inline-block; font-size: 0.75rem; color: var(--color-bg); background: var(--color-accent); text-decoration: none; padding: 0.6rem 1.5rem; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700; transition: opacity 0.2s; }
.cta-btn:hover { opacity: 0.85; }
```

`components/footer/manifest.yaml` — identical to h2t-graphs

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="footer-inner">
    <span class="footer__copy">{{ copy }}</span>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { padding: var(--space-md) var(--space-lg); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.footer-inner { max-width: 1200px; margin: 0 auto; }
.footer__copy { font-size: 0.65rem; color: var(--color-text-dim); letter-spacing: 0.1em; }
```

- [ ] **Step 7: Smoke test**

Write `C:/tmp/terminal_recipe.yaml`:
```yaml
type: landing
profile: h2t-terminal
title: "Terminal Test"
sections:
  - component: nav
    content:
      brand_name: "SYSTEM"
  - component: hero
    content:
      headline: "INITIALIZE"
      subline: "dark hacker aesthetic for technical content"
      badge: "exec landing.sh"
  - component: footer
    content:
      copy: "© 2026 system"
```

```
$H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
  --profile h2t-terminal --palette amber --type landing \
  --recipe C:/tmp/terminal_recipe.yaml --out C:/tmp/terminal_amber
```
Expected: `Built landing -> C:/tmp/terminal_amber`. Verify `--color-accent: #d4a843` in `profile.css`.

- [ ] **Step 8: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-terminal/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-terminal profile — mono scanlines, green/amber/cyan palettes"
```

---

### Task 9: h2t-editorial profile

Source: `h2t:deck` SKILL.md STYLE 2.

**Files:** Create `plugins/h2t-creative/profiles/h2t-editorial/` full profile.

- [ ] **Step 1: Create `DESIGN.md`**

```markdown
# h2t-editorial

## Brand Intent
Light book-like aesthetic — serif headlines, generous whitespace, classical typography. Extracted from h2t:deck STYLE 2. Playfair Display for headlines, Inter for body.

## Color Tokens

### default (dark ink)
- `--color-bg`: `#faf9f6`
- `--color-bg-light`: `#f0eeeb`
- `--color-bg-card`: `#ffffff`
- `--color-text`: `#1a1a1a`
- `--color-text-dim`: `#6b6b6b`
- `--color-accent`: `#c45a3c`
- `--color-border`: `#e0ddd8`

### warm
- `--color-bg`: `#fdf8f0`, `--color-bg-light`: `#f5ede0`, `--color-bg-card`: `#fffdf9`
- `--color-text`: `#2a1f14`, `--color-text-dim`: `#8a7a6a`, `--color-accent`: `#b85c30`, `--color-border`: `#e8ddd0`

### night
- `--color-bg`: `#1a1614`, `--color-bg-light`: `#242018`, `--color-bg-card`: `#2a2620`
- `--color-text`: `#e8dfd4`, `--color-text-dim`: `#9a9080`, `--color-accent`: `#d4aa50`, `--color-border`: `#403830`

## Available Palettes
- `default` — dark ink
- `warm` — cream
- `night` — dark gold

## Typography
- `--font-display`: Playfair Display, Georgia, serif
- `--font-body`: Inter, Helvetica Neue, sans-serif

## Restrictions
- Headlines always in Playfair Display
- Body always in Inter
- Large leading (1.75+)
```

- [ ] **Step 2: Create `tokens.css`**

```css
:root {
  --font-display: 'Playfair Display', 'Georgia', serif;
  --font-body: 'Inter', 'Helvetica Neue', sans-serif;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font-body);
  font-size: 18px;
  background-color: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 3: Create the three palette files**

`palettes/default.css`:
```css
:root {
  --color-bg: #faf9f6;
  --color-bg-light: #f0eeeb;
  --color-bg-card: #ffffff;
  --color-text: #1a1a1a;
  --color-text-dim: #6b6b6b;
  --color-accent: #c45a3c;
  --color-border: #e0ddd8;
}
```

`palettes/warm.css`:
```css
:root {
  --color-bg: #fdf8f0;
  --color-bg-light: #f5ede0;
  --color-bg-card: #fffdf9;
  --color-text: #2a1f14;
  --color-text-dim: #8a7a6a;
  --color-accent: #b85c30;
  --color-border: #e8ddd0;
}
```

`palettes/night.css`:
```css
:root {
  --color-bg: #1a1614;
  --color-bg-light: #242018;
  --color-bg-card: #2a2620;
  --color-text: #e8dfd4;
  --color-text-dim: #9a9080;
  --color-accent: #d4aa50;
  --color-border: #403830;
}
```

- [ ] **Step 4: Create all 5 components**

`components/nav/manifest.yaml` — identical to h2t-graphs

`components/nav/nav.html`:
```html
<nav class="section nav">
  <div class="nav-inner">
    <a href="{{ home_href }}" class="nav__brand">{{ brand_name }}</a>
  </div>
</nav>
```

`components/nav/nav.css`:
```css
.nav { position: sticky; top: 0; z-index: var(--z-nav); background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: var(--space-md) var(--space-xl); }
.nav-inner { max-width: 1100px; margin: 0 auto; }
.nav__brand { text-decoration: none; font-family: var(--font-body); font-size: 0.8rem; font-weight: 500; color: var(--color-text); letter-spacing: 0.05em; text-transform: uppercase; }
```

`components/hero/manifest.yaml` — identical to h2t-graphs

`components/hero/hero.html`:
```html
<section class="section hero">
  <div class="hero-inner">
    <p class="hero__kicker">{{ badge }}</p>
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subline">{{ subline }}</p>
  </div>
</section>
```

`components/hero/hero.css`:
```css
.hero { padding: var(--space-xl); background: var(--color-bg); }
.hero-inner { max-width: 1100px; margin: 0 auto; }
.hero__kicker { font-family: var(--font-body); font-size: 0.65rem; font-weight: 500; color: var(--color-accent); text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: var(--space-md); }
.hero__headline { font-family: var(--font-display); font-size: clamp(2.5rem, 5vw, 4.5rem); font-weight: 700; color: var(--color-text); line-height: 1.15; margin-bottom: var(--space-md); }
.hero__subline { font-family: var(--font-body); font-size: 1.1rem; color: var(--color-text-dim); line-height: 1.75; max-width: 600px; }
```

`components/section/manifest.yaml` — identical to h2t-graphs

`components/section/section.html`:
```html
<section class="section content-section">
  <div class="section-inner">
    <h2 class="section__title">{{ title }}</h2>
    <div class="section__body">{{ body | safe }}</div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content-section { padding: var(--space-xl); background: var(--color-bg-light); border-top: 1px solid var(--color-border); }
.section-inner { max-width: 1100px; margin: 0 auto; }
.section__title { font-family: var(--font-display); font-size: clamp(1.5rem, 3vw, 2.5rem); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-lg); border-top: 1px solid var(--color-border); padding-top: var(--space-lg); }
.section__body { font-family: var(--font-body); font-size: 1rem; color: var(--color-text); line-height: 1.75; }
.section__body blockquote { border-left: 3px solid var(--color-accent); margin: var(--space-lg) 0; padding: var(--space-sm) var(--space-md); font-family: var(--font-display); font-style: italic; font-size: 1.1rem; }
```

`components/cta/manifest.yaml` — identical to h2t-graphs

`components/cta/cta.html`:
```html
<section class="section cta-section">
  <div class="cta-inner">
    <a href="{{ href }}" class="cta-btn">{{ text }}</a>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta-section { padding: var(--space-xl); background: var(--color-bg-card); border-top: 1px solid var(--color-border); text-align: center; }
.cta-inner { max-width: 1100px; margin: 0 auto; }
.cta-btn { display: inline-block; font-family: var(--font-body); font-size: 0.875rem; font-weight: 500; color: #ffffff; background: var(--color-accent); padding: 0.75rem 2rem; text-decoration: none; border-radius: var(--radius-sm); transition: opacity 0.2s; }
.cta-btn:hover { opacity: 0.9; }
```

`components/footer/manifest.yaml` — identical to h2t-graphs

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="footer-inner">
    <span class="footer__copy">{{ copy }}</span>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { padding: var(--space-lg) var(--space-xl); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.footer-inner { max-width: 1100px; margin: 0 auto; }
.footer__copy { font-family: var(--font-body); font-size: 0.75rem; color: var(--color-text-dim); }
```

- [ ] **Step 5: Smoke test all three palettes**

Write `C:/tmp/editorial_recipe.yaml`:
```yaml
type: landing
profile: h2t-editorial
title: "Editorial Test"
sections:
  - component: nav
    content:
      brand_name: "LICHTPFAD"
  - component: hero
    content:
      headline: "Мастерство через практику"
      subline: "25 years of Houdini expertise"
      badge: "Hou2Touch School"
  - component: footer
    content:
      copy: "© 2026 Hou2Touch"
```

```
for palette in default warm night; do
  $H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
    --profile h2t-editorial --palette $palette --type landing \
    --recipe C:/tmp/editorial_recipe.yaml --out C:/tmp/editorial_$palette
done
```
Expected: 3 × `Built landing -> ...`

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-editorial/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-editorial profile — Playfair+Inter, dark-ink/warm/night"
```

---

### Task 10: h2t-mono profile

Source: specdesigner.netlify.app aesthetic — ultra-minimal monospace, single red accent, zero decoration.

**Files:** Create `plugins/h2t-creative/profiles/h2t-mono/` full profile.

- [ ] **Step 1: Create `DESIGN.md`**

```markdown
# h2t-mono

## Brand Intent
Ultra-minimal. Pure monospace, near-black bg, single red accent, zero decoration. Differentiation through spacing only — no brackets, no labels, no separators. CTA uses one filled + one ghost button. Extracted from SpecDesigner aesthetic (specdesigner.netlify.app).

## Color Tokens

### default (red)
- `--color-bg`: `#0d0d0d`
- `--color-text`: `#e0e0e0`
- `--color-text-dim`: `#666666`
- `--color-accent`: `#e8352b`
- `--color-border`: `#1a1a1a`

### white (inverted)
- `--color-bg`: `#f5f5f5`, `--color-text`: `#0d0d0d`, `--color-text-dim`: `#888888`
- `--color-accent`: `#e8352b`, `--color-border`: `#e0e0e0`

### blue
- `--color-bg`: `#0d0d0d`, `--color-text`: `#e0e0e0`, `--color-text-dim`: `#666666`
- `--color-accent`: `#2563eb`, `--color-border`: `#1a1a1a`

## Available Palettes
- `default` — red accent
- `white` — inverted light
- `blue` — blue accent

## Typography
- `--font`: JetBrains Mono, monospace

## Restrictions
- Zero decorative elements
- No border-radius
- All labels uppercase, body mixed-case
```

- [ ] **Step 2: Create `tokens.css`**

```css
:root {
  --font: 'JetBrains Mono', monospace;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 14px;
  background-color: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 3: Create the three palette files**

`palettes/default.css`:
```css
:root {
  --color-bg: #0d0d0d;
  --color-text: #e0e0e0;
  --color-text-dim: #666666;
  --color-accent: #e8352b;
  --color-border: #1a1a1a;
}
```

`palettes/white.css`:
```css
:root {
  --color-bg: #f5f5f5;
  --color-text: #0d0d0d;
  --color-text-dim: #888888;
  --color-accent: #e8352b;
  --color-border: #e0e0e0;
}
```

`palettes/blue.css`:
```css
:root {
  --color-bg: #0d0d0d;
  --color-text: #e0e0e0;
  --color-text-dim: #666666;
  --color-accent: #2563eb;
  --color-border: #1a1a1a;
}
```

- [ ] **Step 4: Create all 5 components**

`components/nav/manifest.yaml` — identical to h2t-graphs

`components/nav/nav.html`:
```html
<nav class="section nav">
  <div class="nav-inner">
    <a href="{{ home_href }}" class="nav__brand">{{ brand_name }}</a>
  </div>
</nav>
```

`components/nav/nav.css`:
```css
.nav { position: sticky; top: 0; z-index: var(--z-nav); background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: var(--space-md) var(--space-xl); }
.nav-inner { max-width: 1200px; margin: 0 auto; }
.nav__brand { text-decoration: none; font-size: 0.7rem; color: var(--color-text-dim); letter-spacing: 0.2em; text-transform: uppercase; }
.nav__brand:hover { color: var(--color-accent); }
```

`components/hero/manifest.yaml` — identical to h2t-graphs

`components/hero/hero.html`:
```html
<section class="section hero">
  <div class="hero-inner">
    <p class="hero__tag">{{ badge }}</p>
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subline">{{ subline }}</p>
  </div>
</section>
```

`components/hero/hero.css`:
```css
.hero { padding: var(--space-xl); background: var(--color-bg); }
.hero-inner { max-width: 1200px; margin: 0 auto; }
.hero__tag { font-size: 0.6rem; color: var(--color-accent); text-transform: uppercase; letter-spacing: 0.3em; margin-bottom: var(--space-lg); }
.hero__headline { font-size: clamp(2.5rem, 6vw, 5.5rem); font-weight: 400; color: var(--color-text); line-height: 1.0; letter-spacing: -0.02em; margin-bottom: var(--space-lg); }
.hero__subline { font-size: 0.85rem; color: var(--color-text-dim); line-height: 1.7; max-width: 500px; }
```

`components/section/manifest.yaml` — identical to h2t-graphs

`components/section/section.html`:
```html
<section class="section content-section">
  <div class="section-inner">
    <h2 class="section__title">{{ title }}</h2>
    <div class="section__body">{{ body | safe }}</div>
  </div>
</section>
```

`components/section/section.css`:
```css
.content-section { padding: var(--space-xl); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.section-inner { max-width: 1200px; margin: 0 auto; }
.section__title { font-size: 0.6rem; color: var(--color-accent); text-transform: uppercase; letter-spacing: 0.25em; margin-bottom: var(--space-lg); }
.section__body { font-size: 0.875rem; color: var(--color-text-dim); line-height: 1.75; max-width: 700px; }
```

`components/cta/manifest.yaml`:
```yaml
component: cta
fields:
  text:
    type: text
    required: true
  href:
    type: url
    required: true
  text_ghost:
    type: text
    required: false
    default: "Learn more"
  href_ghost:
    type: url
    required: false
    default: "#"
```

`components/cta/cta.html`:
```html
<section class="section cta-section">
  <div class="cta-inner">
    <a href="{{ href }}" class="cta-btn cta-btn--filled">{{ text }}</a>
    <a href="{{ href_ghost }}" class="cta-btn cta-btn--ghost">{{ text_ghost }}</a>
  </div>
</section>
```

`components/cta/cta.css`:
```css
.cta-section { padding: var(--space-xl); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.cta-inner { max-width: 1200px; margin: 0 auto; display: flex; gap: var(--space-md); align-items: center; flex-wrap: wrap; }
.cta-btn { display: inline-block; font-size: 0.7rem; text-decoration: none; text-transform: uppercase; letter-spacing: 0.2em; padding: 0.6rem 1.5rem; transition: opacity 0.15s; }
.cta-btn--filled { color: var(--color-bg); background: var(--color-accent); }
.cta-btn--ghost { color: var(--color-text-dim); border: 1px solid var(--color-border); }
.cta-btn:hover { opacity: 0.8; }
```

`components/footer/manifest.yaml` — identical to h2t-graphs

`components/footer/footer.html`:
```html
<footer class="section footer">
  <div class="footer-inner">
    <span class="footer__copy">{{ copy }}</span>
  </div>
</footer>
```

`components/footer/footer.css`:
```css
.footer { padding: var(--space-lg) var(--space-xl); background: var(--color-bg); border-top: 1px solid var(--color-border); }
.footer-inner { max-width: 1200px; margin: 0 auto; }
.footer__copy { font-size: 0.6rem; color: var(--color-text-dim); letter-spacing: 0.1em; text-transform: uppercase; }
```

- [ ] **Step 5: Smoke test all palettes**

Write `C:/tmp/mono_recipe.yaml`:
```yaml
type: landing
profile: h2t-mono
title: "Mono Test"
sections:
  - component: nav
    content:
      brand_name: "LICHTPFAD"
  - component: hero
    content:
      headline: "Ultra Minimal"
      subline: "zero decoration, maximum clarity"
      badge: "v1.0"
  - component: cta
    content:
      text: "Start"
      href: "#"
      text_ghost: "Learn more"
      href_ghost: "#about"
  - component: footer
    content:
      copy: "© 2026 LICHTPFAD"
```

```
for palette in default white blue; do
  $H2T_PYTHON "$PLUGIN_ROOT/assembler.py" \
    --profile h2t-mono --palette $palette --type landing \
    --recipe C:/tmp/mono_recipe.yaml --out C:/tmp/mono_$palette
  echo "Built mono/$palette"
done
```
Expected: 3 × `Built mono/<palette>`

- [ ] **Step 6: Run full test suite one final time**

```
$H2T_PYTHON -m pytest tests/h2t_creative/test_assembler.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-creative/profiles/h2t-mono/
git -C C:/dev/h2t-skills commit -m "feat(h2t-creative): add h2t-mono profile — ultra-minimal, red/white/blue palettes"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Palette-aware `_build_profile_css` | Task 1 |
| Deck pipeline fix (was reading tokens.css directly) | Task 1 |
| `--palette` CLI flag, `flag > recipe > default` precedence | Task 1 |
| Unknown palette → hard error with available list | Task 1 |
| Legacy profile fallback (no palettes/ dir) | Task 1 |
| style-validate new checks (palettes/default.css) | Task 2 |
| style-create → palettes/ output + offer step | Task 3 |
| h2t-default migration | Task 4 |
| Skill wizard 3-state palette selection | Task 5 |
| h2t-graphs profile (red/blue/green palettes) | Task 6 |
| h2t-pfad profile + fx/background.js dot field | Task 7 |
| h2t-terminal profile (green/amber/cyan palettes) | Task 8 |
| h2t-editorial profile (dark-ink/warm/night palettes) | Task 9 |
| h2t-mono profile (red/white/blue palettes) | Task 10 |
| DESIGN.md schema for all profiles | Tasks 6–10 |

**Type consistency:** `_build_profile_css(profile_dir, sections, palette)` signature is uniform. All callers (`assemble_landing`, `assemble_deck`, `main_assemble`) pass `palette` consistently. All component manifests use the same field names for recipe portability (`brand_name`, `home_href`, `headline`, `subline`, `badge`, `title`, `body`, `text`, `href`, `copy`).

**h2t-mono cta note:** `text_ghost`/`href_ghost` are profile-specific optional fields with defaults — recipes from other profiles still work.
