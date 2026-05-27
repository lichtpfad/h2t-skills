---
title: Research Maintenance Smoke
date: 2026-05-27
status: done
---

# Research Maintenance Smoke

## Scope

Validate local maintenance commands for:

- `research doctor`
- `research rebuild-indexes`
- `research cleanup --dry-run`

## Environment

- Repo: `C:/dev/h2t-skills-wt-research-maintenance`
- Branch: `codex-research-maintenance-doctor-cleanup`
- Output root: `C:/tmp/h2t-research-maintenance-smoke`

## Commands

```powershell
uv.exe run pytest tests/connectors/research -q
```

Result:

- `279 passed`

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `ok=true`
- `status=OK`
- `provider_used=jina`
- `research_refs.document_id=research-doc:37a2a2d3f08b34bd7ad73a75`

```powershell
uv.exe run h2t-ops research doctor --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_doctor`
- `status=ok`
- `errors=0`
- `warnings=0`

```powershell
uv.exe run h2t-ops research rebuild-indexes --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_rebuild_indexes`
- `status=ok`
- `documents=1`
- `threads=0`
- `runs=0`
- `syntheses=0`
- `aliases=1`

```powershell
uv.exe run h2t-ops research cleanup --dry-run --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_cleanup`
- `dry_run=true`
- `status=ok`
- `count=0`

## Conclusion

Maintenance commands inspect and rebuild local research store state without deleting canonical object
JSON. The smoke root contained one URL-backed document; `doctor` reported a clean store, `rebuild-indexes`
regenerated document and alias indexes, and `cleanup --dry-run` reported no deletion candidates.
