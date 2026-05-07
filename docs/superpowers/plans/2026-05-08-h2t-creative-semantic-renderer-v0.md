# h2t-creative semantic renderer v0 — implementation plan

**Date:** 2026-05-08
**Branch:** `codex/h2t-creative-semantic-renderer-v0`
**Worktree:** `C:/dev/h2t-skills-semantic-v0`
**Status:** APPROVED 2026-05-08 by human, with two added guardrails (§1.1) and recorded decisions P-D1–P-D5 (§10).

**Issues:** to be filed under `lichtpfad/h2t-skills` once plan is acked
(`creative: [v0] Add semantic block renderer for landings` —
implementation tracker).

---

## 0. Inputs

This plan assumes the following are settled (already on branch):

- `docs/superpowers/specs/2026-05-08-h2t-creative-semantic-rendering-architecture.md` — architecture decision record. v0 scope is §10. The plan implements §10 only; §11 extension protocol, §6 asset model, §7 complex visuals are read-only references for v0.
- `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-rhythm-spec.md` (lives on `codex/r2b-editorial-landing` worktree, NOT cherry-picked here yet — see §3.2). Provides editorial-specific composition rules + research-backed v0 block standard.

Negative evidence (do NOT continue from):

- `codex/r2b-editorial-landing` branch — failed #88 implementation. `dist/r2b-h2t-editorial-landing-modular/` capture is what THIS plan must outperform. Treated as reference for "what not to do", not as starting point.

---

## 1. Goals

1. Implement the smallest possible semantic renderer that satisfies architecture spec §10 v0 scope.
2. Preserve backward compatibility with all existing component-based recipes (`sections:` format) — no profile breaks.
3. Ship `h2t-editorial` landing pilot as the first migrated recipe (semantic `blocks:` format), per architecture spec §13.
4. Land Agent Visual QA gates BEFORE any human review claim.
5. Migrate the recovered primitives + tokens from the failed #88 branch WITHOUT migrating the failed recipe / build / screenshots.

Non-goals:

- Custom-JS injection in recipes, user-authored templates, page-builder UI (architecture §10 out-of-scope).
- Migrating non-editorial profiles (graphs / mono / pfad / terminal) — deferred per architecture §12.
- Replacing assembler.py wholesale. Renderer v0 BRANCHES inside the existing `assemble_landing` entry point; `_build_section_html` / `_build_profile_css` paths stay live for legacy recipes.

## 1.1 Hard guardrails (added at approval, 2026-05-08)

Two rules that override ANY slice that appears to weaken them:

### G-A — Negative-evidence rule (failed #88 artefacts)

The failed primitive-showcase recipe + Batch C / post-Intent-Reset
screenshots + the `dist/r2b-h2t-editorial-landing-{system-b-validation,modular}/`
build outputs from the `codex/r2b-editorial-landing` branch are
**negative evidence ONLY**. They are referenced from this plan
(§3.2 file map) and from the architecture spec §13 as "what failed
and why", and that is the only legitimate role they have on this
branch.

Concretely forbidden:

- Cherry-picking the failed `recipe-landing.yaml` into this branch.
- Copying any of the four PNG captures (`{desktop,mobile}_2026050{7,8}_*.png`) into this worktree's `docs/visual-regression/` tree as if they were valid artefacts.
- Citing those captures inside parity-notes.md as "the previous build looked like X, so we keep that" — they are anti-references, not references.
- Carrying the "system-b-validation" or "h2t-editorial-landing-system-b-modular" path slugs forward in any new recipe / build / capture path. New work uses the v0 slugs (`dist/h2t-editorial-landing-v0/`, `docs/visual-regression/2026-05-08-semantic-v0/`).

If a slice's RED tests would only pass by re-introducing failed
artefacts as positive evidence, the slice is wrong, not the rule.

### G-B — Backward-compat is first-class

Semantic renderer v0 must NOT delete, deprecate or weaken legacy
component-recipe support (`sections:` + per-component manifest format).
Legacy recipes remain **first-class** outputs of the assembler until
each one is individually migrated to the semantic format on its own
slice.

Concretely:

- The `sections:` parser path inside `assemble_landing` stays alive (architecture §3, §12; this plan §3.3).
- `_build_section_html`, `_build_profile_css`, `_resolve_component_dir` are NOT renamed, NOT moved, NOT modified except by additive changes that the legacy path does not observe.
- T9 byte-identity regression (§4 T9) is the gate. Any legacy recipe that produces a different `dist/` byte sequence after v0 lands fails the slice.
- Profile-level CLAUDE.md / DESIGN.md / SKILL.md docs that describe legacy recipes stay valid until the matching profile migrates. No bulk doc rewrites.
- The legacy SKILL `plugins/h2t-creative/skills/landing/SKILL.md` is NOT replaced in v0. A separate skill (or an additive section) for the semantic format is a follow-up, not part of this plan.

If a slice claims it has to delete legacy code "to make the new path
clean", the slice is wrong, not the rule.

---

## 2. T0 — Caller inventory (mandatory per legacy-fidelity skill)

Before any signature change to `assemble_landing` or `_build_section_html`:

```
T0.1  grep -rn "assemble_landing\|assemble_deck\|main_assemble" plugins/ scripts/ tests/
T0.2  grep -rn "_build_section_html\|_build_profile_css\|_resolve_component_dir" plugins/ tests/
T0.3  list every CLI invocation in plugins/h2t-creative/skills/landing/SKILL.md
T0.4  list every recipe under profiles/<*>/validation/ — these are the live legacy users
```

T0 deliverable: a short audit row in the plan's progress section listing
each caller + its expected backward-compat outcome (preserved /
migrated). Without T0 we cannot guarantee non-regression.

T0 is ONE batch with the human. No code yet.

---

## 3. File map

### 3.1 New files (plan land)

```
plugins/h2t-creative/
├── renderer/                                 # new package
│   ├── __init__.py
│   ├── semantic_parser.py                    # T1: parse `blocks:` format
│   ├── skin_loader.py                        # T2: load profiles/<p>/skins/<format>.yaml
│   ├── field_mapper.py                       # T3: role → component fields
│   ├── asset_validator.py                    # T5: image/video/scripted policy
│   └── adapter.py                            # T4: branch into legacy or semantic path
├── profiles/h2t-editorial/skins/
│   └── landing.yaml                          # T7: editorial role → primitive map
└── tests/
    ├── test_semantic_parser.py               # T1
    ├── test_skin_loader.py                   # T2
    ├── test_field_mapper.py                  # T3
    ├── test_assembler_semantic_branch.py     # T4
    ├── test_asset_validator.py               # T5
    ├── test_editorial_landing_pilot.py       # T8
    └── test_backward_compat_legacy_recipes.py # T9
```

### 3.2 Files migrated FROM r2b-landing branch (cherry-pick OR re-create)

Decision per artifact (D-prefix decisions, surfaced in §10):

| Artifact on r2b-landing | Action here | Rationale |
|---|---|---|
| `profiles/h2t-editorial/components/{tabs,page-header,section-reset,card-grid,stats,comparison-table,flow,editorial-cta,mmap,pos-grid}/` | **Cherry-pick** the relevant component-creation commits OR re-extract from goldens. Pick whichever is cleaner per T6. | Recovered primitives are valid even though the failed recipe was not. They satisfy architecture §13 step 1 ("keep extracted System B-Landing tokens and primitives"). |
| `profiles/h2t-editorial/components/{decomposition-table,prohibition-table,wave-block,comp-box,disc,meta-box,tags}/` | **Skip** for v0 (per architecture §13 + composition spec §3 — appendix-only primitives). | Not needed by the seven semantic blocks; defer until a slice that actually needs them. |
| `profiles/h2t-editorial/tokens.css` (System B-Landing layer + global typography reset) | **Cherry-pick** the diff, NOT the whole file (preserve any origin/main edits). | Architecture §13 step 1. The global typography reset (h1/h2/h3) is required for primitives to render correctly — that fix was the hard-won output of Batch C.1. |
| `profiles/h2t-editorial/sources/landing-references.yaml` | **Cherry-pick.** | T0.5 source arbitration verdict. |
| `docs/superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md` | **Cherry-pick.** | Audit trail. |
| `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-design-system.md` | **Cherry-pick.** | T2 vocabulary extraction. |
| `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-composition-spec.md` | **Cherry-pick.** | Block inventory + Amendments A+B. |
| `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-rhythm-spec.md` | **Cherry-pick.** | Editorial rhythm + research-validated v0 standard (Appendix A). |
| `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-system-b-modular/` (Batch C frozen evidence) | **Skip.** Stays on r2b-landing branch as negative evidence. | Per user's instruction "never delete" + branch isolation policy. |
| `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-modular/` (post-Intent-Reset capture) | **Skip.** | Same. |
| `dist/r2b-h2t-editorial-landing-{system-b-validation,modular}/` | **Skip.** Build artefacts; never committed. | Standard practice. |
| `profiles/h2t-editorial/validation/recipe-landing.yaml` (failed primitive-showcase) | **Skip + replace.** Recipe v0 is written from scratch in T8 against the semantic spec. | Failed recipe contradicts architecture §1. |
| `plugins/h2t-creative/tests/test_r2b_legacy_fidelity_landing.py` | **Cherry-pick selectively.** Keep §LT-1..LT-7 (component contracts); drop §LT-8..LT-9 (recipe + Batch-C build contracts that are no longer the target). | Component-level contracts are real; recipe-level ones target the rejected recipe. |

### 3.3 Files NOT touched

- `assembler.py` legacy path: `_build_section_html`, `_build_profile_css`, `_resolve_component_dir` — unchanged. Renderer v0 ADDS a branch; it does not modify the legacy path.
- All other profiles (graphs / mono / pfad / terminal / default) — untouched.
- Deck form — untouched.

---

## 4. TDD slices

Each slice: write failing tests → confirm RED → implement → confirm GREEN → human review per slice (no batching) before merging into main.

### T1 — Semantic recipe parser (`renderer/semantic_parser.py`)

**Goal.** Parse a recipe with top-level `blocks:` list. Each block has `role`, `content`, optional `visual`, optional `presentation`.

**Tests RED first.**

- `test_semantic_parser_loads_blocks_list`
- `test_semantic_parser_rejects_recipe_with_both_blocks_and_sections`
- `test_semantic_parser_each_block_has_role_field`
- `test_semantic_parser_unknown_role_raises_descriptive_error`
- `test_semantic_parser_visual_block_has_role_and_content_id_or_omits`
- `test_semantic_parser_preserves_block_order`

**Schema.** See §5.

**Implementation.** Pure parsing — no rendering. Returns a typed
intermediate representation. ~80 LOC.

### T2 — Skin mapping loader (`renderer/skin_loader.py`)

**Goal.** Load `profiles/<profile>/skins/<format>.yaml` (e.g. `profiles/h2t-editorial/skins/landing.yaml`). Skin maps semantic role → component name + field-mapping rules.

**Tests RED first.**

- `test_skin_loader_loads_editorial_landing_skin`
- `test_skin_loader_rejects_skin_with_unknown_role`
- `test_skin_loader_rejects_skin_pointing_at_missing_component`
- `test_skin_loader_supports_per_role_field_mapping`
- `test_skin_loader_role_with_no_mapping_falls_back_to_default_skin`

**Schema.** See §6.

**Implementation.** YAML load + cross-check role names against the v0 block library + verify component dirs exist. ~60 LOC.

### T3 — Field-mapping engine (`renderer/field_mapper.py`)

**Goal.** Translate a semantic block's `content` dict into the component manifest's `fields`. Handles per-role mapping rules from the skin.

**Tests RED first.**

- `test_field_mapper_hero_to_page_header_fields`
- `test_field_mapper_proof_to_stats_three_kpis`
- `test_field_mapper_features_to_card_grid_with_g3_grid_class`
- `test_field_mapper_process_to_flow_steps_html`
- `test_field_mapper_comparison_to_comparison_table_thead_tbody`
- `test_field_mapper_evidence_to_section_title_body`
- `test_field_mapper_cta_to_editorial_cta_full_dom`
- `test_field_mapper_unknown_field_raises_at_block_position`

**Implementation.** Skin-driven dict transformation. ~120 LOC.

### T4 — Adapter / assembler integration (`renderer/adapter.py` + `assembler.py` patch)

**Goal.** `assemble_landing` branches: if recipe has `blocks:` → semantic path; if `sections:` → legacy path. Both produce identical output shape (`dist/<slug>/{index.html, profile.css, base.css}`).

**Tests RED first.**

- `test_assembler_semantic_recipe_routes_through_renderer`
- `test_assembler_legacy_recipe_unchanged_output_byte_identical_to_pre_v0_baseline`  (golden fixture)
- `test_assembler_recipe_with_neither_blocks_nor_sections_fails_loud`
- `test_assembler_recipe_with_both_fails_loud_per_T1`

**Implementation.** ~30 LOC patch on `assemble_landing` + ~80 LOC adapter. The adapter calls semantic_parser → skin_loader → field_mapper → reuses existing `_build_section_html` per derived component section.

**Backward compat invariant.** Every existing landing recipe under
`profiles/<*>/validation/recipe.yaml` builds byte-identically to its
pre-v0 output. Encoded as a regression fixture in `test_backward_compat_legacy_recipes.py`.

### T5 — Asset validator (`renderer/asset_validator.py`)

**Goal.** Architecture §6 + rhythm-spec A.5: visual blocks declare `visual.role` + reference an asset; missing assets fail loud, no placeholders.

**Tests RED first.**

- `test_asset_validator_image_role_requires_existing_path`
- `test_asset_validator_video_role_requires_poster`
- `test_asset_validator_scripted_role_requires_static_fallback`
- `test_asset_validator_missing_asset_fails_loud_with_block_position`

**Implementation.** Pure validation, runs at parse time before any rendering. ~50 LOC.

For #88 pilot: NO visual assets. Every block has `visual:` absent or `visual: { role: omit }`. Asset validator returns OK noop.

### T6 — Migrate recovered primitives + tokens

Per §3.2 file map. Detail:

- T6.1  Cherry-pick or re-create the seven needed components: `tabs`, `page-header`, `section` (RESET), `card-grid`, `stats`, `comparison-table`, `flow`, `editorial-cta`.
- T6.2  Cherry-pick token amendments (`tokens.css` System B-Landing layer + global h1/h2/h3 reset).
- T6.3  Cherry-pick source dossier + arbitration spec + design-system + composition-spec + rhythm-spec.
- T6.4  Cherry-pick `test_r2b_legacy_fidelity_landing.py` §LT-1..LT-7 (drop LT-8/LT-9).
- T6.5  Re-run those tests → all green at the new HEAD.

Two important constraints:

- The seven components migrate AS-IS; no behavioural changes here.
- The `comparison-table` component must SHIP with `.bt-cards` mobile dual-representation in this slice (per rhythm spec A.4) since #88 pilot uses it. If the existing component doesn't have it, T6.6 = add `.bt-cards` + `@media (max-width:480px)` rule.

### T7 — Editorial landing skin (`profiles/h2t-editorial/skins/landing.yaml`)

**Goal.** The role-to-primitive map for the editorial landing form. Per architecture §13 step 4 + research recommendations D5(a) tight regime.

**Tests RED first.**

- `test_editorial_skin_maps_hero_to_page_header`
- `test_editorial_skin_maps_proof_to_stats`
- `test_editorial_skin_maps_features_to_card_grid`
- `test_editorial_skin_maps_process_to_flow`
- `test_editorial_skin_maps_comparison_to_comparison_table_with_mobile_cards_flag`
- `test_editorial_skin_maps_evidence_to_section`
- `test_editorial_skin_maps_cta_to_editorial_cta`
- `test_editorial_skin_marks_unsupported_roles_explicitly`  (`solution`, `faq`, `testimonials`, `pricing`, `gallery`, `video`, `navigation` → declared `unsupported_in_v0` in skin)

### T8 — Editorial pilot recipe (`profiles/h2t-editorial/validation/recipe.yaml`)

**Goal.** First semantic-format landing recipe. Per rhythm spec §6 D-recommendations + §A.9 D5(a) tight regime: 7 sections (hero, proof, problem-via-hero-lede, features, process, evidence, cta).

The recipe filename is `recipe.yaml` (NOT `recipe-landing.yaml` from the failed #88 — fresh slug, fresh history).

**Tests RED first.**

- `test_editorial_pilot_recipe_uses_semantic_blocks_format`
- `test_editorial_pilot_recipe_has_seven_blocks`  (D5a tight)
- `test_editorial_pilot_recipe_includes_all_required_v0_roles`
- `test_editorial_pilot_recipe_excludes_solution_faq_pricing_testimonials`  (deferred per D5a)
- `test_editorial_pilot_recipe_no_synthetic_copy`
- `test_editorial_pilot_recipe_declares_no_visual_assets`  (consistent with T5 noop)
- `test_editorial_pilot_recipe_one_dense_block_max`

**Build & structural gate.**

- `test_editorial_pilot_build_index_html_within_loc_budget`  (≤ 250 LOC HTML)
- `test_editorial_pilot_build_no_appendix_only_classes`
- `test_editorial_pilot_build_no_image_tags`
- `test_editorial_pilot_build_carries_seven_blocks_in_order`

### T9 — Backward-compat regression suite (`test_backward_compat_legacy_recipes.py`)

**Goal.** Lock byte-identity of every existing legacy recipe build against a pre-v0 fixture.

**Method.** Before T4 lands, capture `dist/` snapshots for all existing landing recipes (h2t-graphs, h2t-mono, h2t-default, etc. that have one). Store hashed manifest in `tests/fixtures/legacy_landing_baselines.json`. After T4: re-build each, compare to fixture.

**Tests.**

- `test_legacy_recipe_<profile>_<form>_byte_identical_to_baseline` — parametrised over each existing recipe.

If a legacy recipe diff appears, T4 has a bug; T1-T3 must not touch the legacy path.

### T10 — Visual capture + Agent Visual QA

Per architecture §14 + legacy-fidelity skill discipline.

- T10.1  Build editorial pilot to a fresh `dist/h2t-editorial-landing-v0/`.
- T10.2  Capture desktop (1440 × 900) + mobile (390 × 844).
- T10.3  **Agent Visual QA — mandatory before any human review.** Open every screenshot via `Read`. Score per block per viewport: PASS / ISSUE / BLOCKER + visible-problem one-liner. Notes go into `docs/visual-regression/<date>-semantic-v0/parity-notes.md`.
- T10.4  Mobile usability gate (rhythm spec A.3): no horizontal overflow, no clipped text, comparison block renders cards.
- T10.5  Hand human the live URL + parity-notes. Stop until each gate is acked.

### T11 — Cleanup of rejected #88 artefacts

Per user's CLAUDE.md ("never delete without confirmation") and worktree-isolation policy:

- T11.1  `codex/r2b-editorial-landing` branch stays as negative evidence on the remote. NOT merged.
- T11.2  `r2b-landing` worktree on the local machine: keep until v0 lands; remove via `git worktree remove` only after explicit user confirmation.
- T11.3  In the v0 commit log, add a `chore(h2t-creative)` commit body noting that the rejected recipe + Batch C build artefacts live on `codex/r2b-editorial-landing` for archival reference.
- T11.4  Update plan §16 of the original modularization plan (lives on r2b-landing branch) with a back-pointer: "v0 plan supersedes this slice — see semantic-renderer-v0 plan." Done as a doc-only commit on r2b-landing if the user wants to keep that history accurate; SKIP if not.

---

## 5. Semantic recipe schema (T1 contract)

```yaml
type: landing                        # required, fixes routing
profile: h2t-editorial               # required, picks skin
palette: default                     # optional, defaults to "default"
title: "h2t-editorial — landing"

blocks:                              # required for semantic format
  - role: hero                       # required string from v0 block library
    content:                         # required map; shape per-role per skin
      headline: "..."
      lede: "..."
      meta: "..."
    visual:                          # optional
      role: omit                     # one of: omit | image | video | scripted | static
                                     # (architecture §6 + §7)
    presentation:                    # optional, profile-specific overrides
      density: tight                 # one of: tight | normal | spacious
                                     # (rhythm spec §A.2)
  - role: proof
    content:
      stats:
        - n: "16"
          l: "primitive components"
        # ...
  # ... etc
```

Validation rules (§T1 tests):

- `blocks` and `sections` must not both be present.
- Each block has `role` (string) + `content` (map).
- `role` must be in v0 block library (`hero`, `proof`, `features`, `process`, `comparison`, `evidence`, `cta`) OR a profile-specific extension declared in skin.
- Optional fields (`visual`, `presentation`) parsed if present, ignored if absent.
- Block order is preserved.

---

## 6. Skin mapping schema (T2 contract)

```yaml
# profiles/h2t-editorial/skins/landing.yaml
profile: h2t-editorial
format: landing
version: v0

roles:
  hero:
    component: page-header
    field_mapping:
      headline: headline
      meta: meta
    presentation_options:
      lede_attached: true            # fold lede into trailing paragraph in section wrapper

  proof:
    component: stats
    field_mapping:
      stat1_n: "stats[0].n"
      stat1_l: "stats[0].l"
      stat2_n: "stats[1].n"
      stat2_l: "stats[1].l"
      stat3_n: "stats[2].n"
      stat3_l: "stats[2].l"

  features:
    component: card-grid
    static_fields:
      grid_class: g3
    field_mapping:
      cards_html: "${render_cards(features)}"   # template helper, T3

  process:
    component: flow
    field_mapping:
      steps_html: "${render_flow_steps(steps)}"

  comparison:
    component: comparison-table
    field_mapping:
      thead_html: "${render_table_head(columns)}"
      tbody_html: "${render_table_body(rows)}"
    mobile_representation: cards     # selects .bt-cards path; CSS already in component

  evidence:
    component: section
    field_mapping:
      title: title
      body: body_html

  cta:
    component: editorial-cta
    field_mapping:
      label: label
      title: title
      body: body
      primary_label: primary_label
      primary_href: primary_href
      secondary_label: secondary_label
      secondary_href: secondary_href

unsupported_in_v0:
  - solution                         # D5a — fold into hero lede
  - faq                              # D8 — no objection cluster
  - testimonials
  - pricing
  - gallery
  - video
  - navigation                       # D10 — single-purpose landing
```

Field mapping syntax:

- Plain `key: key` — direct copy.
- `"${helper(arg)}"` — call a renderer helper. Helper registry is part of `field_mapper.py`. Helpers in v0: `render_cards`, `render_flow_steps`, `render_table_head`, `render_table_body`. Each one is small (~10–25 LOC) and tested in T3.

---

## 7. h2t-editorial landing pilot (T8 recipe shape)

Seven blocks per rhythm spec §A.9 D5(a) tight regime + D6/D7/D8/D9/D10 recommendations:

```yaml
type: landing
profile: h2t-editorial
palette: default
title: "h2t-editorial — landing"

blocks:
  - role: hero
    content:
      headline: "h2t-editorial — landing"
      lede: "Editorial-форма h2t-creative для длинных аналитических разворотов: appendix-отчётов, бенчмарков, исследовательских разборов."
      meta: "R2b · 2026-05-08"

  - role: proof
    content:
      stats:
        - n: "16"
          l: "primitive components"
        - n: "545+"
          l: "contract tests"
        - n: "0"
          l: "R1 / deck token leaks"

  - role: features
    content:
      features:
        - title: "Closed primitive vocabulary"
          body: "..."
        - title: "Layered token strategy"
          body: "..."
        - title: "Source-role discipline"
          body: "..."

  - role: process
    content:
      steps:
        - title: "Source arbitration"
          body: "T0.5 visual gate."
        - title: "Vocabulary extraction"
          body: "design-system §10."
        - title: "TDD slices"
          body: "Component contracts before code."
        - title: "Composition spec"
          body: "Block-inventory + rhythm contract before recipe."

  - role: comparison
    content:
      columns: ["Profile", "Form", "Body type", "Density"]
      rows:
        - { highlight: true, cells: ["h2t-editorial", "deck + landing", "system-ui sans 14 px", "Editorial"] }
        - { cells: ["h2t-terminal", "deck", "JetBrains Mono", "Terminal"] }
        - { cells: ["h2t-graphs", "landing", "Inter", "Marketing"] }
        - { cells: ["h2t-mono", "landing", "Single mono", "Sparse"] }

  - role: evidence
    content:
      title: "Audit trail"
      body_html: "<p>...links to composition-spec / rhythm-spec / design-system / arbitration ...</p>"

  - role: cta
    content:
      label: "Next"
      title: "Смотреть deck-форму"
      body: "Парная deck-форма h2t-editorial доставлена через PR #102."
      primary_label: "Открыть PR #102 →"
      primary_href: "https://github.com/lichtpfad/h2t-skills/pull/102"
      secondary_label: "Browse appendices"
      secondary_href: "..."
```

Seven blocks. One dense (comparison). No images. No primitive showcase.

---

## 8. Visual QA gates

Two independent gates per legacy-fidelity skill. Both mandatory.

### Gate A — Desktop fidelity (1440 × 900)

- Hero h1 = 28 px Playfair, gold, no clipping, lede ≤ 30 words.
- Proof strip = 3 stats horizontal, gold numbers, muted labels.
- Features row = 3 cards, equal width, ≤ 35 words each.
- Process = vertical numbered flow with 4 steps, sep lines visible.
- Comparison = `.bt` table, ≤ 4 rows, single `.rejuve` highlight row.
- Evidence = small `.section`, h2 + audit links, no h2-as-major-heading mistake.
- CTA = `editorial-cta` card with gold primary text-link, secondary muted.

### Gate B — Mobile usability (390 × 844)

- No horizontal overflow on ANY block.
- Comparison renders as `.bt-cards` (NOT scrolled `.bt`).
- Hero lede stacks under headline; readable at 14 px.
- Stats stack 2×2 OR 1×3 — both acceptable.
- Cards stack 1-up.
- Flow stays vertical (no representation change).
- CTA full-width readable; no sticky (D9 = false).

### Agent Visual QA discipline

- Open every screenshot file with the `Read` tool BEFORE handing to human.
- Per-block, per-viewport: write PASS / ISSUE / BLOCKER + a one-line visible-problem statement.
- Notes file: `docs/visual-regression/2026-05-08-semantic-v0/parity-notes.md`.
- "All N PNGs exist with non-zero size" is NOT visual QA. Counting files = pressure-scenario #1 of legacy-fidelity skill.

---

## 9. Commit / versioning strategy

### 9.1 Commit shape per slice

| Slice | Commit |
|---|---|
| T0 | `chore(h2t-creative): T0 caller inventory for semantic renderer` (no code, just plan-progress note) |
| T1 | `feat(h2t-creative): semantic recipe parser` |
| T2 | `feat(h2t-creative): skin mapping loader` |
| T3 | `feat(h2t-creative): field mapping engine` |
| T4 | `feat(h2t-creative): assembler semantic-vs-legacy branch` |
| T5 | `feat(h2t-creative): asset validator` |
| T6 | `feat(h2t-creative): migrate System B-Landing primitives + tokens from #88 work` (squashed) |
| T7 | `feat(h2t-creative): editorial landing skin` |
| T8 | `feat(h2t-creative): editorial landing pilot recipe` |
| T9 | `test(h2t-creative): backward-compat regression for legacy recipes` |
| T10 | `docs(h2t-creative): pilot visual QA notes` |
| T11 | `docs(h2t-creative): record rejected #88 artefacts as negative evidence` |

### 9.2 PR strategy

Single PR `creative: [v0] Add semantic block renderer for landings` carrying T1–T11. Per-slice commits inside, NOT squashed (preserves the TDD red→green trail). Architecture spec commits already on branch — included automatically.

### 9.3 Versioning

Per user's CLAUDE.md (semver):

- T1–T11 ship as patch bumps if any are needed mid-flight (none expected — single PR).
- After live verification of the editorial pilot, separate `chore(h2t-creative): bump version after semantic renderer v0 live verification` with a **minor** bump: current → next minor (TBD at time of bump). Run via `scripts/bump_plugin.py h2t-creative <next-minor>`.
- No version bump until human has opened the live pilot in a browser AND parity-notes are PASS at both gates.

---

## 10. Decisions surfaced by this plan (verdicts recorded 2026-05-08)

| ID | Decision | Verdict |
|---|---|---|
| **P-D1** | T6 method: cherry-pick component-creation commits from `codex/r2b-editorial-landing` OR re-extract primitives fresh from goldens? | **Cherry-pick.** Components were correct; only the recipe + composition were wrong. Re-extraction wastes work. |
| **P-D2** | T6.6 dual-representation for `comparison-table` (`.bt-cards` + `@media`): land in this slice OR drop `comparison` from the pilot? | **Ship dual-rep in this slice.** Pilot deliberately uses `comparison` to validate the dual-rep contract. If implementation reveals excessive cost, surface as a slice-mid amendment, not a default fallback. |
| **P-D3** | T9 baseline: capture per-recipe builds for all existing landings, or scope only to `h2t-graphs` + `h2t-mono` (the active landing profiles)? | **Active only — graphs + mono.** terminal has no landing recipe; pfad / default same. Reduces fixture surface. |
| **P-D4** | T11 cleanup: leave `r2b-landing` worktree intact OR remove after v0 lands? | **Leave.** Keep until v0 is live-verified, then user removes manually. Plan does not auto-remove worktrees. |
| **P-D5** | Filename for the editorial pilot: `recipe.yaml` (canonical) OR `recipe-landing.yaml` (descriptive)? | **`recipe.yaml`.** Matches `h2t-graphs / h2t-mono` precedent and establishes the new semantic-recipe convention. The failed `recipe-landing.yaml` slug stays only on `codex/r2b-editorial-landing` as negative evidence. |

---

## 11. Acceptance for plan approval

This plan is accepted when the human acks:

1. T0 caller inventory will run before any signature change.
2. §3.2 file-map cherry-pick scope (P-D1 default OR amended).
3. §5 semantic recipe schema OR amendments.
4. §6 skin mapping schema OR amendments.
5. §8 two-gate visual QA discipline (mandatory Agent QA before human).
6. §9 PR + versioning strategy.
7. P-D2 / P-D3 / P-D4 / P-D5 verdicts.

After ack, T1 starts on this branch, this worktree.

---

## 12. References

- Architecture spec: `docs/superpowers/specs/2026-05-08-h2t-creative-semantic-rendering-architecture.md` (this branch).
- Rhythm spec + research-validated v0 standard: `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-rhythm-spec.md` (`codex/r2b-editorial-landing`; cherry-picked here in T6.3).
- Source arbitration verdict: `docs/superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md` (`codex/r2b-editorial-landing`; cherry-picked in T6.3).
- Composition spec (block inventory + Amendments A+B): `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-composition-spec.md` (`codex/r2b-editorial-landing`; cherry-picked in T6.3).
- Legacy-fidelity skill (TDD discipline + pressure scenarios): `plugins/h2t-creative/skills/legacy-fidelity/`.
- R2a deck reference exemplar (process-precedent): `lichtpfad/h2t-skills` PR #95.
- R2b deck merged delivery (System B brand baseline): `lichtpfad/h2t-skills` PR #102.
- Failed #88 negative evidence (DO NOT continue): `codex/r2b-editorial-landing` branch HEAD.
