# h2t-creative Recovery Spec — Phase 2c: Legacy Fidelity Recovery

**Date:** 2026-05-04
**Status:** Draft
**Prerequisite:** `2026-05-04-h2t-creative-recovery-audit.md` (approved)
**Issue:** #83 (priority:p0, phase:design)

---

## 1. Goal

Restore visual fidelity of h2t-creative profiles to their original legacy skill counterparts.

This is a corrective spec. The v1.2.0 migration was wrong — visual gate compared profiles against themselves, not against reference sources. Recovery means restoring what was lost during migration, not designing new components.

---

## 2. Non-Goals

- Do not bump minor version until visual gate R4 passes
- Do not extend the shared component library with new generic blocks
- Do not add new profiles
- Do not implement style-create v2 or style-validate v2 (separate track)
- v1.2.0 is **not** the reference — it is the subject of recovery
- Do not treat Phase 2b "Aesthetic Recovery" results as valid baseline

---

## 3. Source of Truth

| Profile | Primary Source | Secondary Source |
|---------|---------------|-----------------|
| `h2t-graphs` | `C:/dev/h2t-landings/graphs/index.html` | `h2t:landing` v2.14.1 SKILL.md |
| `h2t-mono` | `specdesigner.netlify.app` (reference screenshot) | — |
| `h2t-pfad` | `h2t:design` v2.14.1 SKILL.md | `h2t:landing` v2.14.1 SKILL.md |
| `h2t-terminal` | `h2t:deck` v2.14.1 SKILL.md (STYLE 1) | — |
| `h2t-editorial` | `h2t:deck` v2.14.1 SKILL.md (STYLE 2) | — |

Live reference screenshots: `docs/visual-regression/reference/`

Any profile change without a declared source is prohibited.

---

## 4. Architecture

### Shared vs Profile-Specific Components

Shared HTML contracts are allowed. The rule is:

- Light profiles (`h2t-default`, `h2t-editorial`): shared components are fine as-is.
- Dark / reference profiles (`h2t-graphs`, `h2t-pfad`, `h2t-terminal`, `h2t-mono`): shared components must be replaced or overridden by profile-specific rich variants that match the visual grammar of the source.

Override resolution: if `profiles/<name>/components/<component>/` exists, assembler uses it. If not, assembler falls back to `shared/components/<component>/`. No other fallback.

### Profile Source Dossier

Every profile undergoing recovery gains a `sources/` directory:

```
profiles/<name>/
  sources/
    references.yaml       ← live URLs, screenshot paths, legacy skill paths
    legacy-skill.md       ← relevant excerpt from legacy SKILL.md
    screenshots/          ← captured reference images
```

`references.yaml` must be committed before any profile changes begin. Profile recovery without this file is blocked.

### Validation Recipe

Every recovered profile gets a `recipe.yaml` that exercises its visual grammar — not a generic placeholder. The recipe must include at least one profile-specific component (e.g., `hud-panel`, `stats-bar`, `chip`) to be valid.

### Fidelity Gate

Visual gate compares generated output against `sources/screenshots/` or live reference URL. A gate that only verifies colors and fonts is insufficient. The gate must verify:

- Profile-specific structural elements are present (brackets, scanlines, chip tags, overlays, etc.)
- Component archetypes from source are represented
- No generic shared-component structure replacing a known profile pattern

Failure condition: shared component structure where profile-specific rich component is documented in audit.

---

## 5. Implementation Slices

### R1 — First Slice: h2t-graphs + h2t-mono

**Rationale:** h2t-graphs has the highest fidelity gap (most documented missing components) and a full HTML source on disk. h2t-mono is the simplest dark profile and its reference is visually distinct.

**h2t-graphs — components to restore:**
- `hud-panel` (L-bracket corners, accent border)
- `stats-bar` (segmented cells, glow on numbers)
- `numbers-grid` (1px border cells, `--surface` bg)
- `chip` / `stack` (mono tech-stack tags)
- `screenshot-card` (panel with corner brackets)
- `section-tag` (`// LABEL` via `::before`)
- `code-block`
- `cards-grid`
- `layers`
- `comparison-table`
- Mermaid integration (dark-themed, matching HUD tokens)

**h2t-mono — components to restore:**
- `comparison-table` (feature matrix, checkmarks)
- `two-column` (side-by-side split layout)

**Delivery:** sources dossier → grammar extraction → DESIGN.md update → components implementation → profile-specific recipe → visual gate against reference screenshot.

---

### R2 — Overlay System

Restore the visual background layer system. These must be injected per-profile, not shared.

| Layer | Target Profiles |
|-------|----------------|
| Grid background (CSS repeating gradient) | h2t-graphs, h2t-pfad |
| Dot-field animation (Canvas2D, particle network) | h2t-graphs (copy from h2t-pfad `fx/background.js`, adapt accent colors) |
| Corner marks (4 L-shaped viewport edge marks) | h2t-pfad |
| Coordinate labels (N/E/version/date fixed at corners) | h2t-pfad |
| Cursor reticle (JS lerp-following crosshair) | h2t-pfad (optional in landing context) |

Scanlines overlay is already present in h2t-terminal `tokens.css::after` — no action needed.

---

### R3 — Follow-up Profiles (h2t-pfad, h2t-terminal, h2t-editorial)

After R1 + R2 establish the pattern, apply the same extraction pipeline to the remaining profiles. These are recovery targets, not first-slice.

**h2t-pfad** — highest complexity (most profile-specific components):
- `pfad-card` (bg-card surface, `:: LABEL` prefix, red sweep hover animation)
- `pfad-tag` (4-corner bracket, expand-on-hover, active fills edge)
- `section-tag` (already on h2t-graphs)
- `chip` / `stack`

**h2t-terminal** — primarily CSS effects:
- `code-block` (styled display)
- `cards-grid` (terminal-themed)
- `layers` (steps list)
- `fade-up` + `slide-in` animations

**h2t-editorial** — typography-driven:
- `quote` / `pull-quote` (left-border accent)
- `cards-grid` (editorial variant)
- `slide-in` animation

---

### R4 — Visual Gate

For each recovered profile:

1. Build local page using profile recipe
2. Capture desktop screenshot (1440px) and mobile (375px)
3. Capture reference screenshot (live URL or `sources/screenshots/`)
4. Side-by-side checklist: for each documented component, verify it is present and structurally matches source
5. Fail if: only colors/fonts match but structural motifs (brackets, overlays, chip tags, etc.) are absent

Gate is run by the agent, confirmed by human visual inspection. Agent cannot self-pass the gate.

---

### R5 — Semver Confirmation

v1.2.0 is NOT live-confirmed. Version bump decision:

- Patch increments during R1–R4 work: allowed
- Next minor bump: only after human visual confirmation of R4 gate across all recovered profiles
- Exact version tag (1.2.0 re-use or 1.3.0) must be decided at confirmation time based on git/publish state — do not assume re-use is safe

---

## 6. Profile Extraction Pipeline

This pipeline applies to both legacy recovery and new style extraction. The source type differs; the process is the same.

### Step 1: Source Intake

- Identify: live URL, reference screenshots, legacy skill SKILL.md, existing HTML/CSS, DESIGN.md
- Commit to `sources/references.yaml` and `sources/screenshots/`
- **Gate:** no profile changes until sources are committed

### Step 2: Visual Grammar Extraction

Extract and document in `DESIGN.md`:

- **Typography:** font families, weights, scale, line-height, any restrictions
- **Color system:** bg, text, dim, accent, glow, border, surface — all named tokens
- **Layout:** grid system, density, max-widths, section rhythm, spacing scale
- **Motifs:** brackets, scanlines, chips, cursor, overlays, glow, cards, tags
- **Component archetypes:** hero, nav, cards, stats, quote, code, table, diagrams — catalog from source

### Step 3: Token Contract

Before writing any CSS, declare in DESIGN.md:

- Canonical tokens (new or existing)
- Legacy aliases (if migrating from token rename)
- Forbidden hardcodes (colors that must use tokens)
- Font loading requirements
- Profile overlay flags (which fx/ layers are active)
- Required profile-specific components (cannot be substituted with shared)
- Explicitly missing patterns (from source but not yet implemented — backlog)
- Shared vs override decision per component

### Step 4: Implementation

- Update `profile.yaml` (web fonts, fx flags)
- Create/update `tokens.css` (non-color tokens) and `palettes/default.css` (colors)
- Implement profile-specific components in `profiles/<name>/components/`
- Write profile-specific `recipe.yaml` that exercises the visual grammar
- Do not use generic recipe for fidelity validation

### Step 5: Fidelity Validation

Run R4 gate (see above). Cannot be skipped or self-passed.

### Step 6: Promotion Gate

- Patch version during iteration
- Minor only after human visual confirmation
- Version decision made at confirmation time

---

## 7. Acceptance Criteria

### R1 Complete (h2t-graphs + h2t-mono)

- [ ] h2t-graphs: all R1 components present and visually match `graphs.lichtpfadstudio.com`
- [ ] h2t-mono: comparison-table and two-column match `specdesigner.netlify.app`
- [ ] Both profiles have `sources/` dossier committed
- [ ] Both profiles have a profile-specific recipe that exercises ≥1 profile-specific component
- [ ] Visual gate R4 passes for h2t-graphs and h2t-mono (human-confirmed)

R1 is complete and shippable independently of R3 profiles.

### Full Recovery Complete (all profiles)

All R1 criteria above, plus:

- [ ] h2t-pfad: overlay system + pfad-card/pfad-tag restored
- [ ] h2t-terminal: code-block, cards-grid, animations restored
- [ ] h2t-editorial: quote/pull-quote, slide-in restored
- [ ] All profiles have `sources/` dossiers committed
- [ ] All profiles have profile-specific recipes
- [ ] Visual gate R4 passes for all profiles (human-confirmed)
- [ ] Version bumped only after full R4 confirmation
