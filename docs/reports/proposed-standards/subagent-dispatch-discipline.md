# Give Every Subagent a Self-Contained Prompt with Disjoint Write-Sets

**Proposed home:** `C:/dev/docs/standards/subagent-dispatch-discipline.md` (NEW)
**Track:** process · **Recurrence:** 4 lineage(s) · **Domain-independence:** high

## TL;DR
Each dispatched subagent must receive a fully self-contained prompt (no implicit context inheritance assumed) and an explicit, disjoint write-set. After each subagent completes, verify its commits against its declared ownership set before integration. Decide the write strategy (subagent-writes vs parent-collects-and-writes) before dispatch, not after.

## Evidence (where it was harvested)
- Lineages: POS, rejuve, h2t-skills, crypto-regime-spike
- Source files:
  - `C:/dev/POS/.claude/rules/governance.md`
  - `C:/work/rejuve/.claude/rules/research-execution.md`
  - `C:/Users/stani/.claude/projects/C--dev-h2t-skills/memory/reference_subagent_context_inheritance.md`

## Notes for operator
Highest recurrence of any process finding (4 lineages). Ready to lift as-is. The write-strategy decision point is frequently missed — worth calling it out explicitly in the standard header.
