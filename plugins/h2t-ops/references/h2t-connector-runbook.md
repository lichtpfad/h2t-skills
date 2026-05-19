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

## 2. Reference implementations

## 3. Step-by-step procedure

## 4. API coverage checklist (review gate)

## 5. Error and exit-code map

## 6. Output contract

## 7. POS boundary and distribution-without-POS gate

## 8. Definition of Done / PR gate
