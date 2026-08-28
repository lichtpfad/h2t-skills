---
title: "kb-ingest Multi-Domain — Implementation Plan"
status: "draft"
date: "2026-08-09"
milestone: ""
---
# kb-ingest Multi-Domain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven).
> Steps use checkbox (`- [ ]`) syntax. Two repos: engine tasks run in `C:/dev/llm-kb-template`,
> skill tasks in `C:/dev/h2t-skills`.

**Goal:** Make the `h2t-ops:kb` ingest skill drive a multi-domain KB correctly, and close the
strict-tier engine gap in `parse_claims.py`. Flat KBs stay bit-for-bit unchanged.

**Architecture:** One ingest run = one domain, derived from the `<domain>--<slug>` page slug. The
skill passes the domain-prefixed slug (and `--slug` to honesty); the engine resolves per-domain
config. See `2026-08-09-kb-ingest-multi-domain-design.md`.

**Spec:** `docs/superpowers/specs/2026-08-09-kb-ingest-multi-domain-design.md`

---

## Part 1 — Engine fix (repo: `C:/dev/llm-kb-template`, own branch + PR)

Test runner: `C:/dev/llm-kb-template/.venv/Scripts/pytest`.

### Task E1: `parse_claims` validates judge-prompts against the domain's config

**Files:**
- Modify: `scripts/parse_claims.py` (`main`, line ~96-99)
- Test: `tests/test_parse_claims_domain.py` (create)

- [ ] **Step 1: Branch** — `git -C C:/dev/llm-kb-template checkout -b fix/parse-claims-domain origin/main`

- [ ] **Step 2: Write the failing test**

```python
import sys
from pathlib import Path
REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))


def test_parse_claims_validates_domain_judge_prompts(monkeypatch, capsys):
    """require_all_judge_prompts must run against the slug's domain effective_config, not base."""
    import parse_claims
    seen = {}

    def _fake_require(cfg):
        seen["judges"] = list(cfg.get("judges", []))

    # a multi cfg: base has 2 judges, the 'research' domain overrides to 3
    multi = {"kb_name": "x",
             "base": {"judges": ["b1", "b2"], "judge_prompts": {"b1": "p", "b2": "p"},
                      "source_types": ["blog"]},
             "domains": [{"name": "research",
                          "override": {"judges": ["r1", "r2", "r3"],
                                       "judge_prompts": {"r1": "p", "r2": "p", "r3": "p"},
                                       "source_types": ["blog"]}}]}
    monkeypatch.setattr(parse_claims._kbconfig, "load_config", lambda repo=None: multi)
    monkeypatch.setattr(parse_claims._kbconfig, "require_all_judge_prompts", _fake_require)
    monkeypatch.setattr(parse_claims, "load_claims", lambda slug: ([], 1))
    monkeypatch.setattr(parse_claims, "write_round_header", lambda slug, r: Path("x"))
    monkeypatch.setattr(sys, "argv", ["parse_claims.py", "research--foo"])
    try:
        parse_claims.main()
    except SystemExit:
        pass
    assert seen.get("judges") == ["r1", "r2", "r3"]
```

- [ ] **Step 3: Run to verify it fails** —
  `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_parse_claims_domain.py -v`
  Expected: FAIL — with the old code, `load_config()` returns the raw multi cfg which has **no
  top-level `judges`** (they live under `base`/`domains`), so `_fake_require` records
  `seen["judges"] == []` (not the domain's `["r1","r2","r3"]`). The test still discriminates the
  fix; only after Step 4 does `effective_config(raw, "research")` surface the domain's judges.

- [ ] **Step 4: Implement** — in `scripts/parse_claims.py` `main()`, replace line 99
  (`_kbconfig.require_all_judge_prompts(_kbconfig.load_config())`) with:

```python
    raw = _kbconfig.load_config()
    cfg = _kbconfig.effective_config(raw, _kbconfig.domain_from_slug(slug, raw))
    _kbconfig.require_all_judge_prompts(cfg)
```

  (`slug` is already bound at line 96, before this.)

- [ ] **Step 5: Run to verify it passes** —
  `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_parse_claims_domain.py -v` → PASS.
  Then the council/parse suite: `… pytest tests/ -k "parse_claims or council" -q` → PASS.

- [ ] **Step 6: Full suite** — `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/ -q` → all green
  (flat bit-for-bit preserved).

- [ ] **Step 7: Commit** —
  `git -C C:/dev/llm-kb-template add scripts/parse_claims.py tests/test_parse_claims_domain.py`
  then commit `fix(parse_claims): validate judge-prompts against the slug's domain config`.

- [ ] **Step 8: PR** — codex diff-review (read-only, synchronous), then open PR to `main`.

---

## Part 2 — Skill edits (repo: `C:/dev/h2t-skills`, branch `feat/kb-ingest-multi-domain`)

File: `plugins/h2t-ops/skills/kb/references/ingest.md`. Markdown — no unit tests; verification is
self-review + a manual dry-run (Task S5).

### Task S1: honesty gains `--slug`

- [ ] **Step 1: Edit `ingest.md:40`** — change the honesty command to:
  `$PY -m pipeline.run honesty --harvest harvest.json --verdicts honesty.json --out real.json --repo "$KB" --slug <slug>`

- [ ] **Step 2: Commit** —
  `git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/kb/references/ingest.md`
  then `feat(kb): pass --slug to honesty for multi-domain grading`.

### Task S2: slug-convention + Multi-domain subsection

- [ ] **Step 1: Rewrite the "Pick the target slug" paragraph** (`ingest.md:22-23`) to:

```
Resolve the target **domain and slug** first. Read `$KB/kb.config.json`:
- **Multi-domain KB** (`domains[]` present): choose the domain the topic belongs to (the domain
  list is `kb.config.json.domains[].name`). The page slug is then `<domain>--<topic-slug>`, and the
  stub `$KB/wiki/<domain>--<topic-slug>.md` must exist AND carry a `domain: <domain>` frontmatter
  field. Scaffold it with the engine's `scaffold_topics.py` (it stamps `domain:`); never hand-write
  a stub without the `domain:` field — the linter rejects it. Every `<slug>` below is this
  domain-prefixed value.
- **Flat single-domain KB** (no `domains[]`): `<slug>` is a plain topic slug, no `domain:` field.

One ingest run targets **exactly one domain** — the engine derives it from the slug prefix and
fails loud on a batch that mixes domains.
```

- [ ] **Step 2: Add a short "## Multi-domain KB" subsection** near the top of `ingest.md` (after
  the two-flows list) explaining: one central KB holds many domains via `base ⊕ override`; grading
  config (judges, source-trust, verdicts) is resolved per-domain from the slug; flat KBs are
  unchanged. Keep it 4–6 lines.

- [ ] **Step 3: Commit** — `docs(kb): document domain-prefixed slug convention for multi-domain KB`.

### Task S3: strict-tier note

- [ ] **Step 1: Add a one-line note** under § Council (`ingest.md:~168`): "In a multi-domain KB,
  `parse_claims.py <slug>` and `synthesize_council.py <slug>` resolve the domain from the
  `<domain>--<slug>` prefix and use that domain's judges / vote-threshold / judge-prompts — so the
  slug MUST be domain-prefixed."

- [ ] **Step 2: Commit** — `docs(kb): note per-domain council resolution under --strict`.

### Task S4: version bump + reinstall

> NOTE: source `plugins/h2t-ops/.claude-plugin/plugin.json` is already `1.5.9`, but the INSTALLED
> cache is `1.5.8` (1.5.9 unreleased). Bump to `1.5.10`.
>
> CORRECTION (verified during execution): the `lichtpfad` marketplace is a **GitHub source**
> (`known_marketplaces.json` → `lichtpfad/h2t-skills`, `autoUpdate: true`). The live SKILL markdown
> is served from the plugin cache pulled from GitHub — **NOT** from `uv tool install` (that only
> rebuilds the Python CLI binaries: h2t-gather/h2t-handoff/h2t-ops). So the live skill reloads
> **automatically after the skill PR is merged to `main`** (autoUpdate). There is no autonomous way
> to reload it before merge; the version bump is what lets autoUpdate detect the new release.

- [ ] **Step 1: Patch-bump** `"version"` `1.5.9 → 1.5.10` in
  `plugins/h2t-ops/.claude-plugin/plugin.json:4`.

- [ ] **Step 2: (optional) `uv tool install --editable C:/dev/h2t-skills`** — refreshes the CLI
  binaries only; does NOT reload the skill markdown. Live skill reload = merge PR → autoUpdate.

- [ ] **Step 3: Commit** — `chore(h2t-ops): bump 1.5.9 -> 1.5.10 (kb multi-domain ingest)`.

### Task S5: self-review + dry-run verification

- [ ] **Step 1: Self-review** — grep `ingest.md` for every `<slug>` occurrence; confirm each is
  covered by the convention section (domain-prefixed in multi, plain in flat). Fix any missed one.

- [ ] **Step 2: Manual dry-run** (against a scaffolded 2-domain KB, or the e2e fixture pattern):
  confirm `pipeline.run honesty … --slug alpha--x --repo <multiKB>` returns rc 0 and resolves the
  alpha domain; confirm a flat KB run with a plain slug still works. Record the result in the PR.

- [ ] **Step 3: PR** — open PR to `h2t-skills` main; reference the engine PR (Part 1) as a
  dependency (the skill's strict tier needs the `parse_claims` fix merged).

---

## Sequencing

Part 1 (engine `parse_claims` fix) should merge first — the skill's strict tier depends on it. Part
2 (skill) can be authored in parallel but its strict-tier path isn't correct until Part 1 is in.
Tier-1 (default) skill path only needs Part 2 (honesty `--slug` + slug convention).
