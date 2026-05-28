# TODOS

Backlog items captured during plan reviews and implementation. Do not mix with active plan tasks.

---

## docs-init

### Template validation for programmatic callers

**What:** Add `if template not in TEMPLATE_EXTRA_DIRS: raise ValueError(f"Unknown template: {template!r}")` at the top of `init_repo()`.

**Why:** CLI calls are protected by `choices=[...]`. Programmatic calls (e.g., future callers beyond scaffold_project.py) silently write `template: bad_value` into `.claude/rules/docs-lint.yaml`, creating dead config.

**How to apply:** Add 2-3 lines to `plugins/h2t-dev/skills/docs-init/scripts/init.py` + 1 test `test_init_repo_raises_on_bad_template` in `tests/docs/test_docs_init_repo_root.py`.

**Depends on:** Task 1 of #196 (init.py already being modified).

---

### Idempotency test

**What:** Add `test_init_repo_is_idempotent` — call `init_repo` twice on the same path, verify `changes == []` on the second call.

**Why:** `init_repo` has `if not X.exists():` guards, but the new `docs-lint.yaml` path is not covered by any idempotency test. A future edit removing an exists-guard would silently break idempotency.

**How to apply:** Add to `tests/docs/test_docs_init_repo_root.py` alongside existing tests.

**Depends on:** Task 1 of #196.

---

## milestone-closure / docs-init

### Safety guard for arbitrary --repo-root paths

> **Note:** Basic safety guard (home dir + root path) was added in #196 per D5 amendment.
> This TODO captures the more thorough version: depth check, DEV_ROOT parent check, symlink resolution.

**What:** Extend the safety guard in `init_repo()` to also reject: paths that are parents of `DEV_ROOT`, paths with depth < 3 (too shallow to be a project), and paths that are symlinks pointing outside the intended tree.

**Why:** The #196 guard blocks obvious mistakes (home dir, drive root). A path like `C:/dev` (the DEV_ROOT itself) would still pass the #196 guard. A second-level guard would catch `--repo-root C:/dev` and similar.

**How to apply:** Extend the `_DANGER` check in `init_repo()`. Add test `test_init_repo_rejects_dev_root_itself`.

---

## milestone-closure / closure.py

### GitHub milestones pagination

**What:** `fetch_milestones` calls `gh api repos/{owner}/{repo}/milestones -f state=all`. GitHub returns up to 100 milestones per page. Repos with >100 milestones silently miss targets beyond page 1.

**Why:** Codex identified this as an unaddressed edge case. Current repos are safe (< 100 milestones), but it's a silent failure mode.

**How to apply:** Add `-f per_page=100` to the fetch call, and if result count == 100, follow Link header for pagination. Or: use `gh api --paginate` flag.

**Depends on:** None — independent fix.
