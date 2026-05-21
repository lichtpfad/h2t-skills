# Template: technical-decision/v1

Use for engineering decisions, connector migrations, API choice, or architecture tradeoffs.

Required registration fields:

- `request.original_user_request`
- `request.normalized_query`
- `request.domain`
- `request.purpose: "decision_support"`
- `work_context.repo`
- `work_context.cwd`
- `work_context.issue`
- `traceability.has_source_urls: true`
- `traceability.has_verbatim_quotes: true`
- `traceability.limitations_recorded: true`

POS defaults:

- `promotion_status: evidence_only`
- `suggested_collections: ["research", "engineering"]`

Validation rules:

- `min_sources: 3`
- `quotes_required: true`
- `limitations_required: true`
- `confidence_required: true`
