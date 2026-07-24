# kb — lint mode

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`

Thin wrapper over the engine's `lint_wiki.py` (config-bound source-type / verdict / council checks). Read-only.

```bash
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/"        # all pages; or a single wiki/<slug>.md
```

Exit 0 = all pages PASS; non-zero = at least one violation (printed per page). On FAIL, report the offending pages + first violations; do not "fix" content silently — a lint failure on a KB page means the claim/verdict/council data is malformed and needs the operator or a kb re-ingest (mode: ingest), not a cosmetic patch.
