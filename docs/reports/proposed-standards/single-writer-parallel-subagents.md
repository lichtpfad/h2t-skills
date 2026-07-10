# Enforce Single-Writer Discipline When Parallel Subagents Share a File

**Proposed home:** `C:/dev/docs/standards/single-writer-parallel-subagents.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
When parallel judge or worker subagents must contribute to a shared output file, each subagent returns its section as a return value — it does not write to the shared file directly. The orchestrator collects all sections and writes the file exactly once. This preserves subagent independence (no coordination required between agents) while eliminating last-write-wins races. The write-strategy (subagent-writes vs parent-writes) must be declared before dispatch — see also subagent-isolation-write-sets.md.

## Evidence (where it was harvested)
- Lineages: quant-kb
- Source files:
  - `C:/dev/quant-kb/CLAUDE.md`

## Notes for operator
Single-lineage but high domain-independence — the race condition is a structural hazard in any parallel-agent orchestration. Ready to lift. The closest companion is subagent-isolation-write-sets.md (which covers the broader write-set discipline); this file specializes on the single-writer pattern for shared files specifically.
