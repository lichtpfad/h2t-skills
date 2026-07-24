---
name: h2t-ops:kb
description: "Use when working with the Ecosystem Research KB or any llm-kb-template instance: knowledge base, база знаний, add to the knowledge base / добавить в базу знаний, learn from the knowledge base / узнать из базы знаний, search and add to the KB / поискать и добавить в базу знаний, ground a decision in the KB, kb-ingest, kb-lint, kb-lookup, KB health. Human-invoked; ingest is COST-GATED."
compatibility: "Requires an llm-kb-template instance (default C:/dev/research-kb, override H2T_KB_ROOT) with its .venv, and the h2t-ops research connector for ingest harvest."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:kb

One entry point for the shared Ecosystem Research KB (an `llm-kb-template` instance). Three modes; read the mode file before acting.

## Resolve the KB root (all modes)

```bash
KB="${H2T_KB_ROOT:-C:/dev/research-kb}"
PY="$KB/.venv/Scripts/python"      # Windows; Linux/mac: $KB/.venv/bin/python
```

## Guardrails (all modes)

- **Python never calls an LLM** — agents are dispatched only via the Agent tool, between deterministic Python stages.
- **Council never skipped under `--strict`** — poisoning the KB is worst where the operator is blind.
- One stage per CLI call. Frequent small commits. `git mv` / `git rm` only.

## Routing

| Intent | Action |
|---|---|
| Fill the KB from research (ingest, наполни KB, add to knowledge base, зафиксируй ресёрч) | **REQUIRED:** read `references/ingest.md` and follow it before any ingest action (it holds the cost-gate). |
| Ground a decision in the KB (ground, заземли, узнать из базы знаний, kb-lookup, look up in KB) | **REQUIRED:** read `references/query.md` and follow it before grounding. |
| Check KB integrity (lint, проверь KB, KB health) | **REQUIRED:** read `references/lint.md` and follow it. |
| Compound: search AND add (поискать и добавить в базу знаний, search and add to the KB) | **REQUIRED:** read `references/query.md` first; only if its gap-fill fires, then read `references/ingest.md`. Query-then-ingest, not a fourth mode. |
