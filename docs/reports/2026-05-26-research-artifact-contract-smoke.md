---
title: Research Artifact Contract Phase 1 Smoke
date: 2026-05-26
status: done
---

# Research Artifact Contract Phase 1 Smoke

## Scope

Validate the new local research object/index contract for:

- URL-backed `ResearchDocument`
- query-backed `ResearchThread`
- query-backed `ResearchRun`
- query-backed `ResearchSynthesis`
- `research_refs` writeback into artifact envelopes

## Commands

### 1. URL-backed fetch

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-smoke-v2 --json
```

Result:

- `status=OK`
- `provider_used=jina`
- artifact envelope contains:
  - `research_refs.document_id`
  - `research_refs.document_json`

Verified files:

- `C:/tmp/h2t-research-smoke-v2/objects/documents/research-doc:37a2a2d3f08b34bd7ad73a75.json`
- `C:/tmp/h2t-research-smoke-v2/indexes/documents.index.json`
- `C:/tmp/h2t-research-smoke-v2/indexes/aliases.index.json`

Verified contract:

- canonical object JSON written under `objects/documents/`
- `documents.index.json` contains one rebuildable row
- `aliases.index.json` contains canonical URL alias entry
- no Markdown parsing involved in lookup

### 2. Query-backed answer

```powershell
uv.exe run h2t-ops research answer --query "What does Exa /answer do?" --json
```

Result:

- `status=OK`
- `primary_engine=exa`
- artifact envelope contains:
  - `research_refs.thread_id`
  - `research_refs.thread_json`
  - `research_refs.run_id`
  - `research_refs.run_json`
  - `research_refs.synthesis_id`
  - `research_refs.synthesis_json`

Verified files:

- `C:/Users/<user>/.h2t/research/objects/threads/research-thread:914af17221fd2893239bde34.json`
- `C:/Users/<user>/.h2t/research/objects/runs/research-run:8bacbde04f27a794098929c1.json`
- `C:/Users/<user>/.h2t/research/objects/syntheses/research-synthesis:faa6b88f8c3da5997e3f6837.json`
- `C:/Users/<user>/.h2t/research/indexes/threads.index.json`
- `C:/Users/<user>/.h2t/research/indexes/syntheses.index.json`

Verified contract:

- `ResearchThread.latest_synthesis_id` updated after synthesis write
- `threads.index.json` reflects the same `latest_synthesis_id`
- `syntheses.index.json` contains review/routing fields:
  - `status`
  - `review_status`
  - `confidence_summary`
  - `has_open_questions`

## Notes

An earlier `fetch --provider direct https://example.com` failed in this environment with `fetch_network_timeout`.
That path is not used as evidence for Phase 1 success.

After the fix:

- failed URL-backed fetches no longer persist `ResearchDocument` rows
- successful URL-backed fetches persist document/index state
- successful query-backed answer writes thread/run/synthesis state and backfills `latest_synthesis_id`

## Conclusion

Phase 1 local research contract is live-validated for:

- document persistence
- thread/run/synthesis persistence
- artifact `research_refs`
- rebuildable shared indexes
- JSON-first local truth
