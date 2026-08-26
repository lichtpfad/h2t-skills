---
title: "h2t-ops Deploy Design"
status: "draft"
owner: "lichtpfad"
date: "2026-05-25"
milestone: ""
---
# h2t-ops Deploy Design

Date: 2026-05-26
Issue: #183
Status: draft

## Purpose

Add a unified `h2t-ops deploy` surface so agents can deploy registered services
without hardcoding target-specific mechanics into the CLI.

This is an operator workflow surface, not a connector task.

## Core decision

V1 should be **profile-driven**, not **driver-heavy**.

That means:
- Python owns registry loading, validation, script execution, and output normalization
- deploy mechanics live in YAML profiles plus script bundles
- adding a new platform should usually not require changing Python code

This is a better fit for the real deployment landscape:
- some targets use SSH
- some use GitHub Actions
- some use panel/upload flows
- some may use hooks or platform CLIs later

## Problem

Today deploy knowledge is fragmented:

- `docs/vps/deploy.sh`
- GitHub Actions workflow conventions
- hosting-specific manual steps
- machine-local runbooks

That works for a human who already knows the target system. It is not a stable
surface for agents. An agent should be able to say "deploy `h2t-graphs` to
`arvixe-prod`" without embedding Arvixe-specific logic into Python.

## Product goal

Provide one stable CLI surface:

```text
h2t-ops deploy <service> [--target <target-name>] [--dry-run] [--json]
h2t-ops deploy list
h2t-ops deploy status <service> [--target <target-name>] [--json]
```

The CLI resolves:

```text
service -> target -> profile -> script contract
```

Then it executes the profile-defined script and returns a standard envelope.

## Scope

### In scope for v1

- `deploy <service>`
- `deploy list`
- `deploy status <service>`
- service registry in `~/.h2t/config/deploy/services.yaml`
- profile registry in `~/.h2t/config/deploy/profiles.yaml`
- script-bundle execution contract
- `--dry-run`
- `--json`
- 2–3 initial profiles, for example:
  - `ssh-shell`
  - `github-actions-dispatch`
  - `arvixe-upload` if Arvixe is not just SSH

### Out of scope for v1

- rollback
- live log streaming
- approval orchestration
- multi-target fanout
- secrets provisioning
- automatic platform discovery
- health checks beyond profile-defined `status`
- replacing every deploy profile with native Python implementations

## Architecture

## CLI role

`h2t-ops deploy` should be a thin orchestrator.

Python responsibilities:
- load service registry
- load profile registry
- validate required inputs
- resolve env vars
- execute the configured script
- normalize result to a standard envelope

Python should not own Arvixe-specific, VPS-specific, or GitHub-specific deploy
logic beyond the generic executor contract.

## Module layout

```text
h2t_ops/deploy/
  models.py
  registry.py
  profiles.py
  executor.py
  commands.py
```

Reason:
- deploy is a separate operator surface
- config/profile execution is the primary abstraction, not connector drivers

## Data model

### Service registry

```python
@dataclass(frozen=True)
class DeployTargetBinding:
    name: str
    profile: str
    config: dict[str, Any]


@dataclass(frozen=True)
class DeployServiceSpec:
    name: str
    service_type: str
    help: str
    default_target: str
    targets: dict[str, DeployTargetBinding]
```

`service_type` is intentionally separate from `profile`.

Examples:
- `python-web`
- `static-site`
- `worker`

This is metadata for future policy and documentation. V1 does not branch
behavior on `service_type`.

### Profile registry

```python
@dataclass(frozen=True)
class ScriptStep:
    run: str


@dataclass(frozen=True)
class DeployProfileSpec:
    name: str
    contract_version: int
    kind: str                  # script-bundle in v1
    inputs: list[str]
    deploy: ScriptStep
    status: ScriptStep
```

V1 supports only:

```text
kind = "script-bundle"
```

The point of the profile is to describe **how** to deploy a target class, while
the target binding supplies concrete values.

## Abstract extension model

The abstraction boundary is:

1. `DeployServiceSpec`
   - what logical service we are deploying
2. `DeployTargetBinding`
   - where that service is deployed
   - which profile it uses
3. `DeployProfileSpec`
   - how that target type is operated
4. `executor`
   - runs the profile script contract

This gives us two independent growth axes:

- new service types without changing the CLI
- new deployment mechanisms without changing the CLI

Examples:
- `h2t-graphs` can have:
  - `arvixe-prod` via `arvixe-upload`
  - `github-preview` via `github-actions-dispatch`
- another service can deploy to VPS via `ssh-shell`

The CLI must stay blind to the mechanism. It only resolves and executes.

## Config contract

## Service registry file

Source of truth:

```text
~/.h2t/config/deploy/services.yaml
```

Example:

```yaml
services:
  h2t-graphs:
    service_type: static-site
    help: h2t-graphs landing
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: arvixe-upload
        config:
          host: ${ARVIXE_HOST}
          user: ${ARVIXE_USER}
          remote_path: /home/.../public_html/h2t-graphs
          local_path: C:/dev/h2t-graphs/dist

      github-preview:
        profile: github-actions-dispatch
        config:
          repo: lichtpfad/h2t-graphs
          workflow: deploy-preview.yml
          ref: main
```

Rules:
- `services` key is required
- service names are unique
- each service defines `service_type`
- each service defines `default_target`
- `default_target` must exist in `targets`
- each target defines `profile`

## Profile registry file

Source of truth:

```text
~/.h2t/config/deploy/profiles.yaml
```

Example:

```yaml
profiles:
  ssh-shell:
    contract_version: 1
    kind: script-bundle
    inputs:
      - host
      - user
      - path
      - service
    deploy:
      run: scripts/deploy/ssh-shell/deploy.ps1
    status:
      run: scripts/deploy/ssh-shell/status.ps1

  github-actions-dispatch:
    contract_version: 1
    kind: script-bundle
    inputs:
      - repo
      - workflow
      - ref
      - service
    deploy:
      run: scripts/deploy/github-actions-dispatch/deploy.ps1
    status:
      run: scripts/deploy/github-actions-dispatch/status.ps1

  arvixe-upload:
    contract_version: 1
    kind: script-bundle
    inputs:
      - host
      - user
      - remote_path
      - local_path
      - service
    deploy:
      run: scripts/deploy/arvixe-upload/deploy.ps1
    status:
      run: scripts/deploy/arvixe-upload/status.ps1
```

Rules:
- `profiles` key is required
- profile names are unique
- `contract_version` is required
- v1 requires `contract_version: 1`
- v1 only supports `kind: script-bundle`
- `deploy.run` and `status.run` are required
- `inputs` is the validation contract for target-local config

## Script contract

This is the key boundary for v1.

Every deploy/status script must:
- accept one canonical structured payload
- return JSON to stdout
- exit non-zero on failure

### Canonical input transport

V1 uses one fixed input mechanism:

- Python writes one resolved JSON payload file
- Python passes its path in:
  - `H2T_DEPLOY_INPUT_JSON`

Scripts must read that file and must not require profile-specific positional
arguments.

Optional fixed env vars may also be provided for convenience:
- `H2T_DEPLOY_ACTION` = `deploy` | `status`
- `H2T_DEPLOY_DRY_RUN` = `true` | `false`

But the JSON file is the source of truth.

Example payload:

```json
{
  "service": "h2t-graphs",
  "service_type": "static-site",
  "target": "arvixe-prod",
  "profile": "arvixe-upload",
  "action": "deploy",
  "dry_run": true,
  "config": {
    "host": "example.host",
    "user": "deploy",
    "remote_path": "/home/.../public_html/h2t-graphs",
    "local_path": "C:/dev/h2t-graphs/dist"
  }
}
```

### Required success envelope

```json
{
  "ok": true,
  "provider": "deploy",
  "result": {
    "service": "h2t-graphs",
    "target": "arvixe-prod",
    "status": "deployed",
    "duration_s": 12.4,
    "details": {
      "profile": "arvixe-upload"
    }
  }
}
```

### Required failure behavior

One of:

1. script exits non-zero and writes a useful stderr summary
2. script returns a standard error envelope and exits non-zero

Python normalizes this into the repo’s standard `error_envelope()` shape.

### Status support levels

Not every deployment mechanism has a meaningful health/status primitive.

V1 therefore allows three status classes from scripts:

- `healthy`
- `failed`
- `unknown`

And one explicit capability fallback:

- `unsupported`

Rule:
- if a profile cannot provide meaningful status, its script must return:
  - `status: "unsupported"`
  - a short reason in `details.reason`

That is preferred over inventing fake health semantics.

## Execution contract

V1 executor behavior:

1. resolve service
2. resolve target (or use default)
3. resolve profile
4. validate required `inputs`
5. expand env placeholders
6. run the profile’s script
7. normalize JSON output

The executor is responsible for materializing the resolved JSON payload file and
passing its path via `H2T_DEPLOY_INPUT_JSON`.

### Dry-run semantics

`deploy --dry-run` must not perform the deploy.

In v1 that means:
- Python passes `dry_run=true` into the script contract
- the profile script returns the resolved action it would execute

Example `details` for dry-run:

```json
{
  "profile": "github-actions-dispatch",
  "resolved_command": "gh workflow run deploy.yml -R lichtpfad/h2t-evals -f service=h2t-evals",
  "mode": "dry_run"
}
```

## Profile examples

### `ssh-shell`

Use when deployment is fundamentally:
- connect to a machine
- run a shell command there

Typical targets:
- VPS
- any SSH-accessible box

This profile may internally do:
- `ssh user@host "cd <path> && bash docs/vps/deploy.sh <service>"`

### `github-actions-dispatch`

Use when deployment is already modeled as a workflow trigger.

Typical targets:
- service repos with `workflow_dispatch`
- preview/prod workflows living in GitHub Actions

### `arvixe-upload`

Use only if Arvixe deploy is operationally distinct from plain SSH deploy.

Examples:
- file upload / sync workflow
- hosting-panel-shaped flow
- rsync/SFTP publish flow

If later we discover Arvixe is just SSH with a different path, this profile can
be removed and the target can move to `ssh-shell` without changing the CLI.

## Why profiles instead of Python drivers

1. new platforms can be added mostly in config + scripts
2. the LLM can reason over declarative profiles
3. the CLI stays small and stable
4. hosting-specific mechanics do not leak into the command surface

Native Python drivers can be added later only when a profile family becomes
stable enough to justify hardening in code.

## UX rules

- `deploy list` must not require network access
- `deploy <service>` without `--target` uses `default_target`
- `deploy status <service>` without `--target` uses `default_target`
- `--json` is the stable machine contract
- human output should stay concise

## Acceptance criteria

`#183` is ready to implement when this spec is accepted with these constraints:

1. CLI surface is exactly:
   - `deploy <service>`
   - `deploy list`
   - `deploy status <service>`
2. config is split into:
   - `services.yaml`
   - `profiles.yaml`
3. deploy code lives in `h2t_ops/deploy/`
4. v1 uses profile-driven script execution, not many hardcoded Python drivers
5. `--json` and `--dry-run` are mandatory
6. `service -> target -> profile -> script` is the canonical resolution path
7. no rollback, approval orchestration, or log tailing in v1
8. script input transport is fixed via `H2T_DEPLOY_INPUT_JSON`
9. profiles that cannot provide status must return `unsupported`, not fake health
10. at least one real profile must be validated end-to-end with:
   - one real `deploy --dry-run`
   - one real `status`
   - and recorded evidence

## Recommended next step

Write a short implementation plan that splits work into:

1. models + two registry loaders
2. executor + JSON normalization
3. CLI wiring
4. one reference profile end-to-end
5. tests + dry-run evidence
