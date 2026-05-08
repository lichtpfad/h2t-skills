# R2b — h2t-editorial landing — failed attempt (negative evidence)

**Status:** Archived as **negative evidence**. Not a positive target.

This folder preserves the failed editorial-landing attempt from issue #88 / branch `codex/r2b-editorial-landing` so the lesson it taught the project survives independently of the worktree it lived in.

The artefacts here describe **a renderer-level success that was a design-level failure**. They are kept to teach the wireframe-gate lesson (canonised in #122) by example, and to make a small set of intermediate sources available for future review under the gate. They are **not** to be copied as positive design targets.

---

## Provenance

| Field | Value |
|---|---|
| Issue | [#88 — h2t-editorial landing recovery](https://github.com/lichtpfad/h2t-skills/issues/88) |
| Branch | `codex/r2b-editorial-landing` (worktree `C:/dev/h2t-skills-r2b-landing`) |
| Active period | 2026-05-03 → 2026-05-07 |
| Final state | uncommitted working tree at branch tip `54c2ca3` |
| Successor work | semantic renderer v0 (#118 / PR #120, merged) → editorial pilot (#119, branch open as evidence) → wireframe gate (#122, merged) → Stitch DESIGN.md adoption (#124-#126, merged) |
| Archive trigger | the worktree was about to be deleted; preserving evidence first |

The branch and worktree were retained well past the failed attempt because the artefacts they contained were the only record of how and why the attempt failed. This archive replaces the worktree as the canonical record so the worktree can be removed safely.

---

## Why it failed

The attempt produced a renderer that built without errors, output a valid `index.html`, and matched its own internal style spec — but the resulting page was **not a landing**. It was a primitive showcase rendering a flattened reproduction of the rejuve appendix design system rather than a composed landing page with a defined intent, hero, proof, and call-to-action.

Two compounding root causes (both now codified as system gates):

1. **No approved wireframe before recipe implementation.** Recipe authoring proceeded directly from extracted primitives. There was no composition decision step that fixed which roles the landing needed, in what order, with what density. The renderer could not have refused — it had nothing to refuse against.

2. **Visual sources were classified as fidelity targets when they were primitive sources.** The rejuve appendix HTML pages (preserved here under `golden-references/`) carry the editorial typographic and palette language we wanted to lift, but they are appendix/report layouts, not landing layouts. The Batch C build cloned the appendix structure 1:1; the post-Intent-Reset rebuild kept the same primitive vocabulary but never had a target wireframe to compose against. The result was visually consistent at the primitive level and structurally wrong at the composition level.

The full audit trail of the Intent Reset moment is in `failed-candidates/system-b-modular/EVIDENCE.md` and `failed-candidates/modular/EVIDENCE.md`.

---

## Relation to current canonical docs

The lessons surfaced here fed directly into the protocol reset merged via #122:

| Lesson from r2b | Codified in |
|---|---|
| Recipe must not be authored before composition is approved | `docs/protocols/h2t-creative/WIREFRAME_GATE.md` |
| Visual sources need explicit classification (target vs primitive vs negative) | `docs/architecture/h2t-creative/CORE_SYSTEM.md` § Evidence Classification |
| Renderer pass ≠ visual pass | `docs/protocols/h2t-creative/VISUAL_QA.md` § "Renderer Pass Is Not Visual Pass" |
| Reuse-before-create when adding blocks/layouts/formats | `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md` |
| Source arbitration before T1 implementation begins | `specs/source-arbitration.md` here (T0.5 proposal — informed `WIREFRAME_GATE.md`) |

When `ROOT_GUIDE.md` (#122) lists "current known evidence" and points to the editorial semantic landing as a **failed landing composition** that should not be replaced until an approved wireframe-driven candidate exists, this folder is the source of that classification.

---

## What is preserved here

### Text evidence

| File | Role |
|---|---|
| `recipe-landing.yaml` | The failed pilot recipe — primary negative-evidence cornerstone. Demonstrates the primitive-showcase failure mode. |
| `landing-references.yaml` | Source dossier the attempt locked. Useful context for how sources were classified at the time. |
| `specs/composition-spec.md` | Composition specification authored mid-flight after the Intent Reset. Partially correct; superseded by `COMPOSITION_RULES.md` on main. |
| `specs/design-system.md` | Design-system extraction from rejuve appendix. Some primitive-vocabulary content is still useful and was lifted into #119 T6 components. |
| `specs/rhythm-spec.md` | Rhythm spec — vertical density / dual-representation rules. The `mobile_representation: cards` contract here is the seed for the `render_comparison_cards` helper merged via #123. |
| `specs/source-arbitration.md` | T0.5 source-arbitration gate proposal. Promoted into the wireframe-gate protocol on main via #122. |

### Golden references (successful precedent — not failed)

`golden-references/` carries the two rejuve appendix HTML pages and their screenshots. These are the **successful editorial precedent** the failed attempt was lifting from. They are kept for two reasons:

1. To verify the typographic and palette language extracted into #119 T6 components against the original.
2. To make the source-classification problem concrete: these pages are appendix/report layouts, not landings. Anyone reading this archive can see for themselves why a 1:1 clone produced a non-landing result.

These files **are not** failed evidence. They are the design-language source. The failure was in how they were classified, not in the source pages.

### Failed candidates

`failed-candidates/modular/` and `failed-candidates/system-b-modular/` carry the build evidence of the two main attempts:

- `system-b-modular/` — Batch C, the appendix-clone direction. Rejected on intent grounds (target mismatch, not implementation bug). One desktop + one mobile screenshot from the final 21:01 capture.
- `modular/` — post-Intent-Reset rebuild that satisfies its own composition spec but still suffers from the underlying "primitive showcase" problem, because no approved wireframe ever existed for it to compose against.

The `EVIDENCE.md` in each subfolder explains, build by build, what was captured and why.

### Components inventory

`components-untracked-inventory.md` (sibling file) classifies the 21 candidate components that lived in the r2b worktree's `components/` directory (most were untracked). It identifies which were lifted into #119 T6 (and remain on the editorial pilot branch), which were R1 base components from `origin/main`, and which were net-new candidates that did not make it into any merged work. The net-new ones are listed by name only — their source is not duplicated here, since they were never preserved as commits and the worktree is being retired. If any of them is later needed, it can be reconstructed against the new wireframe gate.

---

## What is NOT preserved here

Per scope: this archive prefers text and screenshots over generated dist HTML and over uncommitted runtime modifications.

- **`dist/r2b-h2t-editorial-landing-{modular,system-b-validation}/`** — small (≤80 KB total) but gitignored and regeneratable from `recipe-landing.yaml` plus the components on the branch tip. Not copied.
- **Uncommitted runtime modifications** to active files in `plugins/h2t-creative/profiles/h2t-editorial/{components/section/, tokens.css}` and `plugins/h2t-creative/skills/legacy-fidelity/{SKILL.md, references/pressure-scenarios.md}`. These were experimental edits to active profile / skill files. They MUST NOT be applied to current main; they are intentionally lost when the worktree is removed.
- **Sources of the 10 net-new candidate components** that did not make it into #119. Listed by name in `components-untracked-inventory.md`; not copied.
- **`__pycache__/`** and other generated artefacts.

If any of the omitted items turns out to be needed, the worktree retains them until removal — recover before deleting. After that, the loss is deliberate.

---

## What may be reused — only after review under the wireframe gate

The following items may seed future work, but **only after passing through `docs/protocols/h2t-creative/WIREFRAME_GATE.md`**:

- The typographic / palette language captured in `specs/design-system.md` — most of it is already lifted into #119 T6 components. Future work that needs additional primitives from the rejuve appendix should go through reuse-before-create per #122 `EXTENSION_PROTOCOL.md`.
- The dual-representation contract for tables in `specs/rhythm-spec.md` — already partially codified by the `render_comparison_cards` helper merged via #123.
- The T0.5 source-arbitration step in `specs/source-arbitration.md` — already promoted into the wireframe-gate protocol on main; this file is the historical seed.
- Any of the 10 net-new candidate component names listed in `components-untracked-inventory.md` — but only if a wireframe explicitly calls for that role and reuse-before-create cannot satisfy it.

---

## What MUST NOT be copied as a positive target

- **`recipe-landing.yaml`** — primitive showcase, no approved wireframe. Do not migrate as a positive example. Tests on the editorial pilot branch (`feat/119-editorial-semantic-landing-pilot`) explicitly assert this file is absent at the active path.
- **The failed-candidate screenshots** under `failed-candidates/` — they record the rejected outcome. Do not reuse as visual gate evidence.
- **The composition-spec / rhythm-spec markdown** — they were authored mid-flight to rationalise the failure and are partially correct. The canonical replacements are `docs/architecture/h2t-creative/COMPOSITION_RULES.md` and `docs/protocols/h2t-creative/WIREFRAME_GATE.md` on main. Cite the canonical docs, not the archived ones.
- **The uncommitted runtime modifications** mentioned above — explicitly excluded from this archive and must not be lifted from the worktree before deletion.

---

## After this archive lands on main

The worktree `C:/dev/h2t-skills-r2b-landing` and the branch `codex/r2b-editorial-landing` become safe to remove. Removing them will not lose any evidence covered by this archive. Removing them will lose the items explicitly NOT preserved (above). That loss is deliberate.
