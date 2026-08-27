---
title: API Contracts
date: "2026-04-13"
---
# API Contracts

Standard for repos that expose a public API.

## Applicability

Only applies to repos where `projects.yaml` indicates API exposure (i.e. `docs.agent_docs = true` or repo has `api/openapi.yaml`). Currently: `h2t-graphs`, `h2t-evals`.

## File Locations

```
api/
├── openapi.yaml      # OpenAPI 3.x spec (primary contract)
└── schemas/          # JSON Schema definitions reused across endpoints
```

- `api/openapi.yaml` is the single source of truth for the HTTP contract
- `api/schemas/` contains standalone JSON Schemas referenced from `openapi.yaml` via `$ref`
- Do NOT put specs or schemas in `docs/`

## Versioning

- Version field in `openapi.yaml` follows semver: `version: "0.3.1"`
- Patch: non-breaking additions (new optional fields, new endpoints)
- Minor: after live confirmation only (see global semver policy in CLAUDE.md)
- Breaking changes require a new major version and migration notes in `docs/client/`

## Backward Compatibility Rules

1. Never remove or rename a field without deprecation notice
2. New required request fields are breaking changes (minor or major bump)
3. New optional response fields are non-breaking (patch)
4. Deprecate with `deprecated: true` in OpenAPI, keep for one minor version

## Client Documentation

When `api/openapi.yaml` exists:

- `docs/client/api-guide.md` must link to `api/openapi.yaml`
- `docs/client/quickstart.md` must include a minimal working example
- `docs/client/README.md` is the entry point for integrators

## Validation

- CI (when present) should lint `api/openapi.yaml` with a Python-based validator (no Node.js)
- Schemas in `api/schemas/` validated against JSON Schema draft-2020-12
