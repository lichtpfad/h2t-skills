---
name: research-agent
description: "DEPRECATED. Use /research (Exa, h2t-ops plugin) for semantic research or /search-leads (Anysite, BayramAnnakov plugin) for LinkedIn lead generation. See lichtpfad/h2t-skills#69 for rationale."
tools:
  - Read
---

# research-agent — DEPRECATED

This agent is deprecated as of 2026-04-18.

## What to use instead

| You want... | Use |
|---|---|
| Web search, news, academic papers, company/people research | `/research` (h2t-ops:research skill, Exa engine) |
| LinkedIn lead generation, ICP-driven prospect lists | `/search-leads` (BayramAnnakov/lead-search plugin, Anysite engine) |
| Instagram, Reddit, Twitter, YouTube scraping | `/search-leads` (covers these via Anysite) |

## Why deprecated

See issue lichtpfad/h2t-skills#69. Root causes:

1. **Silent fallback** — sub-agent silently fell back to WebSearch when Exa MCP tools were not injected into its toolset, then misdiagnosed this as "permission blocked".
2. **Authoritative unsourced synthesis** — agent wrote findings without URL + verbatim quotes, presenting general-knowledge summaries as facts.

Replacement design: `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`.

## Do not call this agent

If `Task(subagent_type=research-agent, ...)` is invoked, the caller should stop and switch to the slash commands above. This file exists only as a pointer.
