---
name: kb
description: "Use when working with the Ecosystem Research KB or any llm-kb-template instance: knowledge base, база знаний, add to the knowledge base / добавить в базу знаний, learn from the knowledge base / узнать из базы знаний, search and add to the KB / поискать и добавить в базу знаний, ground a decision in the KB, kb-ingest, kb-lint, kb-lookup, KB health. Human-invoked; ingest is COST-GATED."
compatibility: "Requires the installed llm-kb-engine tool (uv tool install), a data-only KB whose location is given by H2T_KB_ROOT, and the h2t-ops research connector for ingest harvest."
metadata:
  author: lichtpfad
  version: 0.1.5
---

# h2t-ops:kb

One entry point for the shared Ecosystem Research KB (an `llm-kb-template` instance). Three modes; read the mode file before acting.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Resolve the KB root (all modes)

```bash
if [ -z "${H2T_KB_ROOT:-}" ]; then
  echo "ERROR: set H2T_KB_ROOT to your knowledge-base directory." >&2
  echo "  export H2T_KB_ROOT=\"$HOME/research-kb\"" >&2
  exit 3
fi
KB="$H2T_KB_ROOT"
```

There is no default worth guessing. The previous one named a directory on one Windows
machine, which resolves to nothing anywhere else, so the skill failed later and further
from the cause than it needed to.

The engine is the installed `llm-kb-engine` tool (`uv tool install`), NOT a KB-local `.venv`. It
exposes cwd-independent console-scripts driven with `--repo "$KB"`: `run <stage>`, `kb-lint`,
`kb-index`, `kb-parse-claims`, `kb-council`. One module (`pipeline.grade.orchestrate`) has no
console-script — the ingest mode resolves an `ENGINE_PY` for it. Each mode file names what it needs.

## Guardrails (all modes)

- **Python never calls an LLM** — agents are dispatched only via the Agent tool, between deterministic Python stages.
- **Council never skipped under `--strict`** — poisoning the KB is worst where the operator is blind.
- One stage per CLI call. Frequent small commits. `git mv` / `git rm` only.

## Routing

| Intent | Action |
|---|---|
| Fill the KB from research (ingest, наполни KB, add to knowledge base, зафиксируй ресёрч) | **REQUIRED:** read `references/ingest.md` and follow it before any ingest action (it holds the cost-gate). |
| Read / retrieve KB material (show sources on X, what do we have on, покажи материалы по) | **REQUIRED:** read `references/query.md` and follow the `read` intent (no council gate — material is surfaced with its status as a label). |
| Ground a decision in the KB (ground, заземли, узнать из базы знаний, kb-lookup, look up in KB) | **REQUIRED:** read `references/query.md` and follow the `ground` intent (council-PASS gate is mandatory). |
| Check KB integrity (lint, проверь KB, KB health) | **REQUIRED:** read `references/lint.md` and follow it. |
| Compound: search AND add (поискать и добавить в базу знаний, search and add to the KB) | **REQUIRED:** read `references/query.md` first; only if its gap-fill fires, then read `references/ingest.md`. Query-then-ingest, not a fourth mode. |
