# Linting Rules

## Python

Use `ruff`. No `pylint`, no `flake8`.

The rule set is **pinned** in `pyproject.toml`: `select = ["E4", "E7", "E9", "F", "I", "UP"]`.
Ruff's own default is not a set anyone chose — 0.16.4 enables 413 rules and reported 1625
findings here, nearly all on untouched files, which turned every finding into "mine or
pre-existing?" instead of a signal. The CI step pins the ruff version too, for the same
reason: an unpinned linter adds rules on its own schedule.

The repo is at **zero findings** under that set (2026-08-24). A red line is therefore yours.

There is **no `ignore`**. E702/E701/E741/UP035 sat there until 2026-08-24 on a cost estimate
that turned out to be wrong by an order of magnitude — "117 findings" was read as a large diff,
and they were in 23 files, three of which held 68 of them. A rule parked in `ignore` is off for
the whole repo, so nothing was catching the next one. Prefer clearing a class to deferring it;
if you must defer, say in the comment what you measured.

Suppression has three scopes and they are not interchangeable. `ignore` kills a rule repo-wide.
`per-file-ignores` kills it for whole files — earned only where the file's shape forces it
(`E402` where a `sys.path.insert` must precede an import). A line-level `# noqa` is the narrow
one, and the only one that leaves the rule live elsewhere in the same file.

`F401` uses the third, and never the first two: a whole-file suppression would let a newly
added unused import pass unnoticed in any file that already had one. The 101 markers were
resolved import by import (#400); **six** remain, each with the reason on its own line.

**The known gap is narrower than it was written here.** A `noqa` covers the statement it sits
on, so `from typing import Any, Dict  # noqa: F401` does swallow a third unused name added to
that line. But measured 2026-08-24: in the *parenthesised* form, ruff anchors the marker to the
individual name's line — a planted `now_iso` on the next line inside an already-marked
`from recovery import (...)` was still reported. So the gap is a property of single-line
multi-name imports only. All six surviving markers are single-name statements, with nothing to
hide behind them.

`F401` stays `unfixable`. Several modules re-export names purely so tests can patch them, and
`ruff --fix` across the repo removed those and took 14 tests down. The safe way to clear a
batch is `uvx ruff check --isolated --select F401 --fix <explicit file list>` — `--isolated` is
what bypasses `unfixable`, and the vetted list is what keeps an interface from being deleted.

Run the **same paths CI runs**, or a clean local check will still fail on the runner:

```
C:/dev/h2t-skills/.venv/Scripts/ruff check plugins/ lib/ h2t_ops/ tests/ scripts/   # Windows
uvx ruff check plugins/ lib/ h2t_ops/ tests/ scripts/                               # macOS
```

CI pins the version (`pipx run ruff==0.16.4`); `uvx ruff` locally may be newer. If a finding
appears locally and not in CI, compare `ruff --version` before assuming it is real.

## Markdown

`docs-lint` for docs structure and frontmatter. `.pymarkdown.yaml` rules apply to all
`docs/**/*.md`.

There is **no `docs-lint` command** — this repo ships no such entry point, and `uv run
docs-lint` fails with "Failed to spawn". It is a plugin skill script, invoked the way the
skill invokes it:

```
.venv/bin/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor
```

It prints a report and **exits 1 whenever there are findings** (`lint.py:1060`), so `doctor`
exits 1 here even though it prints `status: ok`. Do not treat a non-zero exit as a broken
command, and do not gate a step on `doctor` exiting 0 until the findings are cleared.
Wherever a plan or rule says `docs-lint <subcommand>`, that is the script, not a binary.

**The baseline this file used to carry — "50 orphans, 32 naming, 6 structure, 39 metadata,
12 project", verified 2026-08-23 — was the truncated view.** `_DIM_LIMIT = 50` capped every
dimension silently, in the collector shared by `audit`, `plan` and `doctor` alike. The real
count was **136 orphans, 225 findings**. The cap also made the report insensitive to change:
declaring three frozen trees took orphans 136 → 93 and moved the printed number not at all,
which reads exactly like an exclusion setting that does not work.

Fixed 2026-08-24: the cap still bounds the printed list, but each capped dimension emits a
`truncated` finding carrying `total` and `shown`, and `audit` prints `... N more not listed`.
Trust the header count, not the length of the list under it.

Current baseline, same date, with `exclude_dirs` declared in `.claude/rules/docs-lint.yaml`:
**93 orphans, 22 naming, 3 structure, 33 metadata, 1 project.** The 93 are one problem, not
93: `docs/README.md` links 126 targets out of 218 live documents and links `superpowers/` and
`reports/` as *directories*, which the BFS does not follow. `docs-lint fix-index` is the
remedy, and rebuilding that file has not been done.

`exclude_dirs` reaches every walk over `docs/` as of 2026-08-24 — including the `git mv` in
`_apply_misplaced_moves`. Before that it reached two checks out of seven, so a frozen tree
kept producing findings from the five it did not reach (#271).

## Tests

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/        # Windows
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/

.venv/bin/pytest tests/                              # macOS
.venv/bin/pytest tests/docs/
```

Bare `python` is not on PATH on macOS — use `.venv/bin/python` or `python3`. A uv-built venv
ships without `pip`; this checkout's has one only because it was installed by hand, so use
`uv pip install --python .venv/bin/python <pkg>`, which works either way. A red suite there is
usually a missing dependency in that venv rather than a repo defect — CI installs with
`pip install -e .` and sees a different environment.

No `&&` chaining in Bash tool calls (CLAUDE.md constraint).
