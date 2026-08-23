# Linting Rules

## Python

Use `ruff`. No `pylint`, no `flake8`.

The rule set is **pinned** in `pyproject.toml`: `select = ["E4", "E7", "E9", "F", "I", "UP"]`.
Ruff's own default is not a set anyone chose — 0.16.4 enables 413 rules and reported 1625
findings here, nearly all on untouched files, which turned every finding into "mine or
pre-existing?" instead of a signal. The CI step pins the ruff version too, for the same
reason: an unpinned linter adds rules on its own schedule.

The repo is at **zero findings** under that set (2026-08-24). A red line is therefore yours.

`ignore` in `pyproject.toml` carries a comment per class saying why it is deferred; the classes
are tracked in #400. Read the comment before lifting one.

`F401` is handled differently and the difference matters. It is **not** in `ignore` and not in
`per-file-ignores`: both suppress the rule for a whole file, so a newly added unused import
would pass unnoticed in any file that already had one. The 99 pre-existing ones carry a
line-level `# noqa: F401` instead, so the rule stays live everywhere else in the same file.
Verified: appending an unused import to a file full of noqa'd ones still fails.

Those noqa markers are the debt (#400), not a pattern to copy. `F401` is also `unfixable` —
several modules re-export names purely so tests can patch them, and `ruff --fix` removing
those took 14 tests down.

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

Verified 2026-08-23: it prints a report and **exits 1 whenever there are findings**
(`lint.py:987`) — the current checkout has 50 orphans, 32 naming, 6 structure, 39 metadata and
12 project issues, so `doctor` exits 1 here even though it prints `status: ok`. Do not treat a
non-zero exit as a broken command, and do not gate a step on `doctor` exiting 0 until those
findings are cleared. Wherever a plan or rule says `docs-lint <subcommand>`, that is the
script, not a binary.

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
