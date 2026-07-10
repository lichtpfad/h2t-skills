# Enforce Single-Writer Discipline When Parallel Agents Share a File

**Proposed home:** `C:/dev/docs/standards/single-writer-parallel-agents.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
When parallel judge or worker subagents must contribute to a shared file, they must not each write to it independently. Each agent returns its section as output; the orchestrator collects all outputs and performs a single atomic write. This preserves agent independence and prevents last-write-wins data loss.

## Evidence (where it was harvested)
- Lineages: quant-kb
- Source files:
  - `C:/dev/quant-kb/CLAUDE.md`

## Notes for operator
Single-lineage (recurrence 1), domain-independence is high. The rule is precise and portable to any multi-agent orchestration context. Ready to lift as-is. Naturally cross-references the subagent-dispatch-discipline standard.
