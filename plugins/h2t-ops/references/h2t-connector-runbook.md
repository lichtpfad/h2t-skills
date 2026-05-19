# h2t-ops Connector Development Runbook

**Status:** Active procedure
**Model:** procedural index — this runbook tells you WHAT to do and WHERE the
canonical pattern lives. It does not restate architecture. When this runbook and
an authority document disagree, the authority wins.

## Authority order

1. TZ-0 connector architecture spec —
   `docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md`
2. API coverage audit (2026-05-19) —
   `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md`
3. POS operational boundary —
   `plugins/h2t-ops/references/pos-operational-boundary.md`
4. Testing plan — `docs/h2t-ops-testing-plan.md`
5. Notion / Gmail connector code — the pattern to copy.

## Reference map

Default to **stable file paths**. `file:line` is used ONLY for the load-bearing
patterns below; line numbers are verified and updated whenever this runbook is
edited (routine code is path-only because line anchors drift).

| Pattern | Anchor |
|---|---|
| ConnectorSpec class | `h2t_ops/core/registry.py:14` |
| ConnectorSpec usage (canon) | `h2t_ops/connectors/notion/__init__.py:5` |
| Lazy client string | `h2t_ops/connectors/notion/__init__.py:8` |
| cli `_MIGRATED` set | `h2t_ops/cli.py:18` |
| cli ingest shim | `h2t_ops/cli.py:107` |
| Error map (HTTP→typed) | `h2t_ops/connectors/gmail/client.py:137` |
| Exit-code table | `h2t_ops/core/errors.py:39` |
| `emit()` call site | `h2t_ops/core/output.py:61` |
| Envelope builders | `h2t_ops/core/envelope.py:9` |
| POS "no `~/.dor` write" rule | `plugins/h2t-ops/references/pos-operational-boundary.md:28` |
| Proposed-capture contract | `plugins/h2t-ops/references/pos-operational-boundary.md:39` |

Path-only reference implementations:
`h2t_ops/connectors/notion/` (read-centric) and `h2t_ops/connectors/gmail/`
(read + write + OAuth); core: `h2t_ops/core/`; tests:
`tests/connectors/{notion,gmail}/`.

## Reference anchoring policy

Stable file paths by default. `file:line` ONLY for: ConnectorSpec, lazy client
string, cli `_MIGRATED`/shim, error map, `emit()`/envelope, POS boundary rule.
Routine code is path-only — line anchors there drift and make this runbook
brittle. When you edit this runbook, re-verify the anchors in the Reference map.

## 1. When to use / scope

Use this runbook to add or migrate a **connector**: a stateless client over an
external provider API exposed as `h2t-ops <name> ...`.

A connector is in scope only if it is pure provider I/O. The following are NOT
connector work — they belong to a coordinator/POS layer, never inside the
connector (authority: `plugins/h2t-ops/references/pos-operational-boundary.md`):

- writing `~/.dor/**` (lake, context, journal), `pos.db`, `dor.db`, vault;
- interpretation/summarisation that turns provider data into POS memory;
- multi-step sync/cron/webhook workflows.

If a legacy script mixes reads with the above, migrate ONLY the pure-API reads
and record the excluded side-effecting subcommands explicitly (see the audit
"inventory gate" connectors: Drive/MeetGeek/Telegram).

## 2. Reference implementations

Copy the pattern from the connector closest to your case:

- **Notion** — `h2t_ops/connectors/notion/` — read-centric: token auth, no OAuth
  browser flow, block/markdown normalisation.
- **Gmail** — `h2t_ops/connectors/gmail/` — the fuller case: OAuth token reuse
  (no interactive browser), read + write ops, HTTP→typed error mapping.

Each connector is exactly three files plus tests:

| File | Responsibility | Canon |
|---|---|---|
| `<name>/__init__.py` | `CONNECTOR = ConnectorSpec(...)` only | `h2t_ops/connectors/notion/__init__.py:5` |
| `<name>/client.py` | provider API logic, typed errors, lazy SDK import | `h2t_ops/connectors/notion/client.py` |
| `<name>/commands.py` | argparse subcommands → client calls; no provider logic | `h2t_ops/connectors/notion/commands.py` |
| `tests/connectors/<name>/test_{client,commands}.py` | API + CLI contract | `tests/connectors/notion/` |

## 3. Step-by-step procedure

1. **Create the package.** `h2t_ops/connectors/<name>/{__init__,client,commands}.py`.
   Mirror the layout of `h2t_ops/connectors/notion/`.

2. **Write `<name>/client.py`.** Re-wrap the legacy logic (do not rewrite behaviour).
   - Lazy-import the heavy SDK INSIDE the method/`__init__`, never at module
     scope (keeps `h2t-ops --help`/`connectors` cheap).
   - Map provider/HTTP failures to the typed hierarchy; copy the shape of
     `_map_http_error` at `h2t_ops/connectors/gmail/client.py:137`.
   - Missing creds/SDK → `ConfigError`; refused/expired auth → `AuthError`;
     never launch an interactive browser flow.

3. **Write `<name>/commands.py`.** One argparse subparser per verb; each handler calls
   the client and returns a result object — it must NOT build envelopes or print.
   Mirror `h2t_ops/connectors/notion/commands.py`.

4. **Write `<name>/__init__.py`.** Exactly one `CONNECTOR = ConnectorSpec(...)`. The
   `client=` value is the **lazy string** `"h2t_ops.connectors.<name>.client:<Class>"`
   — see `h2t_ops/connectors/notion/__init__.py:8`. `ConnectorSpec` is defined at
   `h2t_ops/core/registry.py:14`; it is discovered automatically — never import
   the client at registration.

5. **Wire the CLI.** Add `"<name>"` to `_MIGRATED` at `h2t_ops/cli.py:18`. If a
   legacy `h2t ingest <name>` path exists, add a deprecation shim mirroring the
   ingest shim at `h2t_ops/cli.py:107` (warns on human output, silent under
   `--json`).

6. **Tests.** API happy path + typed-error mapping + CLI contract
   (`--json`, human, `--help`, shim) + the lazy-registry guard. Migrate any
   legacy normalise tests. Pattern: `tests/connectors/gmail/`.

7. **Live smoke.** Read-only live E2E through the installed CLI; record evidence
   in the issue per `docs/h2t-ops-testing-plan.md`.

Common pitfalls: module-scope SDK import (breaks `--help`); building the
envelope inside `<name>/commands.py` (envelope is `emit()`'s job); interactive OAuth in
`<name>/client.py` (forbidden — must raise `ConfigError`); silently dropping a legacy
subcommand instead of documenting the exclusion.

## 4. API coverage checklist (review gate)

Every connector PR must pass the **9-item API coverage checklist**. It is
maintained verbatim in the roadmap — do not copy it here (single source of
truth): see `docs/h2t-ops-roadmap.md`, section
`skills: [M3] Add connector development skill runbook — #138` →
"API coverage checklist (required gate for every connector PR)".

The nine gates, by name (full text in the roadmap): 1 legacy parity ·
2 provider API gaps · 3 auth/secrets · 4 lazy imports · 5 tests · 6 live smoke ·
7 POS boundary · 8 distribution-without-POS · 9 write side effects.

A reviewer who cannot point each gate at concrete evidence must block the PR.

## 5. Error and exit-code map

Raise the typed hierarchy in `h2t_ops/core/errors.py`; never `sys.exit` or print
from a client. The exit-code table is `EXIT_CODES` at
`h2t_ops/core/errors.py:39` (resolved by `exit_code_for`). Map provider/HTTP
failures with the same shape as `_map_http_error`
(`h2t_ops/connectors/gmail/client.py:137`):

- bad arguments → `UsageError` (2)
- missing/!resolvable creds or SDK → `ConfigError` (3)
- refused/expired auth → `AuthError` (4)
- provider 4xx/5xx → `ProviderError` (1)
- missing resource → `NotFoundError` (5)
- transport/timeout → `NetworkError` (6)

## 6. Output contract

`<name>/commands.py` returns a result object; it never prints. `emit()`
(`h2t_ops/core/output.py:61`) renders it through the universal envelope
(`success_envelope`/`error_envelope` at `h2t_ops/core/envelope.py:9`) honoring
`--json` / `--format md` / human. Do not hand-build envelopes in a connector.

## 7. POS boundary and distribution-without-POS gate

Authority: `plugins/h2t-ops/references/pos-operational-boundary.md`.

- A connector imports no `pos`/`dor.db`/`vault`/`lake` and must run with POS
  absent. It must not write `~/.dor/**` — see the rule at
  `plugins/h2t-ops/references/pos-operational-boundary.md:28`.
- Default any output path to stdout, not `~/.dor/`.

Provider write commands are allowed only as explicit CLI verbs with clear user
intent (e.g. `send`, `label`, `create`, `delete`). They must be classified in
the API coverage checklist as write side effects and covered by tests.

A synthesis/coordinator workflow must not auto-execute provider writes. If an
agent discovery implies a task/decision/action and POS journal/action commands
are unavailable, emit a structured `proposed_capture`
(`plugins/h2t-ops/references/pos-operational-boundary.md:39`) instead of
mutating POS/vault/lake or silently performing workflow writes.

## 8. Definition of Done / PR gate

A connector is done only when (authority: `docs/h2t-ops-testing-plan.md`):

- the 9-item checklist (§4) passes with evidence;
- CI + mocked API/CLI tests green; lazy-registry guard covers the new SDK;
- read-only live E2E through the **installed** CLI passed, evidence in the issue
  in the testing-plan format;
- legacy entrypoint preserved until its users migrate;
- no connector code outside the new package changed; POS boundary held.

<!-- self-review 2026-05-19: 9-item gate coverage
1 parity §3.2 · 2 provider-gap §4 · 3 auth/secrets §3.2,§5 · 4 lazy §3.2,§3.4
5 tests §3.6 · 6 live smoke §3.7,§8 · 7 POS §7 · 8 dist-no-POS §7 · 9 writes §7
all gates have a concrete runbook locus -->
