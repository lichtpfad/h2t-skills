# Deferred (stage 2) and skipped findings

## Deferred to code/skill (natural home is not a guidebook)

### deferred:skill — belongs in a skill, not a written standard

| practice | verdict | lineages | source |
|---|---|---|---|
| Run a codex review-gate after every plan checkpoint and before any completion claim | `deferred:skill` | crypto-regime-spike, quant-kb, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/execution-protocols.md`, `C:/dev/quant-kb/.claude/rules/codex-review.md`, `C:/dev/h2t-skills/.claude/rules/autonomous-execution.md` |
| Gate autonomous-run completion behind a multi-lens council (codex + >=2 Opus lenses, verdict SOUND before handoff) | `deferred:skill` | crypto-regime-spike, quant-kb, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/execution-protocols.md`, `C:/dev/quant-kb/CLAUDE.md`, `C:/dev/h2t-skills/.claude/rules/autonomous-execution.md` |
| Carry a durable autonomous-execution runbook that survives compaction: pipeline steps as checkboxes, always end on handoff even when BLOCKED | `deferred:skill` | crypto-regime-spike, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/autonomous-execution-runbook.md`, `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/reference_autonomous_run_skill.md` |
| End sessions with a durable handoff record (not a chat summary), route reusable discoveries to a persistent backlog | `deferred:skill` | claudeworking, rejuve, crypto-regime-spike | `C:/work/claudeworking/.claude/rules/session.md`, `C:/dev/crypto-regime-spike/.claude/rules/project-workflow.md`, `C:/work/rejuve/.claude/rules/repo-hygiene.md` |
| Route all provider I/O (Drive, Gmail, Calendar, Notion, Telegram, MeetGeek) through h2t-ops connector | `deferred:skill` | h2t-skills | `C:/dev/h2t-skills/.claude/rules/connectors.md`, `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/reference_meetgeek_upload_flow.md` |
| Preserve the user's query language in neural/Exa searches; do not translate a non-English query | `deferred:skill` | h2t-skills | `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/feedback_preserve_query_language.md` |
| Log non-obvious findings immediately during the session into a persistent register rather than waiting for end-of-session | `deferred:skill` | rejuve | `C:/work/rejuve/CLAUDE.md` |
| Durable runbook artifact + sealed section-scoped drift-guard validator (survives compaction, two-track resume) | `deferred:skill` | h2t-skills | `C:/dev/h2t-skills/docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md`, `C:/dev/h2t-skills/docs/superpowers/plans/2026-07-10-cross-repo-practice-harvest.md` |

### deferred:code — belongs in library/framework code, not a guidebook

| practice | verdict | lineages | source |
|---|---|---|---|
| Deploy plugin changes via commit → git push → marketplace update → reload (never update-plugin.sh as final) | `deferred:code` | h2t-skills | `C:/dev/h2t-skills/.claude/rules/plugin-deploy.md`, `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/feedback_plugin_reload.md` |
| Two-gate / staged verdict split (cheap screen gate then confirm gate, distinct verdict per gate) | `deferred:code` | crypto-regime-spike, quant-kb | `C:/dev/crypto-regime-spike/docs/superpowers/plans/2026-06-27-plan4-statistical-multiplicity-oos.md`, `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-quant-kb-plan16-two-gate-verdict-2026-07-10.md` |
| Deterministic validation-library / acceptance-gate that calls the real production gate code instead of reimplementing it | `deferred:code` | crypto-regime-spike, claudeworking, h2t-business | `C:/work/claudeworking/docs/superpowers/plans/2026-07-04-grants-phase2-cards-and-explorer.md`, `C:/dev/h2t-business/docs/superpowers/plans/2026-07-08-course-design-framework.md`, `C:/dev/crypto-regime-spike/docs/superpowers/specs/2026-06-16-pipeline-validation-spec.md` |
| Multi-judge consensus panel for adjudicating extracted claims (parallel judges, majority vote, aggregated deterministically) | `deferred:code` | quant-kb, crypto-regime-spike, rejuve | `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-plan9-council-rekey-2026-07-07.md`, `C:/work/rejuve/docs/superpowers/plans/2026-07-03-jtbd-segmentation.md`, `C:/dev/crypto-regime-spike/docs/superpowers/specs/2026-06-15-passport-conventions-v2.md` |
| Pre-registration / freeze-before-run + append-only immutable ledger for honest multiplicity accounting | `deferred:code` | crypto-regime-spike, quant-kb | `C:/Users/<user>/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-multiplicity-denominator-2026-06-27.md`, `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-operator-freeze-2026-07-08.md` |
| Known-answer / byte-identical golden anchor pinned as a mutation-detecting regression tripwire across every merge | `deferred:code` | crypto-regime-spike, quant-kb | `C:/Users/<user>/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-money-hypoth-plan4-2026-06-27.md`, `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-plan6-typization-2026-07-06.md` |
| Per-run telemetry / cost run-ledger emitted from real usage (shared by benchmark + production runs, not estimates) | `deferred:code` | crypto-regime-spike, quant-kb | `C:/Users/<user>/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-pr76-merge-2026-07-09.md`, `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-plan19-sonnet-extract-2026-07-09.md` |
| LLM-extraction model/config benchmarking with golden-ref scoring + per-stage evaluability | `deferred:code` | quant-kb | `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-plan19-benchmark-2026-07-09.md`, `C:/Users/<user>/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-ingest-model-benchmark-2026-07-09.md` |
| Fail-closed autonomy guard: autonomous agent capped to a status ceiling (MACHINE_CANDIDATE/KILL) with mechanical never-false-GO asserts + frozen manifest | `deferred:code` | crypto-regime-spike | `C:/Users/<user>/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-money-hypoth-phase1-2026-07-04.md` |
| PIT / look-ahead temporal-leakage guard: explicit available_time convention + pin-test that a value on date D uses only data known by D | `deferred:code` | crypto-regime-spike | `C:/Users/<user>/.h2t/sessions/AUTOMATA/crypto-regime-spike/crypto-regime-spike-money-hypoth-phaseB-2026-07-03.md` |

## Skipped (already covered by an existing standard)

| practice | covered-by | source |
|---|---|---|
| Split truth-layer (deterministic scripts own numbers, quotes, tag-integrity) from meaning-layer (LLM only interprets); numbers reach the deliverable only via synthesis JSON | evidence-grounded-synthesis.md | `C:/work/rejuve/.claude/rules/analytics-pipeline.md`, `C:/work/rejuve/.claude/rules/distillation-pipeline.md`, `C:/dev/POS/.claude/rules/extraction-pipeline-standard.md` |
| Attach source + verbatim quote + confidence label to every factual claim; no source = assumption, not a finding | evidence-grounded-synthesis.md | `C:/work/rejuve/.claude/rules/evidence-rules.md`, `C:/dev/invest-research/.claude/rules/research-standards.md`, `C:/dev/h2t-business/.claude/rules/research-validation.md` |
| Read a document's actual content before citing it; grep the codebase for a name/number/quote before asserting it exists | evidence-grounded-synthesis.md | `C:/work/rejuve/.claude/rules/evidence-rules.md`, `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/project_tracker_lags_code.md` |
| Reuse a canonical source-agnostic harness/template for new extraction or research pipelines instead of reinventing per-source | research-pipeline-runbook.md | `C:/dev/POS/.claude/rules/extraction-pipeline-standard.md`, `C:/work/rejuve/.claude/rules/research-execution.md` |
