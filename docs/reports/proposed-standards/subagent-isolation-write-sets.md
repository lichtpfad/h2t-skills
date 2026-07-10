# Give Every Subagent a Self-Contained Prompt with Disjoint Explicit Write-Sets

**Proposed home:** `C:/dev/docs/standards/subagent-isolation-write-sets.md` (NEW)
**Track:** process · **Recurrence:** 4 lineage(s) · **Domain-independence:** high

## TL;DR
Each subagent dispatch must include: (1) a fully self-contained prompt requiring no external look-ups, (2) an explicit write-set listing the files/dirs it is allowed to modify, (3) a disjoint constraint — no two concurrent subagents may write to overlapping paths, and (4) a chosen write-strategy (subagent-writes vs parent-collects-and-writes) declared before dispatch. After the subagent returns, verify its commit touches only its declared write-set before integrating. This prevents last-write-wins races and scope drift in parallel workflows.

## Evidence (where it was harvested)
- Lineages: POS, rejuve, h2t-skills, crypto-regime-spike
- Source files:
  - `C:/dev/POS/.claude/rules/governance.md`
  - `C:/work/rejuve/.claude/rules/research-execution.md`
  - `C:/Users/stani/.claude/projects/C--dev-h2t-skills/memory/reference_subagent_context_inheritance.md`

## Notes for operator
Highest recurrence (4 lineages) and high domain-independence — this is ready to lift immediately. The write-strategy choice (subagent-writes vs parent-writes) is a nuance worth keeping; it prevents a common orchestration ambiguity.
