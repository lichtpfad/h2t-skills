---
name: deploy
description: "Operator deploy surface for registered services via `h2t-ops deploy`. Use for deploy list, dry-run, status, and service-target deploy execution. Profile-driven: service -> target -> profile -> script. Current reference profile: github-actions-dispatch."
compatibility: "Requires `h2t-ops` CLI with local deploy registry under ~/.h2t/config/deploy/services.yaml and profiles.yaml. V1 supports repo-local profile scripts under scripts/deploy/ only."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:deploy

Use this skill for operator deploy workflows exposed through:

```bash
h2t-ops deploy <service> [--target <target>] [--dry-run] [--json]
h2t-ops deploy list [--json]
h2t-ops deploy status <service> [--target <target>] [--json]
```

This is not a connector skill. It is an operator/runtime surface.

## Boundary

- Use `h2t-ops deploy` only for registered services.
- Do not invent deploy commands ad hoc when a service is missing from the registry.
- Do not hardcode host/platform logic into the agent response when the profile can own it.
- Missing deploy coverage becomes config work or a repo issue, not shell improvisation.
- Prefer `--dry-run` before any real deploy unless the user explicitly wants execution.
- Do not mutate unrelated local config under `~/.h2t/config/`.

## Local Config Contract

Deploy registry lives in:

- `~/.h2t/config/deploy/services.yaml`
- `~/.h2t/config/deploy/profiles.yaml`

Current local bootstrap example:

- service: `h2t-graphs`
- target: `github-actions-main`
- profile: `github-actions-dispatch`

V1 profile scripts are repo-local only:

- `scripts/deploy/...`

Absolute external script paths are out of scope.

## Current V1 Semantics

Profile resolution path:

```text
service -> target -> profile -> script
```

Current proven profile:

- `github-actions-dispatch`

Status semantics for that profile are explicit:

- `deploy status` reports the **latest matching workflow run**
- match key:
  - `repo`
  - `workflow`
  - `ref`
- this is surfaced in JSON as:
  - `details.status_scope = latest_matching_workflow_run`

This is honest but not the same as deploy-run correlation by run id.

## Required Workflow

1. Start with:

```bash
h2t-ops deploy list --json
```

2. Confirm the service and target exist.
3. For any risky action, run:

```bash
h2t-ops deploy <service> --dry-run --json
```

4. Inspect:
   - `profile`
   - `target`
   - `resolved_command` or profile details
5. Only then run the real deploy if the user clearly asked for execution.
6. For post-deploy verification, run:

```bash
h2t-ops deploy status <service> --json
```

7. Report:
   - service
   - target
   - profile
   - status
   - any explicit scope limitation from `details`

## Safety Rules

- Default to `--json` for agent processing.
- Default to `--dry-run` before real deploy.
- If `deploy list` fails, stop and fix config instead of bypassing the registry.
- If `status` is `unknown` or `unsupported`, say that directly.
- Do not claim a deploy succeeded based only on dry-run output.
- Do not describe `latest_matching_workflow_run` as a deploy-specific run id.

## Typical Commands

```bash
h2t-ops deploy list --json
h2t-ops deploy h2t-graphs --dry-run --json
h2t-ops deploy status h2t-graphs --json
```

## Output Policy

- Keep human summaries concise.
- Preserve service / target / profile names verbatim.
- For JSON results, retain `details.status_scope` when present.
- Do not paste secrets, tokens, SSH keys, webhook URLs, or raw secret-bearing config.

## Failure Handling

- `config` error:
  - registry/profile/config problem
- `not_found` error:
  - unknown service / unknown target / missing script
- `provider` error:
  - profile script or external platform failure

If a requested service is not registered, do not freehand the deploy. Say that the
service is missing from deploy registry and needs a target/profile entry.
