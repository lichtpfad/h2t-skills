# h2t-dev Changelog

## Unreleased

- fix(docs-index): collect section docs recursively — a nested document now gets its
  own link instead of a link to the directory it lives in, which the orphan BFS treats
  as a dead end
- fix(docs-index): link loose `docs/*.md` and nested `README.md`/`index.md`; only
  `docs/README.md` itself stays out of the index
- fix(docs-index): honour `exclude_dirs` — frozen trees are no longer indexed
- fix(docs-lint): narrow `_safe_generate`'s fallback to `ImportError`; any other error
  used to replace a live index with a two-line stub on `--apply`
- feat(milestone-closure): add gh-api dry-run backend and structured closure report
- docs(milestone-closure): replace standalone docs-index/docs-cleanup flow with unified docs-lint

## 1.0.8 — 2026-05-27
- feat(lifecycle-os): demote docs-init, docs-sync-labels, docs-cleanup, docs-index to CLI-only (SKILL.md removed)
- chore: update plugin description to reflect lifecycle pipeline architecture

## 1.0.7 — 2026-05-27
- feat(milestone-closure): add docs-cleanup preview gate + docs-index rebuild steps

## 1.0.6 — 2026-05-27
- feat(docs-lint): add legacy-dirs, naming-conventions, repo-root, data-docs checks + --fix-labels flag

## 1.0.5 — initial
- Initial plugin release
