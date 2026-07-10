# Proposed additions to `C:/dev/docs/standards/evidence-grounded-synthesis.md`

Harvested practices that belong in the existing standard rather than a new one.

## Evidence tiering ladder: grade each field A–D, gate status transitions on minimum grade per field

- **Evidence:** lineages h2t-business · recurrence 1 · domain-indep high
- **Source:** `C:/dev/h2t-business/.claude/rules/research-validation.md`
- **What to add:** Assign an explicit evidence grade to every field in a research record using a tiered ladder: A = screenshot + URL + verbatim quote + accessed timestamp; B = URL + quote, no screenshot; C = URL only or paraphrase; D = AI-inference. Grade D is forbidden in any `approved` record. Status transitions (draft → reviewed, reviewed → approved) require all fields to meet a minimum grade — specify the minimum per status level. This prevents false-verified records where some fields are well-sourced and others are AI-inferred.

## LLM extraction to distillation with faithfulness-judge gate (quote-binding + stable evidence IDs)

- **Evidence:** lineages quant-kb, POS, rejuve · recurrence 3 · domain-indep high
- **Source:** `C:/dev/POS/docs/superpowers/specs/2026-06-07-meeting-graph-layer-v0-1.md`, `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-quant-kb-research-intake-pipeline-2026-07-05.md`, `C:/work/rejuve/docs/superpowers/plans/2026-07-03-jtbd-segmentation.md`
- **What to add:** LLM extraction pipelines must include a faithfulness-judge gate between extraction and distillation. Each extracted claim must carry a stable evidence ID and a verbatim quote from the source. The judge pass verifies quote-binding (the extraction is entailed by the quote) before the claim can advance to distillation. A claim that fails the faithfulness gate is flagged, not silently discarded — it appears in the output with a FAILED_FAITHFULNESS label.

## Per-field evidence grounding / anti-false-verified: a record is verified only when EVERY required field is anchored to a primary source

- **Evidence:** lineages claudeworking, crypto-regime-spike · recurrence 2 · domain-indep high
- **Source:** `C:/work/claudeworking/docs/superpowers/specs/2026-07-04-grants-phase2-cards-and-explorer-design.md`, `C:/dev/crypto-regime-spike/docs/superpowers/specs/2026-06-15-passport-conventions-v2.md`
- **What to add:** A research record must not be marked `verified` unless every required field carries an independent primary-source anchor (URL + quote + accessed date). Partial anchoring — where some fields are primary-sourced and others are inferred or copied from prior passes — is not verification. Add a schema-level check: the verification flag must be blocked if any required field's `evidence_grade` is below the approved threshold.
