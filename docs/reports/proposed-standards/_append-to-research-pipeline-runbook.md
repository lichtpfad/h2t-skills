# Proposed additions to `C:/dev/docs/standards/research-pipeline-runbook.md`

## Corpus-as-SSOT JSON with per-field evidence provenance and drift-hash
- **Evidence:** lineages claudeworking, quant-kb, rejuve · recurrence 3 · domain-indep high
- **Source:** `C:/work/claudeworking/docs/superpowers/specs/2026-07-04-grants-phase2-cards-and-explorer-design.md`, `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-plan6-typization-2026-07-06.md`, `C:/Users/stani/.h2t/sessions/AUTOMATA/rejuve/analytics-rejuve-audience-dashboard-2026-07-04.md`
- **What to add:** The corpus JSON is the single source of truth for all numbers and extracted data. Every field must carry evidence provenance (source identifier + grade). A drift-hash is computed over the corpus at generation time and embedded in any derived artifact (HTML report, dashboard). Before publishing a derived artifact, verify its embedded hash matches the current corpus hash. If hashes diverge, regenerate — never patch the artifact directly.
