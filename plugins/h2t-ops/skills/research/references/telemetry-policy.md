# Research Telemetry Policy

Exa is paid. Every research run must preserve usage telemetry.

Required telemetry fields:

- provider
- endpoint
- mode or fetch provider
- template id when selected
- status
- latency
- result count
- estimated cost
- cost basis
- artifact id
- repo/issue/session when the agent knows them

Allowed `cost_basis` values:

- `provider_reported`
- `estimated`
- `zero`
- `unknown`

Default local ledger:

```text
~/.h2t/research/telemetry.jsonl
```

The ledger is best-effort. A failed ledger append must not make research fail.
