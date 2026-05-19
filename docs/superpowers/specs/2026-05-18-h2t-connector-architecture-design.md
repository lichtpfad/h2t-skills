# ТЗ-0: H2T Connector Architecture Standard + Core Foundation + Notion Walking Skeleton

**Status:** Draft
**Date:** 2026-05-18
**Author:** Stanislav Glazov + Claude
**Supersedes:** ad-hoc per-skill script discovery; `lib/` + `sys.path.insert` layout

---

## 1. Context / Problem

Connectors today are fragmented and not distributable:

- **Notion implemented 4× independently** (1656 LOC total): `h2t-skills/lib/clients/notion.py` (462),
  `h2t-business/scripts/notion_extract.py` (744), `h2t-business/scripts/notion_dump.py` (311),
  `POS/src/api/app/services/notion.py` (139).
- `exa_search.py` / `fetch_url.py` are standalone scripts **not** in the `h2t` CLI; the agent
  discovers them via `ls … | sort -V | tail -1` glob on every call.
- `pyproject.toml` declares package `h2t` but code lives in `lib/`, imported via a
  `sys.path.insert` hack in `lib/cli/main.py`. `from h2t.connectors.notion import …` is impossible.
- Cross-plugin path resolution broke on macOS (`parents[4]` → `h2t-ops/h2t-core/…` which does not
  exist); fixed in `exa_search.py` 0.1.2 but the underlying discovery model is fragile.
- Agent emits multi-line shell with `$VAR`/`$(…)` expansion → Claude Code flags `simple_expansion`
  → an approval prompt on every research call.

**Goal:** ONE canonical connector per service, distributed via `uv tool install`, usable by
Claude Code skills **and** Personal OS **and** standalone shell, cross-platform (Windows + Mac),
extensible by a runbook — **without an infinite rewrite**.

## 2. Decision

> ### Identity Decision (amendment 2026-05-19 — supersedes original `h2t` naming)
>
> Operational connectors are packaged as `h2t-ops` with Python namespace `h2t_ops`.
> This package MUST NOT claim the root `h2t` Python package or `h2t` console script.
> The existing `h2t` command remains owned by `h2t-ai`.
> `h2t-ops` MAY expose its own console script `h2t-ops`.
> `h2t-ai` MAY later delegate selected namespaces to `h2t-ops` for unified internal UX.
>
> **Root cause of the amendment:** `C:/dev/h2t-ai` already owns the `h2t` distribution
> (`[project.scripts] h2t = "h2t.cli:main"`, `src/h2t/` import package, subcommands
> `td registry graph vision transcribe enrich eval`). The original spec chose a monolithic
> `h2t` package + `uv tool install` global `h2t` without surveying the ecosystem — a total,
> byte-identical collision. The implementation is sound; only the **identity** was wrong.
>
> **Interpretation clause:** everywhere below this line, read `h2t` (the package) as
> `h2t_ops`, `h2t.cli:main` as `h2t_ops.cli:main`, the console script `h2t` as `h2t-ops`,
> and any `h2t.<sub>` import path as `h2t_ops.<sub>`. §3/§4/§8/§12 code/prose are not
> mechanically rewritten; this clause is normative over their literal `h2t` spelling.
> h2t-ai delegation (`h2t notion → h2t-ops notion`) is an explicit follow-up, NOT ТЗ-0.

**Approach 1 — monolithic `h2t_ops` package with lazily auto-registered connectors** (a
sub-distribution; root `h2t` stays h2t-ai's).

Rejected alternatives:
- *Per-connector uv packages* (`h2t-notion`, …): N packages to ship/upgrade, shared
  auth/secrets/envelope duplicated or pushed into a `h2t-core` dependency. Overkill for solo+AI.
- *Library-only, no CLI*: breaks the requirement that scripts are usable as CLI in POS and kills
  agent-friendly `h2t-ops notion …` invocation.
- *Claim root `h2t` / `h2t.cli:main`* (original draft): collides totally with h2t-ai — rejected
  by the Identity Decision above.

## 3. Package Layout

```
h2t/                              # real import package (replaces lib/ + sys.path hack)
  __init__.py
  cli.py                          # entrypoint: build parser from registry, dispatch
  core/
    __init__.py
    registry.py                   # ConnectorSpec, lazy discovery, list/help
    errors.py                     # typed exception hierarchy + exit-code mapping
    envelope.py                   # universal result/error shape (+ optional rich ext)
    output.py                     # --json / --format md / default human renderers
    secrets.py                    # minimal canonical secrets loader (one .env)
  connectors/
    __init__.py                   # iterates subpackages, collects CONNECTOR specs
    notion/
      __init__.py                 # CONNECTOR = ConnectorSpec(...); from .commands import register
      client.py                   # NotionClient — API logic only
      commands.py                 # argparse register() + run_* handlers
    gmail/  calendar/  drive/  meetgeek/  telegram/  github/  research/  fetch/

tests/                            # OUTSIDE the package — not shipped in wheel
  connectors/
    notion/
      test_client.py              # API coverage, mocked transport
      test_commands.py            # CLI contract: exit codes, output shape
  core/
    test_registry.py
    test_envelope.py
    test_errors.py
```

A connector MAY grow internal modules (`models.py`, `formatters.py`, `webhooks.py`,
`transcripts.py`, `providers/`, `strategy.py`) inside its own package. The 2-file shape is the
minimum, not a cap. `research`/`fetch` are expected to be "thick" (search+retry+envelope;
provider ladder direct→jina→…).

## 4. Connector Contract

Every `h2t/connectors/<name>/` MUST export, via its `__init__.py`:

```python
# h2t/connectors/notion/__init__.py
from h2t.core.registry import ConnectorSpec
from .commands import register            # safe: commands.py has NO heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="notion",
    help="Work with Notion pages and databases",
    client="h2t.connectors.notion.client:NotionClient",   # LAZY string ref
    register=register,
)
```

| Symbol | Purpose |
|---|---|
| `CONNECTOR: ConnectorSpec` | registry entry (name, help, lazy client ref, register fn) |
| `register(subparsers)` | adds `h2t <name> …` subcommands to the shared parser |
| `<Name>Client` (in `client.py`) | all API logic, importable, no argparse/print/sys.exit |
| `tests/connectors/<name>/` | API-coverage + CLI-contract tests (outside the package) |

### 4.1 Import discipline (resolves ConnectorSpec × lazy-import tension)

This is the load-bearing rule. Building the registry / `h2t connectors list` / `h2t --help`
MUST NOT import any SDK, read secrets, do OAuth, or hit the network.

- `connectors/<name>/__init__.py`: defines `CONNECTOR`, does `from .commands import register`.
- `commands.py`: module level contains **only** argparse wiring and `register()`. It MUST NOT
  `from .client import …` at module scope. Each handler imports the client locally:
  ```python
  def run_get(args):
      from h2t.connectors.notion.client import NotionClient   # imported at exec time only
      client = NotionClient()
      ...
  ```
- `ConnectorSpec.client` is a `"module:attr"` string. `core.registry` resolves it only when a
  command actually runs (or an explicit health check asks). `connectors list`/`--help` never
  trigger resolution.
- `client.py` MAY import its SDK at module level **only if that dependency is declared in
  `pyproject` project deps** (always installed → import cannot fail at exec time). If the SDK is
  an **optional** dependency, it MUST be imported inside `__init__`/first use and a missing
  import converted to `ConfigError` with an install hint (e.g. "pip install h2t[telegram]"),
  never an uncaught `ImportError`. Expensive SDK construction/auth is always deferred to
  `<Name>Client.__init__` or first use. (The "registry build = zero heavy imports" test guards
  discovery; this rule guards execution-time import failures for optional deps.)

### 4.2 Layer boundary (the duality)

- `client.py` knows nothing about argparse, stdout, or `sys.exit`. It raises typed
  `core.errors` exceptions and returns plain Python objects.
- `commands.py` parses args, calls the client, renders output via `core.output`, maps
  `core.errors` → exit codes. No HTTP/SDK logic.
- POS imports `from h2t.connectors.notion.client import NotionClient`; the agent calls
  `h2t notion …`. Both hit the same logic. The CLI is a thin adapter, not a second implementation.

## 5. Error Model & Exit Codes

`core/errors.py`:

```python
class H2TError(Exception): ...
class UsageError(H2TError): ...      # bad args / unknown subcommand
class ConfigError(H2TError): ...     # secrets/config missing
class AuthError(H2TError): ...       # auth/permission denied by provider
class ProviderError(H2TError): ...   # provider returned an error / runtime failure
class NotFoundError(H2TError): ...   # required resource missing / empty
class NetworkError(H2TError): ...    # connectivity / timeout
```

Canonical exit-code table (the standard; **supersedes** legacy `exa_search.py` codes):

| Code | Meaning | Exception |
|---|---|---|
| 0 | ok | — |
| 1 | runtime / provider error | `ProviderError` |
| 2 | usage / bad args | `UsageError` |
| 3 | config / secrets missing | `ConfigError` |
| 4 | auth / permission error | `AuthError` |
| 5 | not found / empty required resource | `NotFoundError` |
| 6 | network / timeout | `NetworkError` |

`commands.py` does the mapping in one place (a shared decorator/wrapper in `core`), so no
connector hand-rolls `print("Error: …")` again.

**Legacy note:** `exa_search.py` currently uses 1=args, 2=api, 3=net, 4=env. Remapping
research/fetch to the table above, plus rewriting the research `SKILL.md` error table and
`docs/superpowers/specs/2026-05-07-research-provider-envelope.md`, is **explicitly ТЗ-2**, not
ТЗ-0.

## 6. Output Contract

Every command supports:

| Flag | Output |
|---|---|
| `--json` | raw machine-readable result (stable schema) |
| `--format md` | readable markdown/table |
| *(default)* | concise human text |

Success envelope (when `--json`):
```json
{ "ok": true, "provider": "notion", "result": { ... } }
```
Error envelope (stderr, when `--json`; non-zero exit always):
```json
{ "ok": false, "provider": "notion",
  "error": { "type": "auth", "message": "...", "hint": "Set NOTION_API_TOKEN" } }
```

`core/envelope.py` owns this universal shape. The richer research/fetch provider-status
envelope (`status: OK/DEGRADED/FAILED`, retry telemetry, cost) is an **optional extension**
nested under `result`/`meta` for search-like connectors only — it is NOT imposed on connectors
that have no retry/fallback semantics. The rich envelope is specified in ТЗ-2.

## 7. Distribution (amended per §2 Identity Decision)

- `pyproject.toml`: distribution `name = "h2t-ops"`; `[project.scripts] h2t-ops =
  "h2t_ops.cli:main"`; import package = `h2t_ops` (drop `lib*` include and the
  `sys.path.insert`). It MUST NOT declare a top-level `h2t` package or an `h2t` console
  script — that identity belongs to `h2t-ai`.
- Install: `uv tool install` from the repo / git ref → global `h2t-ops` command, no venv
  activation, cross-platform via `uv`. Update: `uv tool upgrade h2t-ops`.
- External sharing: a non-infra user runs one `uv tool install` and gets every connector
  under the unambiguous `h2t-ops` name (no clash with anyone's existing `h2t`).
- `h2t-ai` MAY depend on `h2t-ops` (e.g. via `[project.optional-dependencies]`, the same way
  it already composes `h2t-graphs`) and later expose an umbrella bridge so `h2t notion …`
  delegates to `h2t-ops notion …` — **without rewriting the DCC CLI**. That delegation is a
  documented follow-up, explicitly OUT of ТЗ-0.
- Availability is a **CLI-level contract, not a shell idiom**: `h2t-ops --version` exits 0
  when installed; `h2t-ops doctor` reports install path, version, resolvable connectors, and
  secrets presence (no network). Skills probe with a single bare command (`h2t-ops --version`)
  — no glob, no `$VAR`, no `{ …; }`, identical on POSIX and PowerShell, no `simple_expansion`
  prompt. "Not installed → run setup" guidance lives in `SKILL.md` prose.
- `h2t-core:setup` is updated to perform/repair the `uv tool install` of `h2t-ops` (mechanics
  in the ТЗ-0 plan).

## 8. SKILL.md Contract

A connector's `SKILL.md` is a usage guide for the agent, not just a bootstrap. It MUST contain:
connector overview, every subcommand with flags, worked invocation examples, the error/exit-code
table, required secrets, and "when to use / when not to use". Content mirrors
`h2t-ops <connector> --help` so the agent does not round-trip to discover capabilities.

**Agent-facing wording rule (per §2 Identity Decision):** SKILL.md MUST instruct agents to
call `h2t-ops <connector> …` directly — NOT `h2t <connector> …`. Add this note verbatim:
> In the internal umbrella CLI, `h2t <connector> …` may be available later via h2t-ai
> delegation. Skills should call `h2t-ops …` directly unless a project explicitly provides
> the umbrella bridge.

**Scope guard:** authoring rich SKILL.md for *all* skills is per-connector, non-blocking polish
done lazily. Functional connector migration ≠ SKILL.md rewrite. ТЗ-0 ships only Notion's SKILL.md
to the new contract as the reference.

## 9. POS Consumption

POS (FastAPI) imports the canonical client: `from h2t.connectors.notion.client import
NotionClient`. POS MAY also shell out to `h2t notion …` for parity with agents. POS's existing
`src/api/app/services/notion.py` becomes a thin adapter over the canonical client (its
consolidation is tracked in ТЗ-1/ТЗ-2, not ТЗ-0). POS requirements may *extend* the connector
list (e.g. `github`) but do not alter this CLI design.

## 10. Migration Discipline (bounded, not infinite)

The migration is tractable because of three rules, which are part of this standard:

1. **Re-wrap, not rewrite.** Existing working `XClient` → `h2t/connectors/x/client.py` is a
   mechanical transform: strip `print`/`sys.exit`; raise typed `core.errors` instead of error
   strings. API calls, auth, pagination untouched. Hours per connector, diff-reviewable.
2. **Backward-compatible alias = no big-bang.** `h2t ingest notion` and the current SKILL.md
   keep working via a deprecation shim forwarding to `h2t notion`. No moment requires rewriting
   everything at once. Skills update SKILL.md one at a time, when convenient.
   **Shim policy (decided):** the shim emits a one-line deprecation notice to **stderr** when
   output is human/`--format md`, and is **silent** when `--json` (machine consumers must not
   get noise). Exit code is unchanged (forwards the wrapped command's code). No "warn once" /
   no state file — emitting on every human invocation is acceptable and stateless.
3. **Finite countable list + runbook.** 9 connectors, sequenced; the runbook derived from the
   Notion skeleton turns connectors #2..#9 into a checklist. Each is an independent shippable
   PR; the system is coherent if paused between any two connectors (migrated → new standard,
   un-migrated → alias).

## 11. Scope

**In ТЗ-0:**
- `h2t/` package replacing `lib/`; `pyproject` → `h2t.cli:main`; no `sys.path.insert`
- `core/registry.py` (ConnectorSpec, lazy registry), `core/errors.py`, `core/envelope.py`,
  `core/output.py`, `core/secrets.py` (minimal — single canonical `.env`)
- Notion connector as walking skeleton (`client.py` re-wrapped from `lib/clients/notion.py`,
  `commands.py`)
- Backward-compatible / deprecated route for old `h2t ingest notion`
- Tests: `tests/core/` (registry, envelope, errors) + `tests/connectors/notion/`
  (client mocks, CLI contract)
- Notion `SKILL.md` updated to the §8 contract (reference example only)

**Out of ТЗ-0:**
- Migration of gmail/calendar/drive/meetgeek/telegram → ТЗ-1
- research/fetch provider ladder + legacy exit-code remap + rich provider envelope → ТЗ-2
- `core/http.py` (retry/backoff) — only research/fetch need it → ТЗ-2
- Full multi-provider secrets framework → later
- Consolidating `h2t-business/notion_*.py` and `POS/.../notion.py` onto the canonical client
  → ТЗ-1/ТЗ-2

**Sequence:**
- **ТЗ-0** — standard + `core/` foundation + Notion walking skeleton *(this doc)*
- **ТЗ-1** — migration wave: gmail, calendar, drive, meetgeek, telegram + runbook
- **ТЗ-2** — research/fetch special connectors + `core/http.py` + legacy exit-code remap +
  rich provider envelope

## 12. Definition of Done (ТЗ-0)

- [ ] `h2t --version` exits 0 (the cross-platform availability contract, §7)
- [ ] `h2t notion --help` works
- [ ] `from h2t.connectors.notion.client import NotionClient` works
- [ ] `pyproject.toml` `[project.scripts]` → `h2t.cli:main`; no `sys.path.insert` anywhere
- [ ] `h2t connectors list` / `h2t --help` build the registry **without** importing the Notion
      SDK, reading secrets, or doing OAuth (lazy discipline verified by test)
- [ ] Notion `client.py` raises typed `core.errors`; `commands.py` maps them to the §5 codes
- [ ] `--json` / `--format md` / default outputs conform to §6
- [ ] `tests/connectors/notion/` covers client (mocked) + CLI contract; `tests/core/` covers
      registry, envelope, errors — all green
- [ ] Old `h2t ingest notion` still works and follows the §10 shim policy (stderr notice on
      human output, silent on `--json`, forwarded exit code)
- [ ] Notion `SKILL.md` conforms to §8

## 13. Testing Standard (ТЗ-0 portion)

- Tests live in `tests/`, never inside the package (wheel stays clean).
- `test_client.py`: API coverage with mocked transport — happy path + each typed error
  (`Config/Auth/Provider/NotFound/Network`) for every public client method.
- `test_commands.py`: CLI contract — for each subcommand assert exit code per §5, `--json`
  schema per §6, and that registry build performs zero heavy imports (lazy discipline test).
- `tests/core/`: `ConnectorSpec` resolution laziness, exit-code mapping, envelope shapes.
- Full per-connector API-coverage matrix is defined in ТЗ-1/ТЗ-2; ТЗ-0 establishes the pattern.

## 14. Risks / Open

- `uv tool install` from a private GitHub ref vs PyPI vs local path — pick in the ТЗ-0
  implementation plan (affects external sharing UX).
- ~~Deprecation shim policy~~ — **decided in §10** (stderr on human output, silent on
  `--json`, forwarded exit code, stateless). No longer open.
- `core/secrets.py` "minimal" boundary: ТЗ-0 only needs Notion's token path; do not pre-build
  the multi-provider framework.
