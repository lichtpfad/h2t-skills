---
title: "h2t-ops Deploy Implementation Plan"
status: "draft"
date: "2026-05-26"
milestone: ""
---
# h2t-ops Deploy Implementation Plan

Date: 2026-05-26
Issue: #183
Spec: `docs/superpowers/specs/2026-05-25-h2t-ops-deploy-design.md`
Status: draft

## Goal

Implement a profile-driven `h2t-ops deploy` surface with:

- `deploy <service>`
- `deploy list`
- `deploy status <service>`

using:

- `services.yaml`
- `profiles.yaml`
- script-bundle execution via `H2T_DEPLOY_INPUT_JSON`

## Scope

### In scope

- deploy models
- service/profile registry loading
- executor
- CLI wiring
- one reference profile validated end-to-end

### Out of scope

- rollback
- approval orchestration
- live log tailing
- multiple real profiles in the first implementation pass

### Fixed v1 execution assumptions

- profile script paths are **repo-local** in v1
- profiles may reference only paths under:
  - `scripts/deploy/`
- arbitrary absolute script paths are out of scope for v1
- target config values like `local_path` are machine-local operator config, not
  portable repo defaults

Reason:
- keeps the first implementation testable and reviewable
- avoids turning v1 into a generic local-code launcher
- lets us validate one reference profile end-to-end from the repo itself

## Task breakdown

## T0. Baseline audit

Check:
- current CLI command layout in `h2t_ops/cli.py`
- existing output/error envelope helpers
- existing config loader patterns in `h2t_ops/core` and connectors

Acceptance:
- exact insertion points for the new deploy surface are identified
- no deploy code is added under `connectors/`

## T1. Models and registries

Add module tree:

```text
h2t_ops/deploy/
  __init__.py
  models.py
  registry.py
  profiles.py
```

Implement:
- `DeployTargetBinding`
- `DeployServiceSpec`
- `ScriptStep`
- `DeployProfileSpec`

Add loaders for:
- `~/.h2t/config/deploy/services.yaml`
- `~/.h2t/config/deploy/profiles.yaml`

Validation rules:
- required top-level keys exist
- `default_target` resolves
- referenced profile exists
- `contract_version == 1`
- required target-local `inputs` can be validated later by executor

Acceptance:
- unit tests cover valid load + malformed config cases

## T2. Executor contract

Add:

```text
h2t_ops/deploy/executor.py
```

Implement executor responsibilities:

1. resolve service
2. resolve target
3. resolve profile
4. merge/expand config
5. write resolved payload JSON
6. set:
   - `H2T_DEPLOY_INPUT_JSON`
   - `H2T_DEPLOY_ACTION`
   - `H2T_DEPLOY_DRY_RUN`
7. run the configured script
8. normalize stdout JSON
9. map failures into standard error envelope

Executor path rule:
- resolve `deploy.run` / `status.run` relative to repo root
- reject script paths outside `scripts/deploy/`

Required payload shape:

```json
{
  "service": "...",
  "service_type": "...",
  "target": "...",
  "profile": "...",
  "action": "deploy|status",
  "dry_run": true,
  "config": { ... }
}
```

Acceptance:
- executor tests cover:
  - successful JSON result
  - non-zero exit
  - invalid JSON
  - missing required profile input
  - `status: unsupported`

## T3. CLI surface

Wire top-level CLI:

```text
h2t-ops deploy <service> [--target ...] [--dry-run] [--json]
h2t-ops deploy list [--json]
h2t-ops deploy status <service> [--target ...] [--json]
```

Behavior:
- `deploy list` is local-only
- `deploy` and `status` use registries + executor
- human output stays concise
- `--json` returns normalized envelope

`deploy list` output contract:
- service
- service_type
- target
- profile
- whether target is default

Failure semantics:
- if registry/profile config is invalid, `deploy list` fails as a whole
- v1 does not do partial-success row rendering for broken config
- reason: list is also a diagnostic/config inspection surface, so hidden invalid
  rows would be misleading

Human mode should render a compact table.

`--json` should return one entry per target, for example:

```json
{
  "ok": true,
  "provider": "deploy",
  "result": [
    {
      "service": "h2t-graphs",
      "service_type": "static-site",
      "target": "arvixe-prod",
      "profile": "arvixe-upload",
      "is_default": true
    }
  ]
}
```

Acceptance:
- CLI parser tests
- help surface checks
- dispatch tests to executor

## T4. Reference profile

Implement one real reference profile first.

Recommended first profile:
- `github-actions-dispatch`

Reason:
- no SSH assumptions
- easier dry-run
- easier status semantics than arbitrary hosting panels

Before implementation proceeds, select one concrete real fixture:
- one real service
- one real target
- one real workflow name/repo pair

Example shape:
- `h2t-evals` + `github-actions-dispatch`

Deliver:
- example profile entry in fixture config
- one real repo-local script contract under `scripts/deploy/...`
- fixture config for automated tests
- real or mocked `status` mapping:
  - `healthy`
  - `failed`
  - `unknown`
  - `unsupported` if needed

Acceptance:
- one real profile contract exists in the repo
- end-to-end test fixture passes through full profile resolution
- T5 can run against that same real profile contract without redesign

## T5. Dry-run and status evidence

Record one real operational proof for the reference profile:

Minimum:
- one real `deploy --dry-run`
- one real `status`

Evidence should capture:
- service
- target
- profile
- command/result summary
- whether status is `healthy|failed|unknown|unsupported`

Acceptance:
- evidence doc committed in `docs/reports/`

## T6. Roadmap and issue sync

After implementation and evidence:
- update roadmap if `#183` moves from design to implementation/proof
- add issue comment summarizing:
  - landed CLI surface
  - reference profile implemented
  - remaining follow-up for additional profiles

## Commit hygiene

The worktree may contain unrelated doc churn. For `#183` execution:

- stage only deploy-related code, tests, and `#183` docs
- do not use broad `git add .`
- keep evidence/report updates in a separate, explicit commit when practical
- verify `git diff --cached --stat` before each commit
- treat unrelated modified `docs/superpowers/*` and `uv.lock` as read-only
  background state unless a specific `#183` task explicitly owns them

## Test strategy

### Required automated tests

- model tests
- config loader tests
- executor tests
- CLI parser/dispatch tests

### Required operational validation

- one reference profile end-to-end
- dry-run proof mandatory
- status proof mandatory

## Order of execution

Recommended order:

1. T0 baseline audit
2. T1 models and registries
3. T2 executor
4. T3 CLI
5. T4 reference profile
6. T5 evidence
7. T6 sync

## Closure rule

`#183` should not close on architecture alone.

It closes only when:
- CLI exists
- registry/profile contract exists
- executor works
- one reference profile is proven with real dry-run + status evidence
