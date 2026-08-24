# h2t-dev Changelog

## Unreleased

- feat(docs-lint): `retire` — list open plans/specs older than N days with their
  evidence (age, commits touching the file since it was written), and `--apply`
  to `git mv` them into `docs/archive/`. The only sub-command that lowers the
  debt count; every other one measures form. Deliberately manual: both automatic
  closing signals were measured here and failed — a plan slug appears in 7 of 60
  merged PR bodies, and 47 of 140 documents were created in one commit and never
  touched again, which does not separate "done and never updated" from
  "abandoned". Writing `status: done` on that would be a guess put in the file

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
