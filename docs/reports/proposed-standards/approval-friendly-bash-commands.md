# Keep Bash/Tool Commands Approval-Friendly: One Command Per Call, No Compound Operators

**Proposed home:** `C:/dev/docs/standards/approval-friendly-bash-commands.md` (NEW)
**Track:** process · **Recurrence:** 4 lineage(s) · **Domain-independence:** high

## TL;DR
Every Bash tool call must contain exactly one command — no `&&`, `||`, `|`, `;`, `$()`, or subshell grouping. Dependent steps run as sequential Bash calls. Plans and specs must call out invocations directly (no compound strings). Large tool output must never be post-processed through the shell inline; write a committed script or read the output in a subsequent step. This keeps every action individually approvable and reproducible across shells and permission models.

## Evidence (where it was harvested)
- Lineages: POS, kraken, h2t-skills, crypto-regime-spike
- Source files:
  - `C:/dev/POS/.claude/rules/governance.md`
  - `C:/dev/kraken/.claude/rules/environment.md`
  - `C:/Users/stani/.claude/projects/C--dev-h2t-skills/memory/feedback_no_shell_postprocess_gather.md`

## Notes for operator
Highest recurrence (4 lineages) and high domain-independence. Ready to lift as-is; this rule is already enforced in CLAUDE.md but lacks a standalone standards file that subagents and cross-repo work can reference independently.
