# h2t-dev Changelog

## Unreleased

- chore: `gh-memory` removed. It had declared itself deprecated since #197 — "Deprecated
  compatibility shim ... prefer h2t-core:session-start and h2t-core:handoff" — and was the
  only skill in the pack carrying `status: deprecated` in its own frontmatter. A shim that
  announces its own obsolescence still occupies a name, still lands in the skill index of
  every session, and still has to be read past. Three tests existed only to assert the
  deprecation text; they go with it (#463)

- chore(pre-merge-check): `compatibility` names git and npx, and states that the skill
  runs against a feature branch rather than main (#464)

- fix: the plugin reaches its own files through `bin/h2t-dev` on PATH instead of
  `CLAUDE_PLUGIN_ROOT`, which the harness never sets in skill bash. Thirteen sites across
  three skills built a path from it — docs-lint 8, milestone-closure 3, github-issues 2 —
  so `"${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"` expanded to
  `/skills/docs-lint/scripts/lint.py` and the skill failed naming the filesystem root.
  Invisible from this checkout, where the documented invocation uses a path from the clone;
  fatal for anyone who installed only the plugin. Measured empty on 2.1.247 and 2.1.160,
  so not version dependent. docs-sync-labels keeps the variable behind its cache-guessing
  fallback and stays tracked as debt (#459)
- fix(docs-lint, docs-index): the repository is resolved with `git rev-parse
  --show-toplevel` before falling back to the name walk. The walk looked for a directory
  whose name is one of sixteen private repositories, so anywhere else it fell through —
  and `lint.py` then returned the cwd. Measured: run from `docs/sub` of a repository not
  on that list, `repo_root` came back as `docs/sub`, and the linter treated a
  subdirectory as the whole repository (#444)

- chore(docs): `TIER_A`/`TIER_B`/`TIER_C` removed — zero readers in the tree, sixteen
  private repository names. `GH` no longer falls back to a Windows install directory: a
  machine without `gh` received a path that cannot exist and failed on exec rather than
  on the missing tool (#434, #444)

- fix(docs-lint, docs-sync-labels, milestone-closure): run through `uv run --no-project
  --with <pkg> python` instead of probing for `~/.h2t/venv`. The installer never created
  that directory — `setup_h2t.py` contains the word `venv` zero times — so the contract
  held only where it had been built by hand (#449)

- feat(standards): the eight standards documents ship inside the plugin, under
  `references/standards/`. They lived only at `C:/dev/docs/standards/` — a path on one
  machine — while every skill and rule that cited them assumed they were readable
  anywhere. Four stale copies scattered inside individual skills were collapsed into the
  one shipped set (#439)

- fix(docs-init): stop writing `C:/dev` into other repositories. The generated
  documentation pointed its readers at a directory that exists on a single Windows
  machine (#450)

- feat(docs-lint): `retire --never-shipped` keeps only candidates with no commit
  that touched the document and code together. Age alone put 111 documents in
  one list here, 42 of which had such a commit; those 42 are a person's to read,
  and the flag is what lets the other 69 move by command without writing a guess
  into a file.

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
