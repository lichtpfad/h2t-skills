---
name: h2t-ops:kb-lint
description: "Health-check the Ecosystem Research KB: run the engine's YAML schema linter over the wiki pages and report PASS/FAIL. Use before/after kb-ingest or to audit KB integrity. Triggers: 'kb-lint', 'lint the KB', 'проверь KB', 'KB health'."
compatibility: "Requires the research-kb instance (default C:/dev/research-kb, override H2T_KB_ROOT) with its .venv."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:kb-lint

Thin wrapper over the engine's `lint_wiki.py` (config-bound source-type / verdict / council
checks). Read-only.

```bash
KB="${H2T_KB_ROOT:-C:/dev/research-kb}"
PY="$KB/.venv/Scripts/python"        # Windows; Linux/mac: $KB/.venv/bin/python
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/"        # all pages; or a single wiki/<slug>.md
```

Exit 0 = all pages PASS; non-zero = at least one violation (printed per page). On FAIL, report
the offending pages + first violations; do not "fix" content silently — a lint failure on a KB
page means the claim/verdict/council data is malformed and needs the operator or a kb-ingest
re-run, not a cosmetic patch.
