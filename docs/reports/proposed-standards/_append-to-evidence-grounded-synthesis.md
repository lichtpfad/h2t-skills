# Proposed additions to `C:/dev/docs/standards/evidence-grounded-synthesis.md`

## Grade evidence on a tiered ladder and gate status transitions on minimum grade
- **Evidence:** lineages h2t-business · recurrence 1 · domain-indep high
- **Source:** `C:/dev/h2t-business/.claude/rules/research-validation.md`
- **What to add:** Assign an explicit evidence grade to every field in a research record, using a tiered ladder (example: A = screenshot + URL + verbatim quote; B = URL + paraphrase; C = secondary source; D = inference; forbidden = AI-only assertion with no external anchor). Status transitions (draft → reviewed → approved) require that all key fields meet a minimum grade for that transition. Fields below the threshold must be flagged or left blank, not filled with lower-grade inference.

## LLM-extraction faithfulness gate: LLM emits locators, code owns quotes
- **Evidence:** lineages rejuve, quant-kb, POS · recurrence 3 · domain-indep high
- **Source:** `C:/work/rejuve/docs/superpowers/plans/2026-07-03-jtbd-segmentation.md`, `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-quant-kb-plan5-llm-extraction-2026-07-06.md`, `C:/dev/POS/docs/superpowers/plans/2026-06-07-meeting-graph-v0-3.md`
- **What to add:** In LLM-extraction pipelines, the LLM must emit only locators (e.g., start/end character offsets or span IDs), never the quote text itself. A deterministic script extracts the verbatim quote from the source document using those locators. If the LLM-returned span diverges from the source (faithfulness mismatch), the extraction fails closed — the item is skipped, logged, and does not appear in the output corpus.
