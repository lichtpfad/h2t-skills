# Research Provider Key Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a predictable provider/key routing layer for `h2t-ops research` so agents can inspect provider readiness, choose a viable route before execution, and fail before side effects when required provider keys are missing.

**Architecture:** Introduce a small read-only routing module beside the existing research store/navigation/maintenance modules. The module exposes provider capability metadata and local secret readiness without making network calls. CLI commands `research providers` and `research route` make the decision surface visible, then `ResearchClient` uses the same route preflight before Exa-backed commands.

**Tech Stack:** Python stdlib, existing `h2t_ops.connectors.research` client/CLI patterns, existing `resolve_secret()` secret lookup, pytest.

---

## Issue And Boundary

GitHub issue: `#194 research: provider/key routing`.

This plan only implements local provider/key routing and readiness checks.

In scope:

- `h2t-ops research providers`
- `h2t-ops research route --capability <capability>`
- provider capability registry for the current research surfaces
- deterministic missing-key errors before artifact writes
- skill documentation for provider/key routing
- smoke evidence

Out of scope:

- POS ingestion
- `ProjectResearchLink` / `ResearchEntityLink`
- semantic provider ranking
- adding new providers
- live network health checks
- automatic purchase/creation of provider API keys
- changing fetch ladder provider internals beyond consuming route metadata

## Provider Model

The v1 routing model is deliberately small.

Provider capability names:

- `preflight`
- `search`
- `answer`
- `similar`
- `crawl`
- `author`
- `fetch`
- `visual_ocr`

Provider IDs:

- `exa`
- `direct`
- `jina`
- `youtube_transcript`
- `visual_ocr`

Secret policy:

- `exa` requires `EXA_API_KEY`
- `direct` requires no secret
- `jina` may use `JINA_API_KEY`, but it is optional in the current fetch ladder
- `youtube_transcript` requires no secret
- `visual_ocr` requires no secret

Route rule:

- If a capability has at least one configured provider, route to the first provider by static priority.
- If no provider is configured, raise `UsageError` before provider calls and before artifact writes.
- `fetch` can route without keys through `direct`.
- Exa-backed `preflight`, `search`, `answer`, `similar`, `crawl`, and `author` must fail before side effects when `EXA_API_KEY` is missing.

Secret-read errors:

- Missing/unreadable/malformed secret sources are treated as provider-not-configured in this v1 routing layer.
- The routing layer must not expose secret file contents or low-level secret parser details.
- The selected route error should be a `UsageError` with a fix hint, because the operator action is to configure a usable provider key before running the provider-backed command.

## File Structure

- Create: `h2t_ops/connectors/research/provider_routing.py`
  - Static provider/capability registry.
  - Secret readiness checks.
  - Route selection envelopes.
  - No network calls and no artifact writes.
- Create: `tests/connectors/research/test_provider_routing.py`
  - Unit tests for registry, readiness, route selection, and missing-key behavior.
- Modify: `h2t_ops/connectors/research/client.py`
  - Add thin client wrappers.
  - Use route preflight before Exa-backed commands.
- Modify: `h2t_ops/connectors/research/commands.py`
  - Add parser/dispatch for `providers` and `route`.
- Modify: `tests/connectors/research/test_client.py`
  - Tests for client wrappers and fail-before-side-effects.
- Modify: `tests/connectors/research/test_commands.py`
  - Parser/dispatch tests and skill documentation assertions.
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
  - Document provider readiness and routing commands.
- Create: `docs/reports/2026-05-27-research-provider-key-routing-smoke.md`
  - Local smoke evidence.

## Contracts To Preserve

- `research providers` and `research route` are read-only.
- Routing checks do not call provider networks.
- Missing required keys produce `UsageError`, not `ProviderError`.
- Missing required keys are reported before writing provider artifacts, objects, indexes, or telemetry.
- Existing `fetch --provider auto` behavior remains valid.
- `JINA_API_KEY` remains optional for `fetch`.
- `--json` works on both routing commands through the existing top-level emitter.
- Do not touch `uv.lock`.

---

### Task 0: Branch And Worktree Hygiene

**Files:**
- No file edits.

- [ ] **Step 1: Check current branch and dirty state**

Run:

```powershell
git status -sb
```

Expected:

- Worktree is clean except this plan file if the plan has not been committed yet.
- If the current branch is not `main`, do not implement from the current branch.
- Do not stage unrelated files.

- [ ] **Step 2: Sync remote state**

Run:

```powershell
git fetch origin --prune
```

Expected:

- `origin/main` is current.

- [ ] **Step 3: Create the feature branch from remote main**

Run:

```powershell
git switch --create codex-research-provider-key-routing origin/main
```

Expected:

- Current branch is `codex-research-provider-key-routing`.
- Branch base is `origin/main`.

If the branch already exists locally, run:

```powershell
git switch codex-research-provider-key-routing
git rebase origin/main
```

Expected:

- Rebase completes without conflicts.

- [ ] **Step 4: Re-check status**

Run:

```powershell
git status -sb
```

Expected:

- Current branch is `codex-research-provider-key-routing`.
- No unrelated dirty files are staged.

---

### Task 1: Add Provider Routing Helper Module

**Files:**
- Create: `h2t_ops/connectors/research/provider_routing.py`
- Create: `tests/connectors/research/test_provider_routing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/connectors/research/test_provider_routing.py`:

```python
from __future__ import annotations

import pytest

from h2t_ops.connectors.research import provider_routing
from h2t_ops.core.errors import UsageError


def test_provider_status_reports_missing_required_exa_key(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    result = provider_routing.provider_status()

    exa_search = [
        item for item in result["providers"]
        if item["provider"] == "exa" and item["capability"] == "search"
    ][0]
    assert result["kind"] == "research_provider_status"
    assert exa_search["configured"] is False
    assert exa_search["missing_secrets"] == ["EXA_API_KEY"]
    assert exa_search["reason"] == "missing_required_secret"


def test_provider_status_marks_direct_and_jina_fetch_available_without_keys(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    result = provider_routing.provider_status(capability="fetch")
    rows = {(item["provider"], item["capability"]): item for item in result["providers"]}

    assert rows[("direct", "fetch")]["configured"] is True
    assert rows[("direct", "fetch")]["reason"] == "available"
    assert rows[("jina", "fetch")]["configured"] is True
    assert rows[("jina", "fetch")]["optional_missing_secrets"] == ["JINA_API_KEY"]
    assert rows[("jina", "fetch")]["reason"] == "available_optional_secret_missing"


def test_select_route_picks_exa_when_key_exists(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: name == "EXA_API_KEY")

    result = provider_routing.select_route("search")

    assert result["kind"] == "research_provider_route"
    assert result["capability"] == "search"
    assert result["selected_provider"] == "exa"
    assert result["configured"] is True


def test_select_route_raises_usage_error_when_required_key_missing(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        provider_routing.select_route("answer")


def test_select_route_rejects_unknown_capability():
    with pytest.raises(UsageError, match="unknown research capability"):
        provider_routing.select_route("unknown")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_provider_routing.py -q
```

Expected:

- FAIL with import error for `h2t_ops.connectors.research.provider_routing`

- [ ] **Step 3: Implement the routing helper**

Create `h2t_ops/connectors/research/provider_routing.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from h2t_ops.core.errors import UsageError


CAPABILITIES = {
    "preflight",
    "search",
    "answer",
    "similar",
    "crawl",
    "author",
    "fetch",
    "visual_ocr",
}


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    capability: str
    required_secrets: tuple[str, ...] = ()
    optional_secrets: tuple[str, ...] = ()
    priority: int = 100
    notes: str = ""


PROVIDER_CAPABILITIES: tuple[ProviderCapability, ...] = (
    ProviderCapability("exa", "preflight", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "search", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "answer", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "similar", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "crawl", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "author", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("direct", "fetch", priority=10),
    ProviderCapability(
        "jina",
        "fetch",
        optional_secrets=("JINA_API_KEY",),
        priority=20,
        notes="Jina Reader can run without a key in the current fetch ladder.",
    ),
    ProviderCapability("youtube_transcript", "fetch", priority=30),
    ProviderCapability("visual_ocr", "visual_ocr", priority=10),
)


def _secret_available(name: str) -> bool:
    from h2t_ops.connectors.research.client import resolve_secret

    try:
        return bool(resolve_secret(name))
    except Exception:
        return False


def _row(capability: ProviderCapability) -> dict[str, Any]:
    missing_required = [
        name for name in capability.required_secrets if not _secret_available(name)
    ]
    missing_optional = [
        name for name in capability.optional_secrets if not _secret_available(name)
    ]
    configured = not missing_required
    if missing_required:
        reason = "missing_required_secret"
    elif missing_optional:
        reason = "available_optional_secret_missing"
    else:
        reason = "available"
    return {
        "provider": capability.provider,
        "capability": capability.capability,
        "configured": configured,
        "required_secrets": list(capability.required_secrets),
        "optional_secrets": list(capability.optional_secrets),
        "missing_secrets": missing_required,
        "optional_missing_secrets": missing_optional,
        "priority": capability.priority,
        "reason": reason,
        "notes": capability.notes,
    }


def provider_status(*, capability: str | None = None) -> dict[str, Any]:
    if capability is not None and capability not in CAPABILITIES:
        raise UsageError(f"unknown research capability: {capability}")
    rows = [
        _row(item)
        for item in sorted(PROVIDER_CAPABILITIES, key=lambda item: (item.capability, item.priority, item.provider))
        if capability is None or item.capability == capability
    ]
    return {
        "kind": "research_provider_status",
        "capability": capability,
        "providers": rows,
    }


def select_route(capability: str, *, provider: str | None = None) -> dict[str, Any]:
    if capability not in CAPABILITIES:
        raise UsageError(f"unknown research capability: {capability}")
    rows = provider_status(capability=capability)["providers"]
    if provider:
        rows = [row for row in rows if row["provider"] == provider]
        if not rows:
            raise UsageError(
                f"research provider {provider!r} does not support capability {capability!r}"
            )
    configured = [row for row in rows if row["configured"]]
    if not configured:
        missing = sorted(
            {
                secret
                for row in rows
                for secret in row.get("missing_secrets", [])
            }
        )
        hint = (
            f"Set {', '.join(missing)} in env, H2T_SECRETS_FILE, "
            "~/.dor/secrets/secrets.env, or ~/.dor/secrets.env."
            if missing
            else "Enable or configure a provider for this capability."
        )
        raise UsageError(
            f"no configured research provider for capability: {capability}",
            hint=hint,
        )
    selected = sorted(configured, key=lambda row: (row["priority"], row["provider"]))[0]
    return {
        "kind": "research_provider_route",
        "capability": capability,
        "requested_provider": provider,
        "selected_provider": selected["provider"],
        "configured": True,
        "route": selected,
        "candidates": rows,
    }
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_provider_routing.py -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/provider_routing.py tests/connectors/research/test_provider_routing.py
git commit -m "feat(research): add provider key routing helpers"
```

---

### Task 2: Expose Routing Through ResearchClient

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Write failing client tests**

Append to `tests/connectors/research/test_client.py`:

```python
def test_research_client_lists_provider_status(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    calls = []

    def fake_status(*, capability=None):
        calls.append(capability)
        return {"kind": "research_provider_status", "capability": capability}

    monkeypatch.setattr(provider_routing, "provider_status", fake_status)

    result = client.ResearchClient(output_dir=tmp_path).research_provider_status(
        capability="fetch"
    )

    assert result == {"kind": "research_provider_status", "capability": "fetch"}
    assert calls == ["fetch"]


def test_research_client_selects_provider_route(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    calls = []

    def fake_select(capability, *, provider=None):
        calls.append((capability, provider))
        return {
            "kind": "research_provider_route",
            "capability": capability,
            "selected_provider": provider or "exa",
        }

    monkeypatch.setattr(provider_routing, "select_route", fake_select)

    result = client.ResearchClient(output_dir=tmp_path).research_route(
        "search",
        provider="exa",
    )

    assert result["selected_provider"] == "exa"
    assert calls == [("search", "exa")]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -k "provider_status or selects_provider_route" -q
```

Expected:

- FAIL because `ResearchClient` has no routing wrapper methods.

- [ ] **Step 3: Add client wrappers**

In `h2t_ops/connectors/research/client.py`, change the existing import:

```python
from h2t_ops.connectors.research import maintenance, navigation, store
```

to:

```python
from h2t_ops.connectors.research import maintenance, navigation, provider_routing, store
```

Add these methods near the existing navigation/maintenance wrappers:

```python
    def research_provider_status(
        self,
        *,
        capability: str | None = None,
    ) -> dict[str, Any]:
        """Return local provider/key readiness without network calls."""
        return provider_routing.provider_status(capability=capability)

    def research_route(
        self,
        capability: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Select a configured provider route for a research capability."""
        return provider_routing.select_route(capability, provider=provider)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -k "provider_status or selects_provider_route" -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): expose provider routing client methods"
```

---

### Task 3: Add CLI Commands

**Files:**
- Modify: `h2t_ops/connectors/research/commands.py`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add failing parser and dispatch tests**

Add these methods to `FakeResearchClient` in `tests/connectors/research/test_commands.py`:

```python
    def research_provider_status(self, *, capability: str | None = None) -> dict:
        self.calls.append(("research_provider_status", {"capability": capability}))
        return {"method": "research_provider_status", "capability": capability}

    def research_route(self, capability: str, *, provider: str | None = None) -> dict:
        self.calls.append(("research_route", {"capability": capability, "provider": provider}))
        return {"method": "research_route", "capability": capability, "provider": provider}
```

Append parser/dispatch tests:

```python
def test_parser_registration_for_research_provider_routing_commands():
    parser = cli.build_parser()

    providers = parser.parse_args(
        [
            "research",
            "providers",
            "--capability",
            "fetch",
            "--json",
        ]
    )
    route = parser.parse_args(
        [
            "research",
            "route",
            "--capability",
            "search",
            "--provider",
            "exa",
            "--json",
        ]
    )

    assert providers.research_cmd == "providers"
    assert providers.capability == "fetch"
    assert providers.as_json is True
    assert route.research_cmd == "route"
    assert route.capability == "search"
    assert route.provider == "exa"
    assert route.as_json is True


def test_run_dispatches_provider_routing_commands(monkeypatch):
    _patch_fake_client(monkeypatch)

    providers = commands.run(
        argparse.Namespace(
            research_cmd="providers",
            output_dir=None,
            capability="fetch",
        )
    )
    route = commands.run(
        argparse.Namespace(
            research_cmd="route",
            output_dir=None,
            capability="search",
            provider="exa",
        )
    )

    assert providers == {"method": "research_provider_status", "capability": "fetch"}
    assert route == {"method": "research_route", "capability": "search", "provider": "exa"}
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected:

- FAIL because parser/dispatch does not support `providers` or `route`.

- [ ] **Step 3: Add parser subcommands**

In `h2t_ops/connectors/research/commands.py`, after `preflight` and before `search`, add:

```python
    providers = cmds.add_parser("providers", help="List research provider/key readiness")
    providers.add_argument(
        "--capability",
        choices=["preflight", "search", "answer", "similar", "crawl", "author", "fetch", "visual_ocr"],
    )
    add_fmt(providers)

    route = cmds.add_parser("route", help="Select a configured research provider route")
    route.add_argument(
        "--capability",
        required=True,
        choices=["preflight", "search", "answer", "similar", "crawl", "author", "fetch", "visual_ocr"],
    )
    route.add_argument("--provider", dest="provider")
    add_fmt(route)
```

- [ ] **Step 4: Add dispatch branches**

In `run(args)`, after the `preflight` branch and before `search`, add:

```python
    if cmd == "providers":
        return client.research_provider_status(capability=args.capability)
    if cmd == "route":
        return client.research_route(args.capability, provider=args.provider)
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -k "provider_routing" -q
```

Expected:

- PASS

- [ ] **Step 6: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/commands.py tests/connectors/research/test_commands.py
git commit -m "feat(research): add provider routing commands"
```

---

### Task 4: Fail Before Side Effects For Exa-Backed Commands

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add failing tests for missing Exa key side-effect boundary**

Append to `tests/connectors/research/test_client.py`:

```python
def test_search_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).search(query="missing key")

    assert not any(tmp_path.iterdir())


def test_answer_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).answer("missing key")

    assert not any(tmp_path.iterdir())


def test_similar_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).similar("https://example.com")

    assert not any(tmp_path.iterdir())


def test_crawl_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com")

    assert not any(tmp_path.iterdir())


def test_resolve_author_missing_exa_key_fails_before_provider_call(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing
    from h2t_ops.connectors.research import author_resolve

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("author provider should not be called without route")

    monkeypatch.setattr(author_resolve, "resolve_author", fail_if_called)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).resolve_author("Ada Lovelace")

    assert not any(tmp_path.iterdir())


def test_preflight_missing_exa_key_fails_before_provider_call(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("exa preflight should not be called without route")

    monkeypatch.setattr(exa, "preflight", fail_if_called)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).preflight()

    assert not any(tmp_path.iterdir())
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -k "missing_exa_key_fails_before_artifact_writes" -q
```

Expected:

- FAIL because current methods call `resolve_secret("EXA_API_KEY")` directly and raise `ConfigError`.

- [ ] **Step 3: Add route preflight helper**

In `ResearchClient`, add this private helper near `_research_root()`:

```python
    def _require_research_route(self, capability: str, *, provider: str | None = None) -> dict[str, Any]:
        """Require a configured local provider route before side effects."""
        return provider_routing.select_route(capability, provider=provider)
```

Then add route preflight before resolving Exa secrets in the following methods:

```python
        self._require_research_route("preflight", provider="exa")
        exa.preflight(resolve_secret("EXA_API_KEY"))
```

```python
        self._require_research_route("search", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
```

```python
        self._require_research_route("similar", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
```

```python
        self._require_research_route("answer", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
```

```python
        self._require_research_route("author", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
```

For `crawl()`, add the same pattern before its first `resolve_secret("EXA_API_KEY")` call:

```python
        self._require_research_route("crawl", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -k "missing_exa_key_fails_before_artifact_writes" -q
```

Expected:

- PASS

- [ ] **Step 5: Run focused client tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -q
```

Expected:

- PASS

- [ ] **Step 6: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "fix(research): fail before side effects on missing provider keys"
```

---

### Task 5: Add End-To-End CLI Tests

**Files:**
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add CLI tests for provider status and route**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_cli_dispatch_lists_research_provider_status(monkeypatch, capsys):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: name == "EXA_API_KEY")

    code = cli.dispatch(
        [
            "research",
            "providers",
            "--capability",
            "search",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "research_provider_status"
    assert payload["result"]["capability"] == "search"
    assert payload["result"]["providers"][0]["provider"] == "exa"
    assert payload["result"]["providers"][0]["configured"] is True


def test_cli_dispatch_routes_fetch_without_keys(monkeypatch, capsys):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    code = cli.dispatch(
        [
            "research",
            "route",
            "--capability",
            "fetch",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "research_provider_route"
    assert payload["result"]["selected_provider"] == "direct"


def test_cli_dispatch_route_missing_exa_key_returns_usage_error(monkeypatch, capsys):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    code = cli.dispatch(
        [
            "research",
            "route",
            "--capability",
            "search",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().err)

    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["type"] == "usage"
    assert "no configured research provider" in payload["error"]["message"]
```

- [ ] **Step 2: Run CLI tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -k "provider_status or routes_fetch_without_keys or route_missing_exa_key" -q
```

Expected:

- PASS

- [ ] **Step 3: Commit**

Run:

```powershell
git add tests/connectors/research/test_commands.py
git commit -m "test(research): cover provider routing cli"
```

---

### Task 6: Update Skill Documentation

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add failing documentation assertion**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_research_skill_documents_provider_key_routing():
    text = Path("plugins/h2t-ops/skills/research/SKILL.md").read_text(encoding="utf-8")

    assert "## Provider Key Routing" in text
    assert "h2t-ops research providers --json" in text
    assert "h2t-ops research route --capability search --json" in text
    assert "EXA_API_KEY is required for search, answer, similar, crawl, and author resolution." in text
    assert "JINA_API_KEY is optional for fetch." in text
    assert "Routing checks are local and do not call provider networks." in text
    assert "Missing required provider keys fail before artifact writes." in text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py::test_research_skill_documents_provider_key_routing -q
```

Expected:

- FAIL because the skill does not yet document provider routing.

- [ ] **Step 3: Update the skill doc**

Add this section to `plugins/h2t-ops/skills/research/SKILL.md` near the command reference:

```markdown
## Provider Key Routing

Use provider routing before dispatching provider-backed research when key availability is uncertain:

```bash
h2t-ops research providers --json
h2t-ops research providers --capability fetch --json
h2t-ops research route --capability search --json
h2t-ops research route --capability fetch --json
```

Rules:

- `EXA_API_KEY` is required for search, answer, similar, crawl, and author resolution.
- `JINA_API_KEY` is optional for fetch.
- `direct` fetch is available without a provider key.
- Routing checks are local and do not call provider networks.
- Missing required provider keys fail before artifact writes.
- If routing reports no configured provider, fix keys/configuration before running the provider command.
```

- [ ] **Step 4: Run docs assertion**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py::test_research_skill_documents_provider_key_routing -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

Run:

```powershell
git add plugins/h2t-ops/skills/research/SKILL.md tests/connectors/research/test_commands.py
git commit -m "docs(research): document provider key routing"
```

---

### Task 7: Focused Verification And Smoke Report

**Files:**
- Create: `docs/reports/2026-05-27-research-provider-key-routing-smoke.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_provider_routing.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q
```

Expected:

- PASS

- [ ] **Step 2: Run full research tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected:

- PASS

- [ ] **Step 3: Run local routing smoke**

Run:

```powershell
uv.exe run h2t-ops research providers --json
uv.exe run h2t-ops research route --capability fetch --json
uv.exe run h2t-ops research providers --capability search --json
```

Expected:

- `providers` returns `kind=research_provider_status`
- `route --capability fetch` returns `selected_provider=direct`
- `providers --capability search` reports Exa configured state based on local `EXA_API_KEY`

- [ ] **Step 4: Record smoke evidence**

Create `docs/reports/2026-05-27-research-provider-key-routing-smoke.md`:

```markdown
---
title: Research Provider Key Routing Smoke
date: 2026-05-27
status: done
issue: 194
---

# Research Provider Key Routing Smoke

## Commands

```powershell
uv.exe run pytest tests/connectors/research/test_provider_routing.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q
uv.exe run pytest tests/connectors/research -q
uv.exe run h2t-ops research providers --json
uv.exe run h2t-ops research route --capability fetch --json
uv.exe run h2t-ops research providers --capability search --json
```

## Result

- focused routing/client/command tests: PASS
- full research test suite: PASS
- provider status command: PASS
- fetch route selected provider: `direct`
- search provider readiness: recorded from local key state

## Notes

- Routing smoke did not call provider networks.
- Missing required provider keys are handled before provider artifact writes.
- `JINA_API_KEY` remains optional for fetch.
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/reports/2026-05-27-research-provider-key-routing-smoke.md
git commit -m "docs(research): record provider routing smoke"
```

---

### Task 8: Final Branch Hygiene And PR

**Files:**
- No code edits expected.

- [ ] **Step 1: Check branch state**

Run:

```powershell
git status -sb
git diff --stat origin/main..HEAD
```

Expected:

- Branch contains only #194 files:
  - `h2t_ops/connectors/research/provider_routing.py`
  - research client/commands changes
  - research tests
  - `plugins/h2t-ops/skills/research/SKILL.md`
  - smoke report
  - this plan
- No `uv.lock` changes.

- [ ] **Step 2: Run final verification**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected:

- PASS

- [ ] **Step 3: Push branch**

Run:

```powershell
git push -u origin codex-research-provider-key-routing
```

- [ ] **Step 4: Open PR**

Run:

```powershell
$body = @"
## Summary
- add local research provider/key readiness routing
- expose research providers and route commands
- fail before side effects when Exa-backed commands are missing EXA_API_KEY
- document routing rules and record smoke evidence

## Tests
- uv.exe run pytest tests/connectors/research -q
- smoke: providers, route --capability fetch, providers --capability search

Closes #194
"@
gh pr create --title "feat(research): add provider key routing" --body $body --base main --head codex-research-provider-key-routing
```

- [ ] **Step 5: Check CI**

Run:

```powershell
gh pr checks <PR_NUMBER> --watch=false
```

Expected:

- Required checks pass or are pending with no immediate failure.

## Self-Review

### Spec coverage

- Provider readiness surface: Task 1, Task 3, Task 5.
- Key routing before execution: Task 1, Task 2, Task 4.
- Missing-key fail-before-side-effects for `preflight`, `search`, `answer`, `similar`, `crawl`, and `author`: Task 4.
- Fetch remains usable without keys: Task 1 and Task 5.
- Jina optional key behavior: Task 1 and Task 6.
- Skill documentation: Task 6.
- Smoke evidence: Task 7.

### Placeholder scan

- No `TBD`, `TODO`, or open-ended "handle errors" instructions.
- `<PR_NUMBER>` appears only in the final reusable PR-check command.
- Code snippets define every new helper name before use.

### Type consistency

- Module functions:
  - `provider_status(capability=None)`
  - `select_route(capability, provider=None)`
- Client methods:
  - `research_provider_status(capability=None)`
  - `research_route(capability, provider=None)`
- CLI commands:
  - `research providers [--capability ...]`
  - `research route --capability ... [--provider ...]`
- Capability strings are consistent across parser choices, tests, and routing registry.
