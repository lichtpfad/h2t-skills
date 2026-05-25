# H2T-OPS Deploy Proof

Date: 2026-05-26
Issue: #183
Branch: `codex-deploy-profile-driven`
Status: draft evidence

## Fixture

Real proof used one minimal local deploy registry under `~/.h2t/config/deploy/`:

- service: `h2t-graphs`
- target: `github-main`
- profile: `github-actions-dispatch`
- repo: `lichtpfad/h2t-graphs`
- workflow: `deploy.yml`
- ref: `main`

This fixture was chosen because:

- it is a real repo/workflow pair;
- `status` can be checked live through GitHub Actions;
- `deploy --dry-run` can prove the resolved command without side effects.

## Commands

### 1. `deploy list --json`

Command:

```powershell
uv.exe run h2t-ops deploy list --json
```

Result:

```json
{
  "ok": true,
  "provider": "deploy",
  "result": [
    {
      "service": "h2t-graphs",
      "service_type": "static-site",
      "target": "github-main",
      "profile": "github-actions-dispatch",
      "is_default": true
    }
  ]
}
```

### 2. `deploy h2t-graphs --dry-run --json`

Command:

```powershell
uv.exe run h2t-ops deploy h2t-graphs --dry-run --json
```

Result:

```json
{
  "ok": true,
  "provider": "deploy",
  "result": {
    "service": "h2t-graphs",
    "target": "github-main",
    "status": "dry_run",
    "details": {
      "profile": "github-actions-dispatch",
      "mode": "dry_run",
      "resolved_command": "gh workflow run deploy.yml --repo lichtpfad/h2t-graphs --ref main",
      "repo": "lichtpfad/h2t-graphs",
      "workflow": "deploy.yml",
      "ref": "main"
    }
  }
}
```

### 3. `deploy status h2t-graphs --json`

Command:

```powershell
uv.exe run h2t-ops deploy status h2t-graphs --json
```

Result summary:

- status: `healthy`
- status scope: `latest_matching_workflow_run`
- repo/workflow/ref:
  - `lichtpfad/h2t-graphs`
  - `deploy.yml`
  - `main`
- latest matching run:
  - `databaseId: 24862273506`
  - `conclusion: success`
  - `url: https://github.com/lichtpfad/h2t-graphs/actions/runs/24862273506`

Observed JSON payload:

```json
{
  "ok": true,
  "provider": "deploy",
  "result": {
    "service": "h2t-graphs",
    "target": "github-main",
    "status": "healthy",
    "details": {
      "profile": "github-actions-dispatch",
      "status_scope": "latest_matching_workflow_run",
      "repo": "lichtpfad/h2t-graphs",
      "workflow": "deploy.yml",
      "ref": "main",
      "reason": "latest workflow run completed successfully",
      "run": {
        "conclusion": "success",
        "createdAt": "2026-04-23T22:34:59Z",
        "databaseId": 24862273506,
        "displayTitle": "chore(docs): add missing frontmatter to plans/specs/ADRs (docs-lint -â€¦",
        "status": "completed",
        "updatedAt": "2026-04-23T22:36:31Z",
        "url": "https://github.com/lichtpfad/h2t-graphs/actions/runs/24862273506"
      }
    }
  }
}
```

## Conclusion

`#183` now has all core v1 proof points on this branch:

- deploy registry/profile loading
- executor contract
- top-level CLI surface
- one real repo-local profile contract
- live `deploy list`
- live `deploy --dry-run`
- live `deploy status`

Current semantics for GitHub Actions status are explicit:

- `deploy status` reports the **latest matching workflow run** for
  `repo + workflow + ref`
- it does **not** yet track a deploy-specific run id across `deploy -> status`

That limitation is in-band via `details.status_scope`, so the surface stays honest.
