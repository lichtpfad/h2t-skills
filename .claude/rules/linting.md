# Linting Rules

## Python

Use `ruff`. No `pylint`, no `flake8`.

There is **no `[tool.ruff]` section in `pyproject.toml`** and no `ruff.toml`, so ruff runs on
its default rule set — which drifts with the ruff version. Two consequences worth knowing
before acting on a finding: existing code already trips rules the default set enables
(`PLW1510`, `I001`, `TRY004` all fire on files nobody has touched), and a finding on a line
you did not write is pre-existing, not yours to fix. Check with `git stash` before assuming.

```
C:/dev/h2t-skills/.venv/Scripts/ruff check plugins/ lib/ h2t_ops/   # Windows
uvx ruff check plugins/ lib/ h2t_ops/                                # macOS — ruff is not in the venv
```

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
