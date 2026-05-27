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

- focused routing/client/command tests: PASS (`117 passed in 0.81s`)
- full research test suite: PASS (`299 passed in 1.66s`)
- provider status command: PASS (`kind=research_provider_status`)
- fetch route selected provider: `direct`
- search provider readiness: `exa configured=true`

## Notes

- Routing smoke did not call provider networks.
- Missing required provider keys are handled before provider artifact writes.
- `JINA_API_KEY` remains optional for fetch.
