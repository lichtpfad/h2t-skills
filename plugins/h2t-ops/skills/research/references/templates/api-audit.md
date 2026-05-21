# Template: api-audit/v1

Use for provider API coverage and legacy parity audits.

Required sections:

- Provider capabilities checked
- Existing local implementation
- Gaps
- Side effects
- Auth/secrets
- Tests
- Follow-up issues

Validation rules:

- `min_sources: 2`
- `quotes_required: true`
- `gap_table_required: true`
- `side_effects_required: true`
