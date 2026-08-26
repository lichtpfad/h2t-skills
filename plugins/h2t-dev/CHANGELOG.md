# h2t-dev Changelog

## Unreleased

- chore: remove `docs-cleanup`. It sat under skills/ for four months with no
  SKILL.md — demoted to "CLI" in 31395f5 without ever becoming one: no entry
  point, nothing on PATH, no command file, zero references. Its README section
  documented usage that could not run, and its 173 lines held `find_stale_plans`
  plus a git-mv-to-archive — `docs-lint retire`, rebuilt from scratch four months
  later by someone who did not know it was there. Its own reason for never
  firing is the same gap the merge hook closes: `find_implemented_specs` read a
  `status` nobody ever set
- test: `tests/dev/test_no_ghost_skills.py` — every directory under skills/ has a
  SKILL.md or is on a short exception list, and every exception must be
  referenced from outside its own directory. That second assertion is the control
  that would have caught this one

- feat(docs-lint): `retire` — list open plans/specs older than N days with their
  evidence (age, commits touching the file since it was written), and `--apply`
  to `git mv` them into `docs/archive/`. The only sub-command that lowers the
  debt count; every other one measures form. Deliberately manual: both automatic
  closing signals were measured here and failed — a plan slug appears in 7 of 60
  merged PR bodies, and 47 of 140 documents were created in one commit and never
  touched again, which does not separate "done and never updated" from
  "abandoned". Writing `status: done` on that would be a guess put in the file
- fix(docs-lint): `retire` reports commits that touched a document *and* code,
  not just commits. The raw count did not discriminate — the modal value was 2
  and for dozens of files the second commit was one bulk `--fix-frontmatter`
  sweep, a tool touching the file rather than anyone working the plan. The new
  column separates 69 documents nothing ever shipped under from 42 that were
  executed and never marked. The old hint named `0 коммитов`, a value that
  could not occur: the count includes the commit that created the file

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
