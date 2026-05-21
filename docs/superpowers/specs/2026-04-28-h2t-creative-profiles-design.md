---
title: "h2t-creative v3 · Phase 1 — Profiles Design Spec"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-04-28"
milestone: ""
---
# h2t-creative v3 · Phase 1 — Profiles Design Spec

**Date:** 2026-04-28
**Status:** Approved
**Scope:** Extraction and migration of 5 existing design systems into h2t-creative profile format. New styles are out of scope — they go through `h2t-creative:style-create` workflow.

---

## 1. Architecture

### Profile directory structure

```
profiles/{name}/
  DESIGN.md              ← brand intent, typography rules, available palettes list
  tokens.css             ← fonts, spacing, radii, z-index ONLY (no colors)
  palettes/
    default.css          ← default --color-* variables
    blue.css             ← alternative palettes (profile-specific set)
    green.css
  components/
    nav/
      nav.html           ← profile-specific markup
      nav.css            ← styles using only --color-* and font/spacing tokens
      manifest.yaml
    hero/...
    section/...
    cta/...
    footer/...
```

### Key principles

- `tokens.css` contains **zero color variables** — fonts, spacing, radii, z-index only
- `palettes/default.css` contains all `--color-*` variables for the default color scheme
- Component HTML/CSS is **fully isolated per profile** — no shared markup between profiles
- Component CSS uses only CSS custom properties from tokens.css + active palette — never hardcoded values
- Adding a new palette = one new CSS file, nothing else changes

### Assembler changes

#### 1. Palette-aware `_build_profile_css` (replaces current implementation)

Both `assemble_landing()` and `assemble_deck()` use this function — deck currently bypasses it and reads `tokens.css` directly. **This is fixed in Phase 1**: deck switches to `_build_profile_css` too, making both pipelines palette-aware simultaneously.

Fallback rule: if `palettes/` directory does not exist in the profile, assembler falls back to reading colors from `tokens.css` directly. This makes the schema change **non-breaking** for existing profiles that haven't migrated yet.

```python
def _build_profile_css(profile_dir, sections, palette="default"):
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
        # Legacy profile without palettes/ — read full tokens.css (colors included)
        color_css = ""  # tokens.css already read below, contains colors

    parts = [(profile_dir / "tokens.css").read_text(encoding="utf-8")]
    if color_css:
        parts.append(color_css)

    seen = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
            seen.add(name)
    return "\n".join(parts)
```

#### 2. Palette source of truth

**Canonical source: `recipe.yaml`** — the recipe is the single source of truth for palette selection in skill-driven use.

```yaml
type: landing
profile: h2t-graphs
palette: blue        # optional — omit to use profile's default palette
title: "..."
sections: [...]
```

**`--palette` CLI flag** — override for direct CLI use only. Takes precedence over `recipe.palette` if both are present. No error on conflict — CLI flag wins silently.

```bash
# skill-driven: palette from recipe
python assembler.py --profile h2t-graphs --type landing --recipe recipe.yaml --out ./dist

# CLI override: ignores recipe.palette if present
python assembler.py --profile h2t-graphs --palette blue --type landing --recipe recipe.yaml --out ./dist
```

Assembler precedence: `--palette flag > recipe.get("palette") > "default"`.

Unknown palette → hard error with list of available palettes.

#### 4. Skill wizard update (`/landing`, `/deck`)

Both skills add a palette selection step after profile is chosen:

```
Step 1: Choose profile  →  ls profiles/
Step 1b: Choose palette →  three states (see below)
Step 2: Build recipe    →  includes palette: <name> field only if non-default chosen
```

**Three states for Step 1b:**

| State | Condition | Action |
|-------|-----------|--------|
| No palettes | `palettes/` dir does not exist | Skip question. Do NOT write `palette:` field to recipe. |
| Default only | Only `palettes/default.css` exists | Skip question silently. Do NOT write `palette:` field. |
| Multiple palettes | Two or more `*.css` files in `palettes/` | Ask user to choose. Write `palette: <name>` only if non-default chosen. |

If profile has no `palettes/` dir, assembler falls back to reading colors from `tokens.css` directly (legacy path).

---

### h2t-default migration

`h2t-default` is migrated as part of Phase 1 (not a prerequisite — done as first profile task):

- `tokens.css` → strip color vars, keep fonts/spacing/radii/z-index
- Colors → `palettes/default.css`
- Assembler fallback ensures `/landing` and `/deck` keep working during migration

---

## 2. Tool migration: style-create and style-validate

Both tools are updated in Phase 1 to match the new schema. Without this, they become broken immediately after the first profile is created.

### style-validate changes

Current check (broken after refactor):
> "tokens.css must define `--color-bg`, `--color-fg`, `--color-accent`"

New check:
```
✓ tokens.css exists and defines font/spacing vars (NOT color vars)
✓ palettes/default.css exists and defines --color-bg, --color-fg, --color-accent
✓ No --color-* vars in tokens.css (warn if found)
✓ All *.css files in palettes/ define the same set of --color-* vars as default.css
```

### style-create changes

Current behaviour: generates colors into `tokens.css`.

New behaviour:
1. Ask color palette questions as before
2. Write colors → `palettes/default.css`
3. Write fonts/spacing/radii → `tokens.css`
4. Offer to add more palettes immediately: "Want to add alternative color palettes now?"

---

## 3. Five Profiles

### h2t-pfad

**Source:** `h2t:design` SKILL.md (PFAD Design System)
**Character:** Elegant, small, all-monospace. Tactical dashboard aesthetic with micro-animations.

**Typography:**
- `--font`: JetBrains Mono, IBM Plex Mono, monospace
- Base font-size: 12px
- Labels: 8px, small elements: 7.5px
- No sans-serif anywhere

**Default palette (red):**
- `--bg`: dark near-black
- `--accent`: red (`#d63030` PFAD variant)
- Additional palettes: TBD during extraction

**fx/ support:** Canvas2D micro-animations (oscilloscope, dot-field particle network, radar sweep, scanner). Implemented as `fx/background.js` following h2t-creative fx/ contract.

**Components:** All 5 standard components with PFAD-specific markup — corner bracket tags, `// SECTION` labels, monospace type scale.

---

### h2t-graphs

**Source:** `C:/dev/h2t-landings/graphs/index.html` (899 lines, full source on disk)
**Character:** Bold typographic hierarchy + mono labels. Data-rich product landing aesthetic.

**Typography:**
- `--sans`: Inter, system-ui (headlines, 700–800 weight)
- `--mono`: JetBrains Mono (nav, labels, code, captions)
- Large bold headlines, mono everything else

**Default palette (red):**
- `--bg`: `#060609`
- `--bg2`: `#0a0a10`
- `--surface`: `#0e0e16`
- `--accent`: `#e94560`
- `--accent-glow`: `rgba(233,69,96,0.4)`
- `--green`: `#00ff88`
- `--blue`: `#4a9eff`
- `--amber`: `#ffb800`
- `--text`: `#a0a0b8`
- `--text-hi`: `#d0d0e0`
- `--text-dim`: `#3a3a50`
- `--border`: `rgba(233,69,96,0.12)`
- Additional palettes: blue, green (swap accent color family)

**Components:** Bold hero with bracket badge tag, mono nav, data-oriented section, strong CTA, mono footer.

---

### h2t-terminal

**Source:** `h2t:deck` SKILL.md — STYLE 1
**Character:** Dark hacker aesthetic. Monospace, green accent, scanline overlay.

**Typography:**
- `--font`: JetBrains Mono (single font stack)
- Uppercase labels, code-like hierarchy

**Default palette (green):**
- Dark bg, green accent (`#00ff41` terminal green)
- Additional palettes: amber, cyan

**fx/ support:** CSS scanline overlay (no JS required). Optional: CRT glow effect.

**Components:** Terminal-styled markup — prompt-like nav (`> brand`), code-block hero, monospace section, ghost CTA button, minimal footer.

---

### h2t-editorial

**Source:** `h2t:deck` SKILL.md — STYLE 2
**Character:** Light, book-like. Serif headlines, generous whitespace, classical typography.

**Typography:**
- `--font-display`: Playfair Display (headlines, 400–800)
- `--font-body`: Inter (body, 400–500)
- Large leading, elegant spacing

**Default palette (dark ink):**
- Light bg (#fafafa), near-black fg (#1a1a1a), restrained accent
- Additional palettes: warm (cream bg), night (dark bg + gold)

**Components:** Serif hero, editorial section with pull-quotes, understated CTA, refined footer.

---

### h2t-mono

**Source:** specdesigner.netlify.app
**Character:** Ultra-minimal. Pure monospace, pure black, single red accent, zero decoration.

**Typography:**
- `--font`: monospace (system or JetBrains Mono)
- All text same weight/size — differentiation through spacing only

**Default palette (red):**
- `--bg`: `#0d0d0d`
- `--accent`: `#e8352b` (SpecDesigner red)
- Additional palettes: white (inverted), blue

**Components:** Minimal markup — no decorative elements, no bracket tags, pure content. CTA = one filled + one ghost button, uppercase text only.

---

## 4. DESIGN.md Schema (updated)

```markdown
# {Profile Name}

## Brand Intent
One paragraph.

## Color Tokens
Listed per palette. Default:
- `--color-bg`: ...

## Available Palettes
- `default` — description
- `blue` — description

## Typography
- `--font-display`: ...
- `--font-body`: ...

## Restrictions
- ...
```

---

## 5. Implementation Order

1. **Assembler update** — palette-aware `_build_profile_css`, `--palette` flag, `palette` field in recipe, deck pipeline fix
2. **style-validate update** — new checks for palettes/default.css
3. **style-create update** — generate palettes/ instead of colors in tokens.css
4. **h2t-default migration** — split tokens.css → tokens.css + palettes/default.css; test landing + deck still work
5. **h2t-graphs profile** — extract from `h2t-landings/graphs/index.html`
6. **h2t-pfad profile** — extract from `h2t:design` SKILL.md
7. **h2t-terminal profile** — extract from `h2t:deck` STYLE 1
8. **h2t-editorial profile** — extract from `h2t:deck` STYLE 2
9. **h2t-mono profile** — extract from specdesigner aesthetic
10. **Skill wizard update** — `/landing` and `/deck` palette selection step
11. **Tests** — update assembler tests for palette paths + fallback behaviour

---

## 6. Out of Scope

- New profiles beyond the 5 listed — use `h2t-creative:style-create` workflow
- Three.js WebGL backgrounds — fx/ uses Canvas2D; Three.js is future
- Deck-specific component variants — Phase 1 landing components only; deck components in Phase 2
- Block library (10–20 blocks) — Phase 2 spec
