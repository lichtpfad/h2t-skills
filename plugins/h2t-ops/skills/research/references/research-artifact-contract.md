# Research Artifact Contract

Research output is evidence, not canonical knowledge.

## Provider Artifact: `research_artifact/v1`

Written or returned by `h2t-ops research`.

Required fields:

- `kind: "research_artifact"`
- `version: "v1"`
- `artifact_id`
- `created_at`
- `tool`
- `provider_status: "OK" | "DEGRADED" | "FAILED"`
- `artifact_refs.sources_json`
- `artifact_refs.artifact_json`
- `telemetry.calls`
- `telemetry.providers`
- `telemetry.estimated_cost_usd`
- `telemetry.cost_basis`

## Registration Manifest: `research_artifact_registration/v1`

Filled by the agent after final synthesis while the work context is fresh.

Required sections:

- `artifact`
- `request`
- `work_context`
- `traceability`
- `pos_intake`

Default POS promotion:

```json
{"promotion_status": "evidence_only"}
```

POS may index and link this artifact. POS owns dedupe, lifecycle, and promotion.
