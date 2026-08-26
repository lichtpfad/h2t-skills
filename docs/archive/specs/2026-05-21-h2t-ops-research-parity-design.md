---
title: "h2t-ops Research Parity + Fetch Ladder Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-21"
milestone: ""
---
# h2t-ops Research Parity + Fetch Ladder Design

## Goal

Migrate the mature `h2t-ops:research` runtime into `h2t_ops/connectors/research/`
without losing its strongest properties:

- Exa search modes and Exa `/contents` crawl parity.
- URL fetch ladder as `h2t-ops research fetch --url ...`, not a top-level
  connector.
- Rich provider envelopes with `OK | DEGRADED | FAILED`.
- Fail-loud behavior and source traceability.
- Existing local artifact storage under `~/.h2t/research/`.

The migration must also prepare a clean interface for Personal OS intake:
research artifacts are evidence, not canonical knowledge. `h2t-ops` can create
traceable artifacts and registration manifests, but POS owns indexing, linking,
dedupe, and promotion into the knowledge base.

## Authority Order

1. `docs/h2t-ops-roadmap.md`
2. `plugins/h2t-ops/references/h2t-connector-runbook.md`
3. `plugins/h2t-ops/references/pos-operational-boundary.md`
4. Existing research specs:
   - `docs/superpowers/specs/2026-05-07-research-provider-envelope.md`
   - `docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md`
5. Existing runtime:
   - `plugins/h2t-ops/skills/research/scripts/exa_search.py`
   - `plugins/h2t-ops/skills/research/scripts/fetch_url.py`
6. Current connector patterns in `h2t_ops/connectors/{gmail,telegram,meetgeek}/`.

## Current Inventory

### Legacy Research Runtime

`plugins/h2t-ops/skills/research/scripts/exa_search.py`

- Commands: `preflight`, `search`, `crawl`.
- Search modes: `fast`, `generic`, `news`, `academic`, `competitor`, `people`,
  `deep`.
- Exa endpoints: `/search`, `/contents`.
- Retry/degraded model:
  - `OK`: non-empty results.
  - `DEGRADED`: provider worked but content/results are weak or empty.
  - `FAILED`: provider/API/network/config failure.
- Sidecars:
  - `~/.h2t/research/*.sources.json`
  - `~/.h2t/research/*.partial.md`
  - `~/.h2t/research/.pending_telemetry.jsonl`
- Secrets: dynamically imports `h2t_secrets.py` from h2t-core plugin cache and
  then reads `EXA_API_KEY`.

### Legacy Fetch Ladder

`plugins/h2t-ops/skills/research/scripts/fetch_url.py`

- Command: `fetch`, plus `preflight`.
- Provider order: `direct`, `jina`, `playwright`, `crawl4ai`, `firecrawl`,
  `browserless`.
- Currently implemented providers: `direct`, `jina`.
- Stubbed providers: `playwright`, `crawl4ai`, `firecrawl`, `browserless`.
- Gate behavior:
  - `login_required` and `paid` are hard gates.
  - The ladder must not bypass gated content with another provider.
- Sidecars:
  - `~/.h2t/research/*.sources.json`
  - optional raw HTML when `--keep-raw`.

### Tests

Existing skill-local tests are large and valuable:

- `plugins/h2t-ops/skills/research/tests/test_exa_search.py`
- `plugins/h2t-ops/skills/research/tests/test_fetch_url.py`

They already cover Exa mode mapping, envelope shape, retry/degraded behavior,
provider errors, provider ladder order, gated/paywall behavior, Jina, UTF-8, and
sidecar writes. The migration should port or re-home these tests rather than
rewrite the behavior from memory.

## Design Locks

### 1. Connector vs Skill vs POS

| Layer | Owns |
| --- | --- |
| `h2t_ops.connectors.research` | Exa provider I/O, fetch ladder I/O, typed errors, machine-readable envelopes, local `~/.h2t/research/` artifacts |
| `h2t-ops:research` skill | Agent workflow, template selection, traceability policy, final report synthesis, registration manifest enrichment |
| POS | Artifact registration, indexing, dedupe, linking, KB promotion, review, lifecycle |

`h2t-ops` must remain usable without POS installed.

### 2. Evidence, Not Truth

Provider result, provider summary, and agent synthesis are evidence. They are
not canonical knowledge until POS/coordinator accepts or promotes them.

Default POS promotion status for research artifacts is:

```json
"promotion_status": "evidence_only"
```

### 3. Traceability Is Required

Final research reports must preserve:

- exact original user request;
- normalized query sent to the provider;
- provider/mode/depth/template;
- timestamp;
- source URLs;
- verbatim quotes;
- confidence labels;
- limitations;
- provider envelope;
- raw sidecar references.

No final report should claim a finding without URL + quote + confidence.

### 4. Agent-Supplied Registration Context

The agent has fresh context that POS should not reconstruct later with another
LLM pass. The skill must collect and persist that context at finalization time:

- repo;
- cwd;
- branch;
- issue/PR when known;
- session id when known;
- domain;
- purpose;
- expected use;
- tags/collections.

### 5. Cost Telemetry

Exa is paid. Research calls must preserve usage telemetry in each artifact and,
where possible, append a local usage ledger under `~/.h2t/research/`.

This is a local ledger, not POS state. POS may import it later.

### 6. Templates Are Lazy References

The skill should become lean. Heavy report policies and domain-specific
templates belong under skill references/templates and are loaded only when the
request needs them.

System prompts remain separate: `systemprompts/` are provider prompts for Exa,
not report templates.

### 7. Validation Is Contracted, Not Required To Be Complete In #136

Research templates should declare validation rules. A full `research validate`
command can be a follow-up if it would slow migration, but #136 must not design
artifacts that cannot be validated later by JSON/jq-style checks.

## Target Module Layout

Research is a TZ-2 thick connector. It is intentionally allowed to exceed the
normal three-file connector layout; otherwise the migration would produce one
large, hard-to-review `client.py`.

```text
h2t_ops/connectors/research/
  __init__.py      # CONNECTOR only
  client.py        # ResearchClient facade, typed errors, artifact orchestration
  exa.py           # Exa search/crawl logic ported from exa_search.py
  fetch.py         # provider ladder ported from fetch_url.py
  commands.py      # argparse only, lazy client import
```

Tests:

```text
tests/connectors/research/
  __init__.py
  test_exa.py
  test_fetch.py
  test_client.py
  test_commands.py
```

Skill references/templates:

```text
plugins/h2t-ops/skills/research/
  SKILL.md
  references/
    research-artifact-contract.md
    pos-registration-contract.md
    traceability-policy.md
    telemetry-policy.md
    templates/
      technical-decision.md
      api-audit.md
      market-research.md
      company.md
      academic.md
      news-monitoring.md
      person.md
  systemprompts/
    fast.md
    generic.md
    news.md
    academic.md
    competitor.md
    people.md
    deep.md
```

## CLI Surface

Connector commands:

```text
h2t-ops research preflight [--json]
h2t-ops research search --query Q [--mode MODE] [--depth DEPTH] [filters...] [--json] [--format md|human]
h2t-ops research crawl --url URL [--json] [--format md|human]
h2t-ops research fetch --url URL [--provider auto|direct|jina|playwright|crawl4ai|firecrawl|browserless] [--json] [--format md|human]
```

Search parity flags:

- `--query`
- `--mode fast|generic|news|academic|competitor|people|deep`
- `--depth shallow|standard|deep`
- `--num-results`
- `--additional-queries`
- `--start-date`
- `--end-date`
- `--include-domains`
- `--exclude-domains`
- `--include-text`
- `--exclude-text`
- `--country`
- `--full-text`
- `--output-dir`
- `--project`
- `--no-retry`

Fetch parity flags:

- `--url`
- `--provider`
- `--keep-raw`
- `--timeout-ms`
- `--min-body-chars`
- `--user-agent`
- `--output-dir`
- `--project`
- `--config`

Future commands, not required for #136:

```text
h2t-ops research validate --manifest PATH --json
h2t-ops research telemetry --since DATE --json
```

## Output Contract

### Success And Degraded

For `OK` and `DEGRADED`, return exit 0 through the normal h2t-ops success
envelope:

```json
{
  "ok": true,
  "provider": "research",
  "result": {
    "status": "OK",
    "kind": "research_provider_envelope",
    "...": "rich provider envelope"
  }
}
```

`DEGRADED` remains exit 0 because the provider produced usable diagnostic
output. Callers must inspect `result.status`, not only process exit.

### Failed With Telemetry

Research needs non-zero exit plus machine-readable provider telemetry. The
current `error_envelope()` has no `details` slot, so #136 should add a small
core extension:

```python
class H2TError(Exception):
    def __init__(self, message: str, *, hint: str | None = None, details: Any | None = None):
        ...
```

`details` is public diagnostic data. It must be JSON-serializable and sanitized
before it reaches `H2TError`; never put headers, API keys, bearer tokens, raw
request objects, or arbitrary exception objects in it.

`error_envelope()` should include `error.details` only when present. Existing
error envelopes must remain byte-for-byte shape-compatible when `details is
None`.

Failed research commands then raise typed errors with:

```json
{
  "provider_envelope": {
    "status": "FAILED",
    "...": "rich failed provider envelope"
  }
}
```

Human output stays concise and fail-loud. JSON output preserves diagnostics.

Required core tests:

- `H2TError(..., details={...})` stores details.
- `error_envelope()` includes `error.details` only when details are not `None`.
- Details are JSON-serializable in `emit(..., fmt="json")`.
- Existing errors without details keep the old JSON shape.
- Token-like strings are not present in research error details.

## Exit Code Remap

Legacy research scripts use `0..5`. h2t-ops canonical exits are:

| Condition | Legacy | h2t-ops typed error | h2t-ops exit |
| --- | ---: | --- | ---: |
| OK | 0 | none | 0 |
| DEGRADED | 0 | none | 0 |
| args | 1 | `UsageError` | 2 |
| provider HTTP / malformed | 2 | `ProviderError` | 1 |
| network / timeout | 3 | `NetworkError` | 6 |
| missing env / config | 4 | `ConfigError` | 3 |
| gated login / paid | 5 | `AuthError` | 4 |

Rationale for gated content as `AuthError`: the request is blocked by missing
credentials/subscription, not by a malformed provider response. The provider
envelope still carries `content_gate=login_required|paid`.

## Artifact Model

### Provider Artifact

The connector produces provider artifacts under `~/.h2t/research/`:

```json
{
  "kind": "research_artifact",
  "version": "v1",
  "artifact_id": "research_...",
  "created_at": "2026-05-21T...",
  "tool": "h2t-ops research",
  "provider_status": "OK",
  "artifact_refs": {
    "sources_json": "...",
    "partial_md": "...",
    "raw_html": null
  },
  "telemetry": {
    "calls": 1,
    "providers": ["exa"],
    "estimated_cost_usd": 0.012,
    "cost_basis": "provider_reported"
  }
}
```

The connector can know provider-level facts, paths, and telemetry. It cannot
know the full agent intent.

### Registration Manifest

After final report synthesis, the skill/agent enriches the artifact with fresh
work context:

```json
{
  "kind": "research_artifact_registration",
  "version": "v1",
  "artifact": {
    "artifact_id": "research_...",
    "report_md": "...",
    "sources_json": "...",
    "provider_envelope_status": "OK",
    "created_at": "2026-05-21T...",
    "tool": "h2t-ops research"
  },
  "request": {
    "original_user_request": "...",
    "normalized_query": "...",
    "mode": "generic",
    "depth": "standard",
    "domain": "h2t-skills",
    "purpose": "decision_support",
    "expected_use": "issue_context"
  },
  "work_context": {
    "repo": "lichtpfad/h2t-skills",
    "cwd": "C:/dev/h2t-skills",
    "branch": "main",
    "issue": 136,
    "session_id": "...",
    "related_files": [],
    "related_projects": []
  },
  "traceability": {
    "requires_quotes": true,
    "has_source_urls": true,
    "has_verbatim_quotes": true,
    "sources_count": 12,
    "limitations_recorded": true,
    "confidence_recorded": true
  },
  "pos_intake": {
    "register": true,
    "index_full_text": true,
    "promotion_status": "evidence_only",
    "suggested_collections": ["research", "h2t-skills"],
    "tags": ["research-connector", "exa", "migration"]
  }
}
```

The registration manifest is the bridge to POS. POS may ingest it, but #136
does not require POS to exist.

Ownership boundary:

- #136 connector implementation must emit or return enough provider artifact
  metadata to construct `research_artifact/v1`.
- #136 skill documentation and references must define
  `research_artifact_registration/v1`.
- The agent fills registration context during final report synthesis.
- A concrete registration writer script is optional and may be a follow-up if it
  would slow connector closure.

## POS Intake Boundary

Allowed in #136:

- write artifacts under `~/.h2t/research/`;
- write or return `research_artifact/v1` provider metadata;
- define `research_artifact_registration/v1` as the agent/POS handoff contract;
- optionally invoke a POS registration command only if it exists and only as an
  optional skill-level step;
- leave a ready-to-ingest manifest when POS is absent.

Forbidden in #136:

- direct writes to POS DB, `dor.db`, `pos.db`;
- writes to vault, `~/.dor/lake`, `~/.dor/context`;
- automatic KB promotion;
- automatic accepted task/decision creation;
- LLM interpretation that claims provider output as truth.

Future POS-side issue:

```text
research: provider-neutral research artifact intake contract
```

This should define how research artifacts are indexed, deduped, linked, and
promoted.

## Templates And References

`SKILL.md` should become a short routing document. It should tell the agent:

1. choose a research template;
2. run `h2t-ops research ...`;
3. write a final report;
4. write registration manifest;
5. optionally hand the manifest to POS.

Templates are lazy-loaded references. They should define:

- `template_id`;
- purpose;
- required request fields;
- required traceability fields;
- default tags/collections;
- validation rules;
- final report shape.

Example template metadata:

```yaml
id: technical-decision/v1
purpose: decision_support
requires:
  - original_user_request
  - repo
  - issue
  - source_urls
  - verbatim_quotes
  - limitations
pos_defaults:
  promotion_status: evidence_only
  suggested_collections: ["research", "engineering"]
validation:
  min_sources: 3
  quotes_required: true
  limitations_required: true
  confidence_required: true
```

Template validation can initially be manual/checklist-based. A future
`research validate` command can load these rules and check a manifest/report
without LLM.

## Cost Telemetry

Each provider call should contribute a telemetry record:

```json
{
  "kind": "research_telemetry",
  "version": "v1",
  "timestamp": "2026-05-21T...",
  "artifact_id": "research_...",
  "provider": "exa",
  "endpoint": "/search",
  "mode": "generic",
  "template_id": "technical-decision/v1",
  "status": "OK",
  "latency_ms": 1234,
  "result_count": 8,
  "estimated_cost_usd": 0.012,
  "cost_basis": "provider_reported",
  "repo": "lichtpfad/h2t-skills",
  "issue": 136,
  "session_id": "..."
}
```

`estimated_cost_usd` may be `null`.

Allowed `cost_basis` values:

- `provider_reported` — Exa returned cost data.
- `estimated` — local estimate from known pricing/operation.
- `zero` — local/free provider such as direct fetch.
- `unknown` — provider cost is unknown or unavailable.

Default local ledger:

```text
~/.h2t/research/telemetry.jsonl
```

The ledger is append-only and best-effort. It must not make research fail if the
append fails; the artifact-local telemetry remains the primary evidence.

Opt-out:

```text
H2T_RESEARCH_TELEMETRY_DISABLE=1
```

Open question for implementation plan: whether ledger append is a T1 must-have
or a T4 closure enhancement. Artifact-local telemetry is mandatory either way.

## Secrets

Research should use the shared h2t secrets substrate rather than plugin-cache
path discovery.

Preferred order:

1. existing shell environment;
2. `$H2T_SECRETS_FILE` if set;
3. `~/.dor/secrets/secrets.env` (current h2t-core canonical path);
4. legacy `~/.dor/secrets.env` (current `h2t_ops.core.secrets` fallback);
5. typed `ConfigError` if required keys are absent.

Do not regress live users whose `EXA_API_KEY` exists only in
`~/.dor/secrets/secrets.env`. If `h2t_ops.core.secrets.load_secrets()` is reused,
extend it or add a research-specific resolver so both current h2t-core and
legacy paths work.

Required keys:

- `EXA_API_KEY` for Exa search/crawl/preflight.

Optional keys:

- `JINA_API_KEY` for authenticated Jina Reader calls.

No secrets should be written to artifact files. Token leak scan must check
`EXA_API_KEY`, `JINA_API_KEY`, and bearer-like strings.

Required tests:

- env var wins over file;
- `$H2T_SECRETS_FILE` works;
- `~/.dor/secrets/secrets.env` works;
- legacy `~/.dor/secrets.env` works;
- missing `EXA_API_KEY` raises `ConfigError` with neutral setup hint;
- artifact and error details contain no secret values.

## Skill Update

`plugins/h2t-ops/skills/research/SKILL.md` should be rewritten as a thin
delegation and workflow guide:

- use `h2t-ops research preflight`;
- use `h2t-ops research search`;
- use `h2t-ops research crawl`;
- use `h2t-ops research fetch`;
- load only the relevant template/reference;
- preserve traceability;
- write registration manifest;
- optional POS intake only if available.

Keep:

- `REPORT-SPEC.md` if still useful;
- `systemprompts/` for Exa provider prompts;
- examples, either updated in place or moved under references.

Do not keep path-glob runtime instructions that discover plugin cache scripts.
Those become obsolete once the connector lands.

## Tests

### Client/Provider Tests

Port existing tests into `tests/connectors/research/`:

- Exa mode mapping and argument validation.
- Exa body builder.
- Exa HTTP success, 4xx, 5xx, 429, malformed JSON, network.
- Retry and degraded semantics.
- Exa `/contents` crawl.
- Fetch ladder direct provider.
- Fetch ladder Jina provider.
- Stub provider behavior.
- Gated login/paywall behavior.
- Redirect-collapsed behavior.
- UTF-8 output safety.
- Sidecar paths and artifact manifest shape.
- Telemetry summary fields.

### Commands Tests

- `research --help` exit 0.
- `research search --help` exit 0.
- `research crawl --help` exit 0.
- `research fetch --help` exit 0.
- `--json` wraps result in canonical success envelope for OK/DEGRADED.
- FAILED with `--json` exposes `error.details.provider_envelope`.
- human output remains concise and does not dump secrets.
- `--format md|human` works where supported.

### Boundary Tests

Grep guards:

- no `~/.dor` write in `h2t_ops/connectors/research`;
- no `vault`, `lake`, `pos.db`, `dor.db` references in connector runtime;
- no `WebSearch` / `WebFetch` fallback in connector runtime;
- no plugin cache glob lookup in connector runtime;
- no Exa/Jina network call during `h2t-ops --help` / `connectors`.

### Lazy Registry

Extend `h2t-ops dev check lazy-registry` to guard research heavy/optional
imports if new dependencies are introduced. Current research implementation is
stdlib-only; this gate still must prove that `EXA_API_KEY` resolution and
network providers are not touched during discovery.

## Live Smoke

Read-only/live-safe:

```text
h2t-ops research preflight --json
h2t-ops research search --query "h2t skills research connector" --mode fast --num-results 2 --json
h2t-ops research fetch --url "https://example.com" --provider direct --json
h2t-ops connectors
h2t-ops --help
```

Optional, only if useful:

```text
h2t-ops research fetch --url "https://example.com" --provider jina --json
```

No paid Firecrawl/Browserless smoke in #136.

## Non-Goals

- No top-level `h2t-ops fetch` connector.
- No automatic POS DB/vault/lake writes.
- No automatic KB promotion.
- No automatic action/task/decision creation.
- No WebSearch/WebFetch silent fallback.
- No paywall/auth bypass.
- No Firecrawl/Browserless/Playwright implementation beyond existing stubs.
- No full template validator unless it is trivial after manifest work.
- No Daily Brief migration in #136.
- No legacy `h2t` monolith cleanup in #136.

## Implementation Outline

Expected plan shape:

1. T0: research baseline verification, no commit.
2. T1: core error-envelope details support, with tests.
3. T2: research secrets resolver + artifact/telemetry helper contracts.
4. T3: migrate Exa pure provider logic and tests.
5. T4: migrate Exa command-facing facade (`search`, `crawl`) and tests.
6. T5: migrate fetch providers and provider tests.
7. T6: migrate fetch ladder/facade and tests.
8. T7: add commands, registry, `_MIGRATED`, command tests.
9. T8: skill references/templates + SKILL.md rewrite.
10. T9: final verification, live smoke, issue evidence, no commit.

Each commit-bearing task should have a narrow file map. Avoid a single "move
the whole script" commit unless review proves it is mechanical and low-risk.

## Definition Of Done

- `h2t-ops research` appears in `h2t-ops connectors`.
- `h2t-ops research search --json` preserves the rich Exa envelope.
- `h2t-ops research fetch --url ... --json` preserves the rich fetch envelope.
- `FAILED` JSON output includes provider telemetry via `error.details`.
- Legacy exit-code semantics are mapped to the canonical h2t-ops exit table.
- Existing research tests are ported or replaced with equivalent connector tests.
- Skill docs no longer require discovering plugin-cache script paths.
- Traceability policy is preserved.
- `research_artifact/v1` provider metadata is emitted or returned.
- `research_artifact_registration/v1` contract is documented for agent/POS
  handoff.
- Cost telemetry is not lost, and cost records include `cost_basis`.
- No connector code writes POS/vault/lake/context state.
- Live read-only smoke passes.
