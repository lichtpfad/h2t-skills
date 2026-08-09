# kb — lint mode

> Resolve `KB` per SKILL.md § "Resolve the KB root": `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"`.
> The engine is the installed `llm-kb-engine` tool; `kb-lint` is a console-script (data-only model).

Thin wrapper over the engine's `kb-lint` (config-bound source-type / verdict / council checks). Read-only.

```bash
kb-lint --repo "$KB"                    # all pages (default: $KB/wiki); or add "$KB/wiki/<slug>.md" for one
```

Exit 0 = all pages PASS; non-zero = at least one violation (printed per page). On FAIL, report the offending pages + first violations; do not "fix" content silently — a lint failure on a KB page means the claim/verdict/council data is malformed and needs the operator or a kb re-ingest (mode: ingest), not a cosmetic patch.
