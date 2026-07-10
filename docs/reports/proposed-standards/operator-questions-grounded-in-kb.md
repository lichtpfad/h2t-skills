# Ground Operator Decision Questions in Verified KB/Research Before Presenting Options

**Proposed home:** `C:/dev/docs/standards/operator-questions-grounded-in-kb.md` (NEW)
**Track:** process · **Recurrence:** 2 lineage(s) · **Domain-independence:** high

## TL;DR
Before surfacing a decision question to the operator, the agent must first look up the relevant KB or completed research and arrive at a reasoned recommendation. The operator is presented with a recommendation and the evidence behind it, not a raw open question. Reserve the operator's attention for value and calibration sign-off — not for method selection or factual resolution that the KB already settles. Asking the operator to pick between options without first doing KB lookup is a protocol violation.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike, quant-kb
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/execution-protocols.md`
  - `C:/dev/quant-kb/.claude/rules/kb-lookup.md`

## Notes for operator
Ready to lift. Pairs naturally with the KB-routing standard (route-reusable-knowledge-to-kb.md). The two together define a knowledge-first protocol: build the KB, consult it before acting, and only escalate to the operator when the KB genuinely doesn't resolve the question.
