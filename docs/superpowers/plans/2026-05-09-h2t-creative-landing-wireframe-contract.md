---
title: "Universal Landing Wireframe Contract Implementation Plan"
status: "draft"
date: "2026-05-09"
milestone: ""
---
# Universal Landing Wireframe Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Specify a landing-specific wireframe artefact format so any author (human or agent) can produce, review, and approve a low-fidelity landing wireframe before recipe implementation begins, closing the abstraction gap left between `WIREFRAME_GATE.md` (generic gate) and recipe authoring.

**Architecture:** Pure docs slice. Two new files under existing canonical paths plus three small cross-link patches into already-merged docs. No runtime, no CSS, no recipe, no Python, no tests of code paths. The landing contract is the format-specialised instantiation of the generic wireframe artefact required by `WIREFRAME_GATE.md`; sibling format-specific contracts (deck, report, …) can be added later by analogy.

**Tech Stack:** Markdown only. No tools beyond a text editor, `git`, `gh`, and a small Python check for markdown link resolution.

## Shell Convention

All shell snippets in this plan use POSIX syntax (`grep`, `tail`, `2>&1 | tail`, `$(cat <<'EOF' ... EOF)`, `/c/Users/...` paths). Run them via the Bash tool / Git Bash. The host platform is Windows; PowerShell is the default interactive shell, but Bash is available alongside per the project convention used throughout the session that produced this plan.

If executing in PowerShell directly, translate the snippets:
- pipe-tail: `... 2>&1 | Select-Object -Last 3` instead of `2>&1 | tail -3`
- grep negation: `... | Select-String -NotMatch "^docs/"` instead of `| grep -vE "^docs/"`
- here-doc body: pass via `--body-file <tempfile>` after writing the body to a temp file
- python path: `C:/Users/stani/.h2t/venv/Scripts/python.exe` (PowerShell understands forward slashes; `/c/Users/...` is Bash-only)

The Python interpreter is the same binary in either shell.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` | **NEW** | The contract. Specifies every field a landing wireframe must define, with options, examples, and constraints. Living under `architecture/` because it is canonical structure, not a process step. |
| `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md` | **NEW** | Review-side checklist. Pass/fail items mapped to CONTRACT sections. Used by the human approver per `WIREFRAME_GATE.md` § Human Approval. Living under `protocols/` because it is process. |
| `docs/protocols/h2t-creative/WIREFRAME_GATE.md` | MODIFY | Add forward-link to the new CONTRACT and REVIEW under "Required Wireframe Artifact" so the gate doc explicitly hands off to the format-specialised contract. |
| `docs/architecture/h2t-creative/ROOT_GUIDE.md` | MODIFY | Add the two new docs to the "Canonical Architecture Docs" / "Required Reading By Task" lists so authors find them. |
| `docs/architecture/h2t-creative/COMPOSITION_RULES.md` | MODIFY | Add a single back-reference: the landing density rule (5-8 primary sections, ≤ 2 dense) is the constraint surface that the CONTRACT operationalises. |
| `docs/wireframes/README.md` | **NEW** | Registers the new `docs/wireframes/` canonical root where approved wireframe artefacts live. One file per page at `<YYYY-MM-DD>-<profile>-<page-slug>.md`. Without this anchor the new root reference would not resolve. |

No other files touched. No `plugins/`, no `.css`, no `.py`, no `.yaml` outside this set.

---

## Task 1: Worktree setup and plan commit

**Files:**
- Use: `C:/dev/h2t-skills-wireframe-contract` (worktree from `origin/main` at `b68644d`)
- Create: `docs/superpowers/plans/2026-05-09-h2t-creative-landing-wireframe-contract.md` (this plan)

- [ ] **Step 1: Verify worktree is in place**

```bash
git -C C:/dev/h2t-skills-wireframe-contract log --oneline -1
```
Expected: `b68644d Merge pull request #128 ...`

If absent, create it:
```bash
git -C C:/dev/h2t-skills worktree add -b docs/h2t-creative-landing-wireframe-contract C:/dev/h2t-skills-wireframe-contract origin/main
```

- [ ] **Step 2: Commit the plan as branch's first commit**

```bash
cd C:/dev/h2t-skills-wireframe-contract
git add docs/superpowers/plans/2026-05-09-h2t-creative-landing-wireframe-contract.md
git commit -m "docs(h2t-creative): plan universal landing wireframe contract

Plan for the landing-specific wireframe artefact format that
operationalises WIREFRAME_GATE for landing pages.

Pure docs slice: two new docs (LANDING_WIREFRAME_CONTRACT.md +
LANDING_WIREFRAME_REVIEW.md) plus three cross-link patches.
No runtime, no CSS, no recipes, no tests."
```

---

## Task 2: Skeleton CONTRACT file with all section headings

**Files:**
- Create: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Write the skeleton with empty sections**

```markdown
# h2t-creative Landing Wireframe Contract

## Purpose

<!-- §3 fills this in -->

## When This Contract Applies

<!-- §4 fills this in -->

## Inputs

<!-- §5 fills this in -->

## Required Wireframe Artefact

<!-- §6 fills this in -->

### Mode Declaration

### Block Sequence

### Per-Block Intent

### Per-Block Density Classification

### Desktop Layout Sketch

### Mobile Representation Per Block

### Source Classification Per Block

### Density Budget

### Asset Inventory

### Negative Examples

## Format Options

<!-- §7 fills this in -->

## Forbidden In A Wireframe

<!-- §8 fills this in -->

## Approval Criteria

<!-- §9 fills this in -->

## Outputs After Approval

<!-- §10 fills this in -->

## Worked Examples

<!-- §11 fills this in -->

### Positive Example — Editorial Landing

### Negative Example — Primitive Showcase (Why It Fails)

## Cross-References
```

- [ ] **Step 2: Verify section order matches WIREFRAME_GATE structure**

The Required Wireframe Artefact subsections must collectively cover every bullet in `docs/protocols/h2t-creative/WIREFRAME_GATE.md` § Required Wireframe Artifact:

| WIREFRAME_GATE bullet | CONTRACT subsection |
|---|---|
| Format and canvas/viewport | Mode Declaration + Desktop Layout Sketch |
| Section/slide/frame order | Block Sequence |
| Intent of each block | Per-Block Intent |
| Desktop layout | Desktop Layout Sketch |
| Mobile layout | Mobile Representation Per Block |
| Grid and max-width decisions | Desktop Layout Sketch |
| Vertical rhythm expectations | Per-Block Density Classification |
| Dense sections and density budget | Density Budget + Per-Block Density Classification |
| Table/gallery/video/interactive placement | Block Sequence + Per-Block Intent |
| CTA placement | Block Sequence (cta role) |
| Required assets and missing assets | Asset Inventory |
| Explicit "not this" negative examples | Negative Examples |

Every WIREFRAME_GATE bullet maps to a CONTRACT subsection — no gaps.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): add landing wireframe contract skeleton"
```

---

## Task 3: §Purpose, §When This Contract Applies, §Inputs

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Fill in `## Purpose`**

```markdown
## Purpose

This contract specifies the format and contents of the wireframe artefact a landing-page author must produce before any recipe, skin, or component implementation begins. It is the landing-specialised instantiation of the generic gate defined in `docs/protocols/h2t-creative/WIREFRAME_GATE.md`.

The contract closes a concrete gap surfaced by issue #88 / branch `codex/r2b-editorial-landing` (archived under `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/`): without a format-specific wireframe shape, "produce a wireframe" devolves into "extract primitives", and the result is a renderer pass / design fail. The fields below are the minimum a human reviewer needs to make an informed approval decision.

The contract does not prescribe visual style — that is the profile `DESIGN.md` and skin's job (see `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Profile / Skin Layer). The contract prescribes structure, intent, density, and responsive behaviour. A single approved wireframe drives recipe authoring, visual QA, and human review.
```

- [ ] **Step 2: Fill in `## When This Contract Applies`**

```markdown
## When This Contract Applies

Mandatory for any output that produces a landing page, including:

- Standalone product, service, or editorial landings.
- Microsites that are functionally one or two landing pages.
- Hub pages and content indexes that share the landing structure (hero + sections + CTA).
- "Landing-companion" pages adjacent to a deck or report (e.g. download / signup adjacent to a publication).

Not required for:

- Decks and presentations (use the deck wireframe contract — to be added by analogy).
- Reports and appendices (use the report wireframe contract — likewise).
- Carousels, interactive explainers (likewise).

If the format is unclear, default to the strictest applicable contract.
```

- [ ] **Step 3: Fill in `## Inputs`**

```markdown
## Inputs

Before drafting a wireframe, the author collects:

- **Intent statement** — one or two sentences naming the landing's primary purpose: explain, sell, teach, document, compare, pitch, or publish. This drives mode selection and CTA shape.
- **Audience** — who the page is for. Constrains density, technical depth, evidence weight.
- **Mode** — one of the canonical landing modes from `docs/architecture/h2t-creative/CORE_SYSTEM.md` and the semantic parser `KNOWN_MODES` set: `product`, `service`, `editorial`, `report`, `portfolio`, `deck-companion`. Mode pre-selects sensible block-sequence defaults.
- **Profile / style target** — which `profiles/<name>/` design system applies. The profile constrains palette, typography, density tolerance, and primitive availability. The author reads the profile's `DESIGN.md` Stitch frontmatter and Restrictions before choosing block density.
- **Source dossier** — the visual / textual / data sources the page draws from, each classified per `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Evidence Classification: target, primitive source, or negative.
- **Required CTA(s)** — what the page must persuade the reader to do. Determines CTA placement and copy intent.
- **Known constraints** — fixed deadlines, mandatory legal copy, brand restrictions, asset availability gaps.
```

- [ ] **Step 4: Verify and commit**

```bash
git diff docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — purpose / when / inputs"
```

---

## Task 4: §Required Wireframe Artefact (the heart)

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

This task fills the largest section. It is split into the ten subsections declared in the skeleton.

- [ ] **Step 1: Write the section preamble**

Just below `## Required Wireframe Artefact`, before the first `###`:

```markdown
The wireframe artefact is one document containing all of the following fields. Missing fields are a review failure. Empty fields are explicit `(none)` rather than absent.
```

- [ ] **Step 2: Fill `### Mode Declaration`**

```markdown
### Mode Declaration

State the mode from the `KNOWN_MODES` vocabulary. Pick one — the modes are mutually exclusive at this layer:

| Mode | Primary intent | Typical sequence |
|---|---|---|
| `product` | Sell or explain a product | hero, proof, features, process, comparison, evidence, cta |
| `service` | Persuade to engage a service | hero, proof, problem, solution, process, evidence, cta |
| `editorial` | Publish a long-form argument or release | hero, proof, features (or evidence-cards), comparison, evidence, cta |
| `report` | Surface findings of an analysis | hero (page-header), proof, evidence, comparison, cta-as-link |
| `portfolio` | Showcase work or precedent | hero, gallery, case_study, evidence, cta |
| `deck-companion` | Resource adjacent to a deck/talk | hero, proof, evidence, cta (typically download / signup) |

The "Typical sequence" is a starting hint, not a constraint. Real wireframes deviate when intent demands.
```

- [ ] **Step 3: Fill `### Block Sequence`**

```markdown
### Block Sequence

A numbered list of semantic block roles in the order they appear from top to bottom on desktop. Use the universal vocabulary from `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Semantic Layer (also encoded in the parser's `KNOWN_BLOCK_TYPES` set):

`nav`, `hero`, `proof`, `problem`, `solution`, `features`, `process`, `comparison`, `gallery`, `video`, `case_study`, `testimonials`, `pricing`, `faq`, `evidence`, `cta`, `footer`

Constraints (see also § Density Budget):

- 5–8 entries total per `COMPOSITION_RULES` density rules. Below 5, the page is rarely a landing; above 8, density discipline collapses.
- The first block after `nav` (or first overall if no nav) MUST be `hero`. The first screen has to communicate intent.
- At least one of `cta` or a CTA-equivalent block (e.g. `cta`-styled `evidence`) must appear. A landing without a CTA is a content page.
- `footer` is optional — many landings ship without one if the surrounding site provides chrome.

Format example:
```

````markdown
1. `hero`           — first screen
2. `proof`
3. `features`
4. `process`
5. `comparison`
6. `evidence`
7. `cta`
````

- [ ] **Step 4: Fill `### Per-Block Intent`**

```markdown
### Per-Block Intent

For each block in the sequence, one or two sentences naming what that specific block must communicate to the specific audience. Not copy. Intent.

Bad: "Stats with three numbers about the product."
Good: "Establish credibility before features land — show that the product has been used at scale (count, retention, partner). Audience is procurement-focused, so prefer institutional metrics over user-testimonials feel."

Per-block intent is the test the recipe author writes against and the human reviewer measures the rendered page against in `VISUAL_QA.md` § Gate A.
```

- [ ] **Step 5: Fill `### Per-Block Density Classification`**

```markdown
### Per-Block Density Classification

Each block is one of: **dense**, **medium**, or **open**.

- **dense** — table-heavy, multi-column data, ≥ 4 cards per row, paragraphs > 3 lines. Comparison tables, deep evidence sections.
- **medium** — moderately structured: 3-card grids, stats blocks with labels, process steps, bordered CTAs.
- **open** — generous whitespace, single-column copy, single hero image, single headline + meta. Hero, single-card evidence, simple CTAs.

Density classification feeds the density budget below and the rhythm rule that dense sections must be followed by breathing room (`COMPOSITION_RULES` § Density Rules).
```

- [ ] **Step 6: Fill `### Desktop Layout Sketch`**

```markdown
### Desktop Layout Sketch

A low-fidelity representation of the desktop view. Acceptable formats (see § Format Options):

- ASCII column diagram
- Markdown table with one row per block listing `column count × role`
- Hand sketch image embedded by relative link

Required content of the sketch, regardless of format:

- **Content max-width** — typically 1100 px for editorial, 1200 px for product. Profile may constrain.
- **Column model per block** — single, two-up, three-up, four-up. Cards-per-row.
- **Block ordering** — must agree with § Block Sequence above.
- **Notes for non-rectangular blocks** — galleries, hero-with-media, full-bleed quotes — call out the divergence from the dominant grid.

The sketch does not commit to specific copy or specific colors. It commits to layout structure.
```

- [ ] **Step 7: Fill `### Mobile Representation Per Block`**

```markdown
### Mobile Representation Per Block

For each block, name its mobile representation explicitly. One of:

- **stack** — single column, contents flow top-to-bottom in source order.
- **collapse-to-1col** — a multi-column desktop block redraws as one column on mobile (cards, stats, features grids).
- **collapse-to-cards** — a desktop table redraws as stacked cards on mobile (the comparison-table dual-rep contract; rhythm spec § A.4).
- **hide** — block does not render below a stated breakpoint. Allowed only for non-essential nav, decorative dividers, or surplus chrome. Essential content must never `hide`.
- **media-fallback** — video, gallery, or interactive block uses a poster, static image, or text fallback on mobile.

Mobile is not passive resizing (`COMPOSITION_RULES` § Responsive Representation). Every multi-column desktop block needs an explicit mobile representation declared here.
```

- [ ] **Step 8: Fill `### Source Classification Per Block`**

```markdown
### Source Classification Per Block

For each block, classify its content source per `CORE_SYSTEM.md` § Evidence Classification:

- **target** — the block IS the canonical thing. Original copy / data / hero image authored for this landing.
- **primitive source** — the block lifts visual or structural primitives from a prior approved evidence (e.g. an editorial appendix design system). Note the precedent.
- **negative** — explicitly NOT a target; included only as a "not this" negative example. Rare; usually doesn't appear in a landing wireframe at all.

A wireframe whose every block is "primitive source" is a **primitive showcase**, not a landing. That's the failure mode #88 fell into. The reviewer rejects such wireframes (see § Approval Criteria).
```

- [ ] **Step 9: Fill `### Density Budget`**

```markdown
### Density Budget

A summary count derived from § Per-Block Density Classification:

- Total blocks: `<N>` (must be 5–8)
- Dense blocks: `<D>` (must be 0–2 per `COMPOSITION_RULES` § Density Rules)
- Dense-then-open ordering check: every dense block is followed by an open or medium block. State pass/fail.

The budget is a hard gate. A wireframe with 3 dense blocks fails review.
```

- [ ] **Step 10: Fill `### Asset Inventory`**

```markdown
### Asset Inventory

Two lists:

- **Required assets** — every image, video, or interactive primitive the wireframe relies on. Each entry: id, role (hero_media / gallery / product_demo / ambient_system / poster / fallback), source (target / primitive / negative), URL or path.
- **Missing assets** — anything required but not yet available. Each entry: which block depends on it, what placeholder is acceptable, deadline for resolving.

A wireframe with `Required: hero_media; Missing: hero_media` ships only if the placeholder is explicitly approved by the human reviewer.
```

- [ ] **Step 11: Fill `### Negative Examples`**

```markdown
### Negative Examples

When a relevant failure mode exists in the project's negative-evidence record, name it here as "not this":

- "Not the appendix-clone direction from the #88 r2b attempt — see `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/failed-candidates/system-b-modular/`."
- "Not the primitive-showcase direction from the same attempt — see `failed-candidates/modular/`."

The point is to close off a known wrong path so the human reviewer doesn't have to re-derive that it's wrong. Negative examples are optional but valuable when they exist.
```

- [ ] **Step 12: Verify and commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — required artefact (10 subsections)"
```

---

## Task 5: §Format Options, §Forbidden In A Wireframe, §Approval Criteria

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Fill `## Format Options`**

```markdown
## Format Options

The wireframe artefact may be expressed in any of these forms, alone or combined:

- **Markdown document** with section headings matching the field list above. Preferred for git review.
- **ASCII column diagrams** for desktop layout. Useful for showing column splits.
- **Hand or low-fi tool sketch** (Excalidraw, Figma frame, paper photo) embedded by relative link from the markdown document.
- **Annotated screenshot** of an existing approved page that this landing structurally inherits from, with deltas called out.

The artefact MUST live in the repo at a stable path so the recipe author and reviewer can reference the same revision. Canonical path: `docs/wireframes/<YYYY-MM-DD>-<profile>-<page-slug>.md` and any embedded images alongside. The `docs/wireframes/` root is registered in `docs/architecture/h2t-creative/ROOT_GUIDE.md` § Canonical Architecture Docs (see Task 10 of the plan that produced this file).

The artefact MUST NOT be a high-fidelity mockup, a full design comp, a production-ready CSS draft, or a screenshot of a competitor's site without deltas.
```

- [ ] **Step 2: Fill `## Forbidden In A Wireframe`**

```markdown
## Forbidden In A Wireframe

Items that DO NOT belong at the wireframe stage and that signal scope creep into recipe / skin / implementation:

- **Production / final copy.** A representative draft headline, CTA label, table column labels, and one-line representative body per block IS allowed and recommended — abstract structure approves cleanly but breaks under real text, so a sample text load-bearing test belongs in the wireframe. Mark every such draft explicitly as `(non-final)` so a reader does not mistake it for locked copy. Final word-for-word copy is recipe stage.
- **Specific hex colors / specific font sizes.** Profile `DESIGN.md` and tokens.css own that.
- **Component implementation details** (HTML class names, manifest field names). Skin owns the role-to-component mapping.
- **Pixel-perfect layouts.** This is intentionally low-fidelity. Aim for "structure and intent decided", not "design comp finished".
- **One-off CSS overrides.** Implementation, not wireframe.
- **JavaScript / interactive state machines.** Wireframe names the interactive primitive role and its fallback; the rest is implementation.

A wireframe that violates these is rejected at review with a "scope creep — return to wireframe stage" verdict, not "approved with concerns".
```

- [ ] **Step 3: Fill `## Approval Criteria`**

```markdown
## Approval Criteria

A wireframe is approved when ALL of the following hold. Each item is binary pass/fail.

1. **Mode declared and in vocabulary** (one of `KNOWN_MODES`).
2. **Block sequence is valid**: 5–8 entries; every entry in `KNOWN_BLOCK_TYPES`; first block after `nav` (or first overall) is `hero`; at least one CTA-bearing block.
3. **Per-block intent stated** for every block — not just "show stats" but what the stats argue and to whom.
4. **Per-block density classified** for every block.
5. **Desktop layout sketch present** in any acceptable format, with content max-width and column model declared.
6. **Mobile representation declared** for every multi-column desktop block.
7. **Source classification stated** for every block.
8. **Density budget within rules**: total 5–8; dense ≤ 2; dense never adjacent to dense.
9. **Asset inventory present** with explicit Missing list (or empty).
10. **Negative examples acknowledged** when project negative-evidence record contains a relevant failure mode.
11. **Forbidden-content scan passes** — no production copy, no hex colors, no component implementation details. Representative `(non-final)` draft copy is allowed; production-locked copy is not.
12. **Profile / style-target compatibility verified** against the profile's `DESIGN.md` Restrictions section.

The reviewer signs off only when every item passes. Any failure returns the wireframe to the author with a numbered list of failed items. The reviewer never approves "with conditions to fix later" — fix first, approve after.
```

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — format / forbidden / approval"
```

---

## Task 6: §Outputs After Approval

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Fill `## Outputs After Approval`**

```markdown
## Outputs After Approval

The approved wireframe becomes a frozen reference for downstream work. It produces, by direct copy or simple derivation:

- **Recipe authoring checklist** — the block sequence + per-block intent + per-block density become the recipe's `blocks:` order, `type:` per block, and shape. Recipe content fills intent into copy, data, and asset references.
- **Skin compatibility check** — the chosen profile's `skins/landing.yaml` must map every block role in the sequence. Roles the skin documents under `unsupported_in_v0:` are immediate review failures.
- **Visual QA checklist** — the desktop layout sketch and mobile representation become the per-block "this is what the rendered page should look like" reference for `docs/protocols/h2t-creative/VISUAL_QA.md` Gate A and Gate B. The reviewer compares the screenshot against the wireframe, not against an internal mental model.
- **Test guardrails** — block sequence and required assets can be encoded as recipe-level tests (e.g. "comparison block has tone: accent on at least one row"). Optional and project-scoped.
- **Frozen reference** — a versioned, committed wireframe artefact at a stable path. Subsequent revision requires re-approval through the same gate.

After approval, the implementation phase begins. Recipe edits, CSS edits, and component edits MUST stay within the wireframe envelope. A divergence requires a new wireframe revision and a new approval round, not silent drift.
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — outputs after approval"
```

---

## Task 7: §Worked Examples

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Fill positive example**

Under `### Positive Example — Editorial Landing`:

```markdown
### Positive Example — Editorial Landing

**Intent.** Publish a one-page argument explaining the editorial profile's positioning to a technical reader. Persuade the reader to follow the architecture spec.

**Audience.** Engineers familiar with markdown-driven publishing tools.

**Mode.** `editorial`.

**Profile.** `h2t-editorial`.

**Source dossier.** `target` for hero copy and CTA; `primitive source` for typography and section rhythm (rejuve appendix); `negative` for the failed #88 attempt to NOT repeat.

**Block sequence.**

1. `hero` (open) — headline + meta only
2. `proof` (medium) — 3 stats: editorial profile facts
3. `features` (medium) — 4 cards, what the profile gives the author
4. `process` (medium) — 4 numbered steps from intent to publishable page
5. `comparison` (dense) — legacy `sections:` vs semantic `blocks:` contrast
6. `evidence` (open) — closing argument with two short paragraphs
7. `cta` (open) — two link-style CTAs to architecture spec + recovery plan

**Density budget.** 7 blocks, 1 dense (`comparison`). Dense block followed by open evidence — rhythm OK.

**Desktop layout.** Content max-width 1100 px. Single column dominant; `proof` is 3-up; `features` is 3-up with one wrap; `comparison` is full-width table.

**Mobile representation.** `proof` collapse-to-1col; `features` collapse-to-1col; `comparison` collapse-to-cards; everything else `stack`.

**Asset inventory.** No images, no video. CTA hrefs are anchor links within the same site.

**Negative examples.** Not the appendix-clone from `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/failed-candidates/system-b-modular/`.

This wireframe passes all 12 approval criteria and is compatible with the primitives and landing skin merged in #128. (Note: #128 ships only primitives and the skin — no recipe. Authoring an actual recipe against this wireframe is a separate, post-merge slice.)
```

- [ ] **Step 2: Fill negative example**

Under `### Negative Example — Primitive Showcase (Why It Fails)`:

```markdown
### Negative Example — Primitive Showcase (Why It Fails)

A counter-example reconstructed from the #88 r2b attempt's `recipe-landing.yaml` (preserved at `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/recipe-landing.yaml`):

**Intent.** *Implicit.* "Demonstrate the primitives we extracted from the rejuve appendix."

**Mode.** Not declared.

**Block sequence.** Twelve blocks: page-header, stats, comp-box, decomposition-table, prohibition-table, disc, mmap, meta-box, wave-block, tabs, tags, pos-grid. Effectively one block per primitive.

**Per-block intent.** Each block's intent is "show this primitive". No block argues anything to anyone.

**Density budget.** 12 blocks (above the 5–8 ceiling); 6 of them dense (above the ≤ 2 ceiling); dense blocks adjacent.

**Mobile representation.** Not declared.

**Source classification.** Every block is `primitive source`. Zero `target`. Zero original copy.

**Why it fails review.** Approval criterion 1 (mode), 2 (block sequence size + first-block-hero rule), 3 (intent), 6 (mobile), 7 (source classification), and 8 (density budget) all fail. The renderer would build it, screenshots would render, every primitive would visually appear — and no reader could say what the page is for. The failure is composition, not implementation.

The lesson: a primitive showcase is not a landing. The wireframe gate exists specifically to catch this before recipe authoring spends time on it.
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — worked examples (positive + negative)"
```

---

## Task 8: §Cross-References

**Files:**
- Modify: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`

- [ ] **Step 1: Fill `## Cross-References`**

```markdown
## Cross-References

- `docs/protocols/h2t-creative/WIREFRAME_GATE.md` — the generic gate this contract specialises.
- `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md` — the review checklist a human reviewer runs against this contract.
- `docs/architecture/h2t-creative/COMPOSITION_RULES.md` — Swiss grid, density, rhythm constraints the contract operationalises.
- `docs/architecture/h2t-creative/CORE_SYSTEM.md` — the semantic layer vocabulary (`KNOWN_BLOCK_TYPES`, `KNOWN_MODES`) referenced by the contract.
- `docs/architecture/h2t-creative/PRD.md` — workflow context (wireframe is step 4 of "Content To Representation").
- `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md` — how to add new block roles or formats; new format-specific contracts (deck, report, …) follow this contract by analogy.
- `docs/superpowers/references/stitch-design-md-spec-reference.md` — profile DESIGN.md format the wireframe must check compatibility against.
- `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/` — concrete negative-evidence record cited in § Worked Examples.
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
git commit -m "docs(h2t-creative): wireframe contract — cross-references"
```

---

## Task 9: Create LANDING_WIREFRAME_REVIEW.md

**Files:**
- Create: `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md`

- [ ] **Step 1: Write the review checklist**

```markdown
# h2t-creative Landing Wireframe Review

## Purpose

This is the human reviewer's pass/fail checklist for a landing wireframe submitted under `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`.

The reviewer does not author the wireframe. The reviewer verifies it. Approval is binary: every item passes, or the wireframe returns to the author.

## When To Run This Review

- Before any recipe / CSS / component work begins for a landing page.
- On every wireframe revision (re-approval is mandatory after changes).
- When a stakeholder challenges an in-flight implementation: roll back to the most recently approved wireframe.

## Checklist

For each item: PASS, FAIL, or N/A. Any FAIL returns the wireframe.

### A. Structural completeness

- [ ] **A1.** Mode declared, in `KNOWN_MODES` (`product`, `service`, `editorial`, `report`, `portfolio`, `deck-companion`).
- [ ] **A2.** Block sequence: 5–8 entries; every entry in `KNOWN_BLOCK_TYPES`.
- [ ] **A3.** First block (after optional `nav`) is `hero`.
- [ ] **A4.** At least one CTA-bearing block present.
- [ ] **A5.** Per-block intent stated for every block. Not "show stats" — what the stats argue and to whom.
- [ ] **A6.** Per-block density classified (`dense` / `medium` / `open`) for every block.
- [ ] **A7.** Desktop layout sketch present, with content max-width and column model declared.
- [ ] **A8.** Mobile representation declared per block (`stack` / `collapse-to-1col` / `collapse-to-cards` / `hide` / `media-fallback`).
- [ ] **A9.** Source classification stated for every block (`target` / `primitive source` / `negative`).
- [ ] **A10.** Asset inventory present: required + missing lists.

### B. Density and rhythm

- [ ] **B1.** Total block count: 5–8.
- [ ] **B2.** Dense blocks: ≤ 2.
- [ ] **B3.** Dense blocks not adjacent to other dense blocks (every dense followed by medium or open).
- [ ] **B4.** Hero is `open` density.
- [ ] **B5.** First-screen content (hero + first body block) communicates intent without scrolling.

### C. Forbidden content scan

- [ ] **C1.** No production / final copy locked into the wireframe. Representative draft copy (sample headline, CTA label, table column labels, one-line body per block) IS allowed — and recommended — provided each instance is explicitly marked `(non-final)`. A reviewer rejects only when the copy is presented as production-ready, not when it serves as load-bearing structural sample.
- [ ] **C2.** No specific hex colors or specific font sizes (profile `DESIGN.md` owns those).
- [ ] **C3.** No component implementation details (HTML class names, manifest field names).
- [ ] **C4.** No pixel-perfect layout — wireframe is intentionally low-fidelity.
- [ ] **C5.** No one-off CSS overrides described.
- [ ] **C6.** No JavaScript / interactive state machine implementation.

### D. Failure-mode awareness

- [ ] **D1.** If the project's negative-evidence record contains a relevant failure (e.g. `docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/`), the wireframe acknowledges it under "Negative examples".
- [ ] **D2.** Block source classification is not entirely `primitive source` (would be a primitive showcase, the #88 failure mode).
- [ ] **D3.** Block sequence is not a verbatim copy of an appendix or report structure (per `WIREFRAME_GATE.md` § Forbidden Before Approval).

### E. Profile compatibility

- [ ] **E1.** Chosen profile's `DESIGN.md` Restrictions section is not violated by the proposed block density or content shape.
- [ ] **E2.** Chosen profile's `skins/landing.yaml` (if it exists yet) maps every block role in the sequence; or, if absent, the wireframe identifies which roles the skin will need to add and notes them as a prerequisite slice.
- [ ] **E3.** Required assets exist or have an explicit placeholder + deadline.

## Verdicts

- **APPROVED** — every item PASS or N/A. Recipe authoring may begin.
- **CHANGES REQUESTED** — at least one FAIL. Reviewer returns the wireframe with the failed-item numbers and a one-sentence note per failure. Author revises and resubmits.
- **SCOPE-CREEP REJECT** — the wireframe contains forbidden content (Section C). Reviewer returns it with "return to wireframe stage; this is implementation". No partial approval.

## Audit Trail

Record the verdict, the reviewer's name/handle, the wireframe revision identifier (commit SHA), and the date alongside the wireframe artefact. The recipe author cites this audit trail in the recipe PR description.

## Cross-References

- `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` — the contract this review verifies.
- `docs/protocols/h2t-creative/WIREFRAME_GATE.md` — the generic gate.
- `docs/protocols/h2t-creative/VISUAL_QA.md` — the next gate, run after the rendered page exists.
```

- [ ] **Step 2: Commit**

```bash
git add docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md
git commit -m "docs(h2t-creative): add landing wireframe review checklist"
```

---

## Task 10: Cross-link patches and `docs/wireframes/` root anchor

**Files:**
- Modify: `docs/protocols/h2t-creative/WIREFRAME_GATE.md`
- Modify: `docs/architecture/h2t-creative/ROOT_GUIDE.md`
- Modify: `docs/architecture/h2t-creative/COMPOSITION_RULES.md`
- Create: `docs/wireframes/README.md` (registers the new canonical root)

- [ ] **Step 1: Patch `WIREFRAME_GATE.md`**

In `docs/protocols/h2t-creative/WIREFRAME_GATE.md`, after the existing line `- Explicit "not this" negative examples when relevant` inside the "Required Wireframe Artifact" section, append a new paragraph:

```markdown

For landing pages specifically, the format-specialised shape of this artefact is defined in `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md`. Reviewers run the checklist at `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md`. Sibling format-specific contracts (deck, report, carousel, interactive) follow the same pattern as they are added.
```

- [ ] **Step 2: Patch `ROOT_GUIDE.md`**

In `docs/architecture/h2t-creative/ROOT_GUIDE.md` § Required Reading By Task, expand item 4 to reference the landing-specific contract. Replace:

```markdown
4. Read the relevant protocol:
   - Landing/deck/page work: `docs/protocols/h2t-creative/WIREFRAME_GATE.md`
   - Visual review: `docs/protocols/h2t-creative/VISUAL_QA.md`
   - New block/layout/format: `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md`
```

with:

```markdown
4. Read the relevant protocol:
   - Landing work: `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` (format-specific) plus `docs/protocols/h2t-creative/WIREFRAME_GATE.md` (generic) and `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md` (reviewer checklist).
   - Deck / report / page work: `docs/protocols/h2t-creative/WIREFRAME_GATE.md` (format-specific contracts pending).
   - Visual review: `docs/protocols/h2t-creative/VISUAL_QA.md`.
   - New block/layout/format: `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md`.
```

Then in § Canonical Architecture Docs, add three new bullets at the appropriate alphabetical position:

```markdown
- `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` — landing-specific wireframe artefact format. Required reading before any landing recipe is authored.
- `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md` — reviewer's pass/fail checklist for a landing wireframe.
- `docs/wireframes/` — approved wireframe artefacts. One file per page at `<YYYY-MM-DD>-<profile>-<page-slug>.md`, with any embedded sketch images alongside. Living source for visual QA and recipe authoring.
```

- [ ] **Step 3: Patch `COMPOSITION_RULES.md`**

In `docs/architecture/h2t-creative/COMPOSITION_RULES.md` § Density Rules, after the "Default landing constraints" bullet list, append:

```markdown

The landing density rules above are operationalised by `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` § Density Budget. Wireframe approval enforces them before recipe authoring begins.
```

- [ ] **Step 4: Create `docs/wireframes/README.md` (REQUIRED root anchor)**

This file is **mandatory**, not optional. Without it, the `docs/wireframes/` root referenced from `ROOT_GUIDE.md` resolves to nothing and a future agent can drift back to a primitive-showcase failure mode by losing the canonical storage location for approved wireframes. Steps 5 and Task 11 enforce its presence as hard gates.

```bash
mkdir -p docs/wireframes
cat > docs/wireframes/README.md <<'EOF'
# h2t-creative Wireframes

This directory holds approved wireframe artefacts for h2t-creative landing pages, decks, reports, carousels, and interactive explainers. One file per page, named `<YYYY-MM-DD>-<profile>-<page-slug>.md`, with any embedded sketch images alongside.

A wireframe lives here only AFTER it has been approved per the relevant gate:

- Landings → `docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md` + `docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md`.
- Decks / reports / carousels / interactive — format-specific contracts pending; until they exist, the generic gate at `docs/protocols/h2t-creative/WIREFRAME_GATE.md` applies.

The approved wireframe is the source of truth for downstream recipe authoring, visual QA, and human review. Subsequent revisions require re-approval through the same gate.
EOF
```

- [ ] **Step 5: Verify all cross-links resolve**

```bash
cd C:/dev/h2t-skills-wireframe-contract
/c/Users/stani/.h2t/venv/Scripts/python.exe -c "
import re, pathlib, sys
root = pathlib.Path('.')
required_anchor = root / 'docs/wireframes/README.md'
assert required_anchor.exists(), (
    'FAIL: docs/wireframes/README.md is missing. This file is the '
    'mandatory root anchor for approved wireframe artefacts. Without '
    'it the docs/wireframes/ reference in ROOT_GUIDE.md does not '
    'resolve and future agents lose the canonical storage location.'
)
files = [
    'docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md',
    'docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md',
    'docs/protocols/h2t-creative/WIREFRAME_GATE.md',
    'docs/architecture/h2t-creative/ROOT_GUIDE.md',
    'docs/architecture/h2t-creative/COMPOSITION_RULES.md',
    'docs/wireframes/README.md',
]
ref_re = re.compile(r'\`(docs/[^\`]+)\`')
broken = []
for f in files:
    text = (root / f).read_text(encoding='utf-8')
    for m in ref_re.finditer(text):
        ref = m.group(1).split('#')[0].split(' ')[0]
        # strip trailing punctuation
        ref = ref.rstrip('.,;:')
        target = root / ref
        if not target.exists() and not (root / ref.rstrip('/')).exists():
            broken.append(f'{f} -> {ref}')
if broken:
    print('BROKEN cross-references:')
    for b in broken: print(f'  {b}')
    sys.exit(1)
print(f'PASS all docs/ cross-references resolve in {len(files)} files')
"
```

Expected: `PASS all docs/ cross-references resolve in 6 files`

- [ ] **Step 6: Commit cross-link patches and the new root anchor**

```bash
git add docs/protocols/h2t-creative/WIREFRAME_GATE.md docs/architecture/h2t-creative/ROOT_GUIDE.md docs/architecture/h2t-creative/COMPOSITION_RULES.md docs/wireframes/README.md
git commit -m "docs(h2t-creative): cross-link landing wireframe contract + register docs/wireframes/ root"
```

---

## Task 11: Final verification, push, PR

**Files:**
- Use: all of the above

- [ ] **Step 1: Verify diff scope**

```bash
cd C:/dev/h2t-skills-wireframe-contract
git diff --stat origin/main..HEAD | tail -10
```

Expected: 7 files changed (1 plan + 3 new: `LANDING_WIREFRAME_CONTRACT.md`, `LANDING_WIREFRAME_REVIEW.md`, `docs/wireframes/README.md` + 3 modified: `WIREFRAME_GATE.md`, `ROOT_GUIDE.md`, `COMPOSITION_RULES.md`), insertions only or insertions plus a small modification delta. No `plugins/`, no `.css`, no `.py`, no `.yaml`.

- [ ] **Step 2: Guard check — only docs/ touched**

```bash
git diff --name-only origin/main..HEAD | grep -vE "^docs/" || echo "(empty = clean — only docs touched)"
```

Expected: `(empty = clean — only docs touched)`

- [ ] **Step 3: Hard gate — required new files MUST appear in the diff**

```bash
git diff --name-only origin/main..HEAD | grep -E "^(docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT\.md|docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW\.md|docs/wireframes/README\.md)$" | sort
```

Expected (exactly three lines, in this order):

```
docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md
docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md
docs/wireframes/README.md
```

If `docs/wireframes/README.md` is absent here, STOP. The PR cannot land without the root anchor — a missing README means future agents lose the canonical storage location for approved wireframes (the failure mode this entire slice is meant to prevent).

- [ ] **Step 4: Run plugin + global tests as a sanity belt-and-braces**

```bash
/c/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-creative/tests/ --tb=short 2>&1 | tail -3
/c/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/h2t_creative/test_assembler.py --tb=short 2>&1 | tail -3
```

Expected: both green. Plugin: ~ 968 passed, 6 skipped. Global: 105 passed. (No tests should change.)

- [ ] **Step 5: Push branch**

```bash
git push -u origin docs/h2t-creative-landing-wireframe-contract
```

- [ ] **Step 6: Open PR**

```bash
gh pr create --title "docs(h2t-creative): add Universal Landing Wireframe Contract" --body "$(cat <<'EOF'
## Why

`WIREFRAME_GATE.md` (merged via #122) requires a wireframe before recipe implementation but specifies the artefact requirements at the generic level — applicable to landings, decks, reports, carousels, and interactive explainers in the same breath. That generality is correct for the gate but leaves an abstraction gap when an author actually sits down to draft a landing wireframe: the field list is not specialised, the approval criteria are not concrete, and "wireframe" risks devolving into "primitive showcase" — the exact #88 failure mode preserved at \`docs/archive/h2t-creative/2026-05-07-r2b-editorial-landing-failed-attempt/\`.

This PR closes that gap for landings specifically. It adds two new docs and three small cross-link patches into already-merged canonical pages.

## What

- **NEW** \`docs/architecture/h2t-creative/LANDING_WIREFRAME_CONTRACT.md\` — the landing-specific wireframe artefact format. Mode vocabulary, block-sequence rules, per-block intent / density / mobile-representation / source-classification fields, density budget, asset inventory, format options, forbidden content, approval criteria, outputs after approval, worked positive + negative examples (the negative drawn from the #88 archive).
- **NEW** \`docs/protocols/h2t-creative/LANDING_WIREFRAME_REVIEW.md\` — the reviewer's pass/fail checklist (sections A–E). Used by the human approver per \`WIREFRAME_GATE.md\` § Human Approval.
- **PATCH** \`WIREFRAME_GATE.md\` → forward-link to the landing-specific shape.
- **PATCH** \`ROOT_GUIDE.md\` → adds the two new docs to Required Reading By Task and Canonical Architecture Docs.
- **PATCH** \`COMPOSITION_RULES.md\` → back-reference: density rules are operationalised by the contract.

Sibling format-specific contracts (deck, report, carousel, interactive) follow this contract by analogy when added.

## Scope

- ✅ docs only
- ❌ no runtime / no CSS / no recipe / no Python / no tests of code paths
- ❌ no profile changes / no \`DESIGN.md\` edits
- ❌ no new components

## Verification

- All cross-references resolve (verified by a small Python check at task 10).
- Plugin tests: unchanged from base (no Python touched).
- Global assembler tests: unchanged.
- Diff scope: every changed file under \`docs/\`.

## Adoption arc context

| PR | Role |
|---|---|
| #122 | architecture & wireframe gate (generic) |
| #128 | h2t-editorial primitives + landing skin (foundation for landing recipes) |
| **this** | landing-specific wireframe shape + review checklist (closes the gap between gate and recipe) |

After merge, a landing recipe slice can be drafted with a concrete wireframe artefact format to fill in and a concrete checklist to be reviewed against. The next-after-this product slice is a real, wireframe-gated h2t-editorial landing recipe — replacing the negative-evidence candidate currently held on \`feat/119-editorial-semantic-landing-pilot\`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7: Stop**

After PR is open, stop. Do not begin recipe implementation. The next slice (a wireframe-gated landing recipe) is a separate PR that runs the contract end-to-end on a real piece of content.

---

## Self-Review Notes (writer)

The plan covers every WIREFRAME_GATE bullet via the table in Task 2 Step 2. Approval criteria in CONTRACT match review checklist items in REVIEW. All forward and backward cross-links named. No placeholders remain — every step contains the actual markdown to write. File paths consistent throughout (e.g. `LANDING_WIREFRAME_CONTRACT.md` always under `docs/architecture/h2t-creative/`, `LANDING_WIREFRAME_REVIEW.md` always under `docs/protocols/h2t-creative/`). Every "verify" step has an expected output. The plan is committed before any other change so it remains the entry point a fresh executor can read first.
