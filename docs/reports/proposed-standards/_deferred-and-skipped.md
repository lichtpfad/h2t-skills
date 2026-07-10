# Deferred (stage 2) and skipped findings

## Deferred to code/skill (natural home is not a guidebook)

| practice | verdict | lineages | source |
|---|---|---|---|
| Deploy plugin changes via commit → git push → marketplace update → reload (never update-plugin.sh as final) | `deferred:code` | h2t-skills | `C:/dev/h2t-skills/.claude/rules/plugin-deploy.md` |
| Two-gate verdict split (research-support × freeze-readiness) with label-efficient judge calibration + dormant-until-N-cal activation | `deferred:code` | quant-kb | `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-quant-kb-plan16-two-gate-verdict-2026-07-10.md` |
| LLM-extraction model/config benchmarking (extract × judge cross-model, harness-floor vs raw-codex token cost, faithfulness-gate insures cheap models, per-stage routing table) | `deferred:code` | quant-kb | `C:/Users/stani/.h2t/sessions/AUTOMATA/quant-kb/quant-kb-ingest-model-benchmark-2026-07-09.md` |
| Fail-closed verdict emission (mde=None never KILL, capacity=False never TRADEABLE, INCONCLUSIVE is acceptable; machine only filters, never a false GO) | `deferred:code` | crypto-regime-spike | `C:/Users/stani/.h2t/sessions/AUTOMATA/crypto-regime-spike/dev-crypto-regime-spike-adjudication-wiring-2026-06-25.md` |
| Sealed schema-validator for a non-code artifact (deterministic structure + source-path existence check keeps an interpretive/LLM output honest) | `deferred:code` | h2t-skills | `C:/dev/h2t-skills/docs/superpowers/plans/2026-07-10-cross-repo-practice-harvest.md` |
| PreToolUse structure-guard enforcement (block file writes to forbidden names/unregistered dirs before write; preventive not reactive validation) | `deferred:code` | h2t-skills | `C:/dev/h2t-skills/docs/superpowers/plans/2026-06-14-lifecycle-os-v2-structure-guard.md` |
| Deterministic structural graph import: extract-once-granularly (pre-judge) vs curated selection (post-judge); node-ID contract; idempotent bulk REST import | `deferred:code` | POS | `C:/dev/POS/docs/superpowers/plans/2026-06-07-meeting-graph-v0-3.md` |

| practice | verdict | lineages | source |
|---|---|---|---|
| Run a codex review-gate after every plan checkpoint and before any completion claim | `deferred:skill` | crypto-regime-spike, quant-kb, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/execution-protocols.md` |
| Gate autonomous-run completion behind a multi-lens council (codex + >=2 Opus lenses) capped at 3 fix iterations, verdict SOUND before handoff | `deferred:skill` | crypto-regime-spike, quant-kb, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/execution-protocols.md` |
| Carry a durable autonomous-execution runbook that survives compaction: pipeline steps as checkboxes, always end on handoff even when BLOCKED | `deferred:skill` | crypto-regime-spike, h2t-skills | `C:/dev/crypto-regime-spike/.claude/rules/autonomous-execution-runbook.md` |
| End sessions with a durable handoff record (not a chat summary), and route reusable discoveries to a persistent backlog rather than the session-snapshot | `deferred:skill` | claudeworking, rejuve, crypto-regime-spike | `C:/work/claudeworking/.claude/rules/session.md` |
| Route all provider I/O (Drive, Gmail, Calendar, Notion, Telegram, MeetGeek) through the h2t-ops connector, never guessing flags or using raw APIs | `deferred:skill` | h2t-skills | `C:/dev/h2t-skills/.claude/rules/connectors.md` |
| Preserve the user's query language in neural/Exa searches; do not translate a Russian/non-English query to English | `deferred:skill` | h2t-skills | `C:/Users/stani/.claude/projects/C--dev-h2t-skills/memory/feedback_preserve_query_language.md` |
| Log non-obvious findings immediately during the session (into a persistent register) rather than waiting for end-of-session | `deferred:skill` | rejuve | `C:/work/rejuve/CLAUDE.md` |
| KB three-layer WikiPattern (raw sources / wiki prose+YAML frontmatter / schema) with source_quality counts + append-only ingest log | `deferred:skill` | crypto-regime-spike, quant-kb | `C:/dev/crypto-regime-spike/docs/superpowers/specs/2026-06-13-quant-kb-design.md` |
| Human-in-loop template+prompt methodology pipeline (each step = template.md + prompt.md; deterministic Python side-utilities gate ID-chaining; expert validates content) | `deferred:skill` | h2t-business, client-auto | `C:/dev/h2t-business/docs/superpowers/plans/2026-07-08-course-design-framework.md` |

## Skipped (already covered by an existing standard)

| practice | covered-by | source |
|---|---|---|
| Split truth-layer (deterministic scripts own numbers/quotes/tag-integrity) from meaning-layer (LLM only interprets); numbers reach deliverable only via synthesis JSON | `evidence-grounded-synthesis.md` (truth/meaning separation already documented) | `C:/work/rejuve/.claude/rules/analytics-pipeline.md` |
| Attach source + verbatim quote + confidence label to every factual claim; no source = assumption, not a finding | `evidence-grounded-synthesis.md` (core claim-sourcing rule) | `C:/work/rejuve/.claude/rules/evidence-rules.md` |
| Read a document's actual content before citing it, and grep the codebase for a name/number/quote before asserting it exists; labels in manifests/CLAUDE.md can lie | `evidence-grounded-synthesis.md` (verification-before-assertion rule) | `C:/work/rejuve/.claude/rules/evidence-rules.md` |
| Reuse a canonical source-agnostic harness/template for new extraction or research pipelines instead of reinventing per-source; keep safety/validation sections verbatim | `research-pipeline-runbook.md` (pipeline reuse and adapter pattern already covered) | `C:/dev/POS/.claude/rules/extraction-pipeline-standard.md` |
| Research-intake / retrieval pipeline: collection-mode funnel (pilot-STOP preflight, band-check, source-eval, fail-loud, evidence per claim) | `research-pipeline-runbook.md` (v1.5 already encodes this funnel) | `C:/work/claudeworking/docs/superpowers/plans/2026-07-04-grants-research-phase1.md` |
| Autonomous durable-runbook spine (survives compaction, resumes from artifact; pipeline steps as checkboxes; gates + decision-protocol embedded; always-handoff terminal) | `h2t-core:autonomous-run skill` (already implemented as a skill, not a guidebook concern) | `C:/dev/crypto-regime-spike/docs/superpowers/plans/2026-07-08-archetype-e-autonomous-runbook.md` |
