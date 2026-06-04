# Linting Rules

## Python

Use `ruff` for linting and formatting (configured in `pyproject.toml`). No `pylint`, no `flake8`.

```
C:/dev/h2t-skills/.venv/Scripts/ruff check plugins/ lib/ h2t_ops/
```

## Markdown

`docs-lint doctor` for docs structure and frontmatter. `.pymarkdown.yaml` rules apply to all `docs/**/*.md`.

## Tests

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/
```

No `&&` chaining in Bash tool calls (CLAUDE.md constraint).
