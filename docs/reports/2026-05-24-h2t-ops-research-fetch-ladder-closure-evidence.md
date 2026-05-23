# h2t-ops Research Fetch Ladder Closure Evidence

**Date:** 2026-05-24
**Issue:** `#98`
**Spec:** `docs/superpowers/specs/2026-05-24-h2t-ops-research-fetch-ladder-closure-design.md`

## Purpose

Capture the minimal real-world smoke evidence required to close `#98` as a
shared fetch-ladder contract issue.

This evidence is about honest classification and provider telemetry, not about
recovering every historical blocked source as `OK`.

## Environment note

Smoke was executed from the repo runtime via:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py ...
```

Reason:

- the checked-in `.venv\Scripts\python.exe` launcher in this environment points
  at a broken `Python311` target;
- the smoke itself is still valid because it exercises the current runtime
  directly.

## Commands and outcomes

### 1. Blocked-source behavior

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://alltd.org/glsl-for-pops-lesson-0/" --provider auto --json --output-dir C:\tmp\h2t-smoke --project t2-smoke
```

Observed:

- `status`: `DEGRADED`
- `provider_used`: `direct`
- `content_type`: `redirect_collapsed`
- `content_gate`: `none`

Telemetry highlights:

- `direct` returned `200` but was classified as `fetch_redirect_collapsed`
- `jina` attempted fallback and ended with `fetch_network_timeout`
- `playwright`, `crawl4ai`, `firecrawl`, `browserless` were skipped as
  `not_configured_stub`

Interpretation:

- the ladder did not silently treat homepage chrome as article success;
- blocked-source behavior is classified honestly.

### 2. Legitimately gated behavior

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://httpbin.org/basic-auth/user/passwd" --provider auto --json --output-dir C:\tmp\h2t-smoke --project t2-smoke
```

Observed:

- `status`: `FAILED`
- `provider_used`: `none`
- `content_type`: `gated`
- `content_gate`: `login_required`

Telemetry highlights:

- `direct` returned `401` and was classified as `fetch_gated_login_required`
- `jina` was not attempted after the hard gate
- stub providers remained skipped

Interpretation:

- hard-gated content is not bypassed;
- the ladder stops honestly on login-required content.

### 3. Fallback and telemetry visibility

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://example.com/" --provider auto --json --output-dir C:\tmp\h2t-smoke --project t2-smoke
```

Observed:

- `status`: `DEGRADED`
- `provider_used`: `jina`
- `content_type`: `short_body`
- `content_gate`: `none`

Telemetry highlights:

- `direct` failed with `fetch_network_timeout`
- `jina` recovered a response and was recorded as the successful fallback path
- stub providers remained skipped

Interpretation:

- provider fallback is visible in the envelope;
- telemetry is sufficient for downstream debugging and adapter reuse.

## Contract check summary

Required closure signals for `#98` are present:

- blocked-source URL classified honestly: yes
- gated/failure path classified honestly: yes
- provider telemetry visible: yes
- stub-provider behavior visible: yes

## Conclusion

This is sufficient evidence to close `#98` as a shared fetch-ladder contract
issue.

Remaining related work belongs elsewhere:

- `#105` — AllTouchDesigner adapter and parser logic
- `#99` — author/channel resolution
- `#136` — public connector/runtime migration for research
