---
title: Code Organization
date: "2026-04-13"
---
# Code Organization

Standard directory layout for h2t-* repos.

## Top-Level Structure

```
{repo}/
├── src/              # Python packages
├── tests/            # Test suite
├── api/              # API contracts
├── scripts/          # Utility scripts
├── data/             # Reference data, JSON registries
├── tools/            # Dev tooling
└── docs/             # Documentation (see documentation-structure.md)
```

## src/

Python packages only. No scripts, no data files.

```
src/
└── h2t_{name}/       # Main package (e.g. h2t_evals, h2t_graphs)
    ├── __init__.py
    └── ...
```

Examples: `src/h2t_evals/`, `src/h2t_graphs/`

## tests/

Mirrors `src/` structure. Each module has a corresponding test file.

```
tests/
├── unit/             # Unit tests (mirrors src/ tree)
├── integration/      # Integration tests
└── fixtures/         # Test data, shared fixtures
```

## api/

Only present in repos with a public API.

```
api/
├── openapi.yaml      # OpenAPI 3.x spec
└── schemas/          # JSON Schema definitions
```

See `api-contracts.md` for full rules.

## scripts/

Standalone utility scripts. Not importable packages.

- Naming: `kebab-case.py` or `kebab-case.sh`
- Each script must have a docstring or `--help`
- Validation scripts referenced from `linting.md` live here

## data/

Reference data and JSON registries that belong to the domain but are not code.

- Operator registries (h2t-ai)
- Static lookup tables
- Configuration templates

Rule: if a directory in `docs/` is more than 80% non-markdown, move it to `data/`.

## tools/

Dev tooling that is not part of the deployed package: code generators, migration helpers, benchmarks.

## Rules

- No `pip install` without an active `.venv`
- Never put JSON data files in `docs/`
- Never put test fixtures in `src/`
- `scripts/` contains scripts, not libraries — no cross-imports between scripts
