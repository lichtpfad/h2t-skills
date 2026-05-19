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
| `__init__.py` | `CONNECTOR = ConnectorSpec(...)` only | `h2t_ops/connectors/notion/__init__.py:5` |
| `client.py` | provider API logic, typed errors, lazy SDK import | `h2t_ops/connectors/notion/client.py` |
| `commands.py` | argparse subcommands → client calls; no provider logic | `h2t_ops/connectors/notion/commands.py` |
| `tests/connectors/<name>/test_{client,commands}.py` | API + CLI contract | `tests/connectors/notion/` |

## 3. Step-by-step procedure

1. **Create the package.** `h2t_ops/connectors/<name>/{__init__,client,commands}.py`.
   Mirror the layout of `h2t_ops/connectors/notion/`.

2. **Write `client.py`.** Re-wrap the legacy logic (do not rewrite behaviour).
   - Lazy-import the heavy SDK INSIDE the method/`__init__`, never at module
     scope (keeps `h2t-ops --help`/`connectors` cheap).
   - Map provider/HTTP failures to the typed hierarchy; copy the shape of
     `_map_http_error` at `h2t_ops/connectors/gmail/client.py:137`.
   - Missing creds/SDK → `ConfigError`; refused/expired auth → `AuthError`;
     never launch an interactive browser flow.

3. **Write `commands.py`.** One argparse subparser per verb; each handler calls
   the client and returns a result object — it must NOT build envelopes or print.
   Mirror `h2t_ops/connectors/notion/commands.py`.

4. **Write `__init__.py`.** Exactly one `CONNECTOR = ConnectorSpec(...)`. The
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
envelope inside `commands.py` (envelope is `emit()`'s job); interactive OAuth in
`client.py` (forbidden — must raise `ConfigError`); silently dropping a legacy
subcommand instead of documenting the exclusion.

## 4. API coverage checklist (review gate)

## 5. Error and exit-code map

## 6. Output contract

## 7. POS boundary and distribution-without-POS gate

## 8. Definition of Done / PR gate
