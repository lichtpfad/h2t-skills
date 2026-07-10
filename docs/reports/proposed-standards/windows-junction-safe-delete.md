# Detect and Unlink Directory Junctions Before Recursive Delete on Windows

**Proposed home:** `C:/dev/docs/standards/windows-junction-safe-delete.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
Before any recursive directory removal on Windows, enumerate the target for reparse points (directory junctions) and unlink each junction via `Remove-Item` without `-Recurse` before proceeding. Recursive deletion that passes through a junction will destroy the shared or gitignored data on the other side, not just the junction entry. This is a Windows-specific hazard with no analog on Unix.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/data-junction-cleanup.md`

## Notes for operator
Single-lineage but high domain-independence — the Windows junction hazard is universal, not domain-specific. Ready to lift as-is with minor generalization of the example paths; no crypto-domain context leaks into the rule itself.
