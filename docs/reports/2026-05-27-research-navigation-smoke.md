---
title: Research Navigation Smoke
date: 2026-05-27
status: done
---

# Research Navigation Smoke

## Scope

Validate the local research navigation surface for:

- `research index documents`
- `research show document`
- `research resolve --url`
- JSON object artifacts as truth
- indexes as navigation caches

## Environment

- Repo: `C:/dev/h2t-skills`
- Branch: `codex-research-navigation-surface`
- Output root: `C:/tmp/h2t-research-navigation-smoke`
- Document: `research-doc:37a2a2d3f08b34bd7ad73a75`

## Verification

Focused suite:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Result:

- `251 passed`

## Smoke Commands

### 1. Fetch

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Result:

- `status=OK`
- `provider_used=jina`
- `research_refs.document_id=research-doc:37a2a2d3f08b34bd7ad73a75`
- canonical object written under `objects/documents/`

### 2. Index

```powershell
uv.exe run h2t-ops research index documents --project demo --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Result:

- `kind=research_index`
- `index=documents`
- `count=1`
- row includes `project_ids=["project:demo"]`

### 3. Show

```powershell
uv.exe run h2t-ops research show document research-doc:37a2a2d3f08b34bd7ad73a75 --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Result:

- `kind=research_object`
- `object_type=document`
- `object_id=research-doc:37a2a2d3f08b34bd7ad73a75`
- object schema is `research_document/v0.1`
- canonical URL is `https://exa.ai/docs/reference/answer`

### 4. Resolve

```powershell
uv.exe run h2t-ops research resolve --url https://exa.ai/docs/reference/answer --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Result:

- `kind=research_resolution`
- `count=1`
- match target is `research-doc:37a2a2d3f08b34bd7ad73a75`
- `object_exists=true`

## Conclusion

The navigation surface can fetch a URL-backed research document, discover it through the shared
document index, read the canonical JSON object, and resolve the canonical URL alias back to the
object without parsing Markdown mirrors.
