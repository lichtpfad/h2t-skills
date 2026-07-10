# Detect and Unlink Directory Junctions Before Recursive Delete on Windows

**Proposed home:** `C:/dev/docs/standards/windows-junction-cleanup.md` (NEW)
**Track:** process · **Recurrence:** 1 lineage(s) · **Domain-independence:** high

## TL;DR
Before any `Remove-Item -Recurse` on Windows, inspect the target for directory junctions (reparse points). Unlink each junction with `Remove-Item` (non-recursive, reparse-point only) before deleting the tree. Skipping this step causes the recursive delete to follow the junction and destroy the data in the shared or gitignored directory it points to.

## Evidence (where it was harvested)
- Lineages: crypto-regime-spike
- Source files:
  - `C:/dev/crypto-regime-spike/.claude/rules/data-junction-cleanup.md`

## Notes for operator
Single-lineage (recurrence 1), but domain-independence is high — this is a Windows OS hazard that applies to any project using junction-based layouts (e.g. worktrees, symlinked data dirs). Ready to lift as-is; consider adding a detection snippet (PowerShell `Get-Item | Where-Object { $_.Attributes -match 'ReparsePoint' }`).
