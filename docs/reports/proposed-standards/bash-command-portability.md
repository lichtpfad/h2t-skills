# Keep Bash/Tool Commands Approval-Friendly and Portable

**Proposed home:** `C:/dev/docs/standards/bash-command-portability.md` (NEW)
**Track:** process · **Recurrence:** 4 lineage(s) · **Domain-independence:** high

## TL;DR
One command per Bash call; no compound operators (`&&`, `||`, `|`, `;`, `$()`). Dependent steps run as sequential Bash calls, not chained in one. Never post-process large tool output through the shell. Plans must use direct binary invocations, not shell pipelines. These rules keep commands harness-approvable and portable across Windows/Unix shells.

## Evidence (where it was harvested)
- Lineages: POS, kraken, h2t-skills, crypto-regime-spike
- Source files:
  - `C:/dev/POS/.claude/rules/governance.md`
  - `C:/dev/kraken/.claude/rules/environment.md`
  - `C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory/feedback_no_shell_postprocess_gather.md`

## Notes for operator
Tied for highest recurrence (4 lineages). Partially present in current CLAUDE.md but scattered. A single canonical standard makes it citable in plans and subagent prompts. Ready to lift as-is.
