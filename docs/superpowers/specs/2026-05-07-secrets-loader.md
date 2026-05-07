---
title: "Minimal h2t_secrets Loader — Single Source of Truth at ~/.dor/secrets/"
status: "draft"
owner: "lichtpfad"
date: "2026-05-07"
milestone: "Secrets unification (umbrella #107)"
related_issue: "lichtpfad/h2t-skills#108"
parent_issue: "lichtpfad/h2t-skills#107"
supersedes: null
---

# Minimal h2t_secrets Loader — Single Source of Truth at ~/.dor/secrets/

**Goal:** Ввести общий Python-loader `h2t_secrets` в `plugins/h2t-core/scripts/`, который читает `~/.dor/secrets/secrets.env` в `os.environ` (без перезаписи shell-export), и мигрировать только `h2t-ops:research` как proof + fix реального drift-бага. Все остальные skills остаются на `os.environ.get` напрямую и работают как раньше через shell-export.

**Scope (PR #1):** Только `h2t-ops:research`. Loader живёт в `h2t-core` плагине. Никаких других skill migrations в этом PR.

**Non-goals:**
- Per-skill migrations beyond research (см. отдельные issues #109, #110, #111).
- `h2t-core:setup --secrets` interactive wizard (issue #112).
- OAuth JSON path moves (deferred).
- OS keyring / 1Password backend.
- Encrypted-at-rest.
- Multi-key routing (issue #71).

---

## 1. Context & Root Cause

См. umbrella issue #107 для полной картины. Кратко:

- Секреты живут в трёх местах (`~/.dor/secrets.env`, `~/.h2t/config/secrets/`, shell env), нет единого loader'а.
- Реальный drift-баг: `EXA_API_KEY` был в shell env на AUTOMATA, отсутствовал в `~/.dor/secrets.env`. Сессия из `C:\Users\stani` без активного shell-export получила `EXA_ERROR:ENV` на preflight, агент задиспатчил deprecated `h2t:research-agent`, silent fallback на WebSearch.
- Фикс на уровне skill'а недостаточен — нужен общий contract: где хранятся ключи, кто их грузит, как откатывать на shell env при экспериментах.

---

## 2. Design

### 2.1 Canonical layout

```
~/.dor/secrets/
  README.md          # rotation runbook (per-key: source, validator, test command)
  secrets.env        # all KEY=VALUE — Exa/Gemini/MeetGeek/...
```

**Никаких изменений** в `~/.h2t/config/secrets/` в этом PR — оставляем существующие OAuth JSONs там. Добавляем `~/.h2t/config/secrets/README.md` со ссылкой на новый layout как deprecation hint.

### 2.2 Loader API (`plugins/h2t-core/scripts/h2t_secrets.py`)

Stdlib only — никаких pip deps:

```python
from pathlib import Path
from typing import Final

DEFAULT_SECRETS_FILE: Final[Path] = Path.home() / ".dor" / "secrets" / "secrets.env"
SECRETS_DIR: Final[Path] = Path.home() / ".dor" / "secrets"


def bootstrap(*, env_file: Path | None = None) -> dict[str, str]:
    """Read secrets.env and merge missing keys into os.environ.

    - Idempotent (safe to call multiple times).
    - Does NOT override existing os.environ keys (shell-export wins).
    - Fail-loud if env_file missing (FileNotFoundError with actionable message).
    - Skips comment lines (#...) and blank lines.
    - Raises ValueError on malformed lines.
    - Returns dict of keys that were newly set (for telemetry/debug).

    env_file defaults to ~/.dor/secrets/secrets.env, overridable via
    H2T_SECRETS_FILE env var (testability).
    """


def get_blob(relative_path: str) -> Path:
    """Return absolute Path to a credential blob under ~/.dor/secrets/.

    Example: get_blob("google/gmail-oauth.json") → ~/.dor/secrets/google/gmail-oauth.json
    Fail-loud (FileNotFoundError) if the file does not exist.
    """
```

### 2.3 Behaviour Decisions

| Concern | Decision | Reason |
|---|---|---|
| Missing `secrets.env` | `FileNotFoundError` with message pointing at fix steps | Silent skip masked the original bug. Fail-loud surfaces config drift. |
| Existing `os.environ` value | Preserved; loader does NOT overwrite | Shell-export-wins pattern. Allows ad-hoc experimentation without editing the file. |
| Order of resolution | shell env > `secrets.env` > unset | Predictable, debuggable. |
| Comments / blank lines | Skipped silently | Standard `.env` semantics. |
| Quoted values | Strip leading/trailing single or double quotes around the value | `KEY="value"` and `KEY='value'` both work. |
| Multiline values | Not supported | Real secrets are single-line; supporting multiline tempts edge cases. Fail with ValueError. |
| Override file via env | `H2T_SECRETS_FILE` env var → bootstrap reads that path instead of default | Tests use this; multi-account future. |
| Returns | dict[str, str] of newly-set keys (not values logged anywhere) | Caller can verify which keys actually arrived from file. |

### 2.4 Migration of `h2t-ops:research`

In `plugins/h2t-ops/skills/research/scripts/exa_search.py`:

1. Add at the top of `main()` (before `_build_parser`):
   ```python
   try:
       from h2t_secrets import bootstrap
       bootstrap()
   except FileNotFoundError as e:
       # Fail-loud: surfaces the drift bug instead of silently falling through to
       # missing-EXA_API_KEY at preflight time.
       print(f"EXA_ERROR:ENV {e}", file=sys.stderr)
       sys.exit(4)
   ```

2. The rest of the script stays unchanged. `os.environ.get("EXA_API_KEY")` calls work because `bootstrap()` populated the env.

3. Path resolution: `h2t_secrets.py` lives in `plugins/h2t-core/scripts/`. The research skill must import it. Two options:
   - **(a) `sys.path.insert`** in `exa_search.py`'s `main()` to point at `plugins/h2t-core/scripts/`. Brittle if file is moved.
   - **(b) Editable install / `PYTHONPATH`** maintained by `h2t-core:setup`. Cleaner but requires setup discipline.
   - **(c) Symlink-style: copy `h2t_secrets.py` into research skill's scripts dir.** Worst — duplication.
   - **(d) `importlib.util.spec_from_file_location`** with a relative path computed from `__file__`. Verbose but bulletproof.

   **Decision: (d).** Compute path: `Path(__file__).resolve().parents[3] / "h2t-core" / "scripts" / "h2t_secrets.py"`. Wrap in helper function `_load_h2t_secrets()` so other skills reuse the same pattern in future migrations.

### 2.5 Distribution Safety

The actual `~/.dor/secrets/` directory is **never** in the repo:

- Add `.dor/` to `.gitignore` (defensive — outside repo by default, but if user accidentally creates `~/.dor/` symlink in repo it won't commit).
- `secrets.env` example/template: `~/.dor/secrets/README.md` shows the format with placeholder values, not real keys.
- Any in-repo example must use obviously-fake keys (e.g., `EXA_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

---

## 3. `secrets.env` Format

Standard dotenv:

```env
# Exa search (https://dashboard.exa.ai/api-keys)
EXA_API_KEY=<uuid>
EXA_API_KEY_BACKUP=<uuid>

# Google Gemini (https://aistudio.google.com/apikey)
GEMINI_API_KEY=<key>

# MeetGeek (https://meetgeek.ai/settings/api)
MEETGEEK_API_KEY=<key>
MEETGEEK_BASE_URL=https://api.meetgeek.ai
MEETGEEK_TIMEOUT=30
MEETGEEK_MAX_PAGES=1000
MEETGEEK_WEBHOOK_SECRET=<secret>
```

User maintains this file manually for now. Wizard from issue #112 will automate later.

---

## 4. Tests

File: `plugins/h2t-core/scripts/tests/test_h2t_secrets.py` (new).

| Test | Scenario | Expected |
|---|---|---|
| `test_bootstrap_loads_keys_into_environ` | tmp file with 2 keys | both keys in `os.environ`, returned dict has 2 entries |
| `test_bootstrap_does_not_override_existing_environ` | shell pre-set `KEY=existing`, file has `KEY=fromfile` | `os.environ["KEY"] == "existing"`, returned dict empty for that key |
| `test_bootstrap_fail_loud_on_missing_file` | non-existent path | `FileNotFoundError` with actionable message ("create ~/.dor/secrets/secrets.env...") |
| `test_bootstrap_skips_comments_and_blanks` | file with `# comment`, blank line, then `K=V` | only `K=V` parsed |
| `test_bootstrap_handles_quoted_values` | `K1="v1"`, `K2='v2'` | both strip quotes |
| `test_bootstrap_raises_on_malformed_line` | line `not_a_kv_pair` | `ValueError` mentioning line number |
| `test_bootstrap_idempotent` | call twice | second call returns empty dict (nothing new) |
| `test_bootstrap_via_env_file_override` | `H2T_SECRETS_FILE=/tmp/foo.env` | reads from /tmp/foo.env |
| `test_get_blob_returns_existing_path` | tmp blob exists | returns absolute Path |
| `test_get_blob_fail_loud_on_missing` | path absent | `FileNotFoundError` |

Plus: integration test in research skill — patch `h2t_secrets.bootstrap` to no-op, verify `_run_search` unchanged behaviour.

---

## 5. Migration Steps (manual, by user, NOT automated by this PR)

1. Create `~/.dor/secrets/` directory.
2. Write `~/.dor/secrets/secrets.env` with all current keys:
   - From shell env: `EXA_API_KEY` (and any others currently shell-exported but NOT in old `secrets.env`).
   - From `~/.h2t/config/secrets/exa-keys.md`: `EXA_API_KEY_BACKUP` (the secondary key registry).
   - From old `~/.dor/secrets.env`: `GEMINI_API_KEY` (preserve).
   - From wherever MeetGeek key currently lives.
3. Write `~/.dor/secrets/README.md` per template (shipped in this PR's docs).
4. Verify: `python plugins/h2t-ops/skills/research/scripts/exa_search.py preflight` returns `OK` from a fresh shell with NO `EXA_API_KEY` exported.

The PR ships the loader, the migration template, the rotation runbook template, and the research skill change. It does NOT touch the user's actual `~/.dor/`.

---

## 6. File Structure

| Path | Change |
|---|---|
| `plugins/h2t-core/scripts/h2t_secrets.py` | **NEW** — loader module (~70 LOC). |
| `plugins/h2t-core/scripts/tests/test_h2t_secrets.py` | **NEW** — pytest suite (~150 LOC). |
| `plugins/h2t-core/scripts/tests/__init__.py` | **NEW** if not present. |
| `plugins/h2t-ops/skills/research/scripts/exa_search.py` | Add `_load_h2t_secrets()` helper + `bootstrap()` call in `main()`. |
| `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | One new test: bootstrap is invoked at startup; existing 88 tests unchanged. |
| `docs/superpowers/specs/2026-05-07-secrets-loader.md` | this file |
| `docs/superpowers/plans/2026-05-07-secrets-loader.md` | follow-up |
| `~/.h2t/config/secrets/README.md` | **NEW** — small redirect note (not in repo if `.h2t/` is outside; otherwise check). |
| User-level `~/.claude/CLAUDE.md` | Manual edit (instructions in plan). Update `Config:` line. |
| Memory note `feedback_h2t_secrets_runtime` | Updated in plan. |

Plugin manifests: no version bump for `h2t-ops` (research skill behaviour unchanged from caller's POV — bootstrap is invisible). `h2t-core` gets a version bump (new public API). Decision in plan.

---

## 7. Acceptance (from issue #108)

- [x] `h2t_secrets.py` exists with `bootstrap()` + `get_blob()` — §2.2
- [x] Tests cover success / missing file / shell-env precedence / comment+blank / malformed line — §4
- [x] Research skill calls `bootstrap()` in `main()` — §2.4
- [x] Existing 88 research tests still pass — §4 last paragraph
- [x] No real key values in repo — §2.5
- [x] `~/.dor/secrets/README.md` rotation runbook — §5

---

## 8. Open Questions (for plan stage)

1. **Plugin version bump.** `h2t-core` is currently version-X. New public API (`h2t_secrets`) is a minor bump candidate. But per user CLAUDE.md `minor only after live verification`, ship as patch first, minor after live use confirms loader works. Decide in plan.

2. **`importlib`-based cross-plugin load.** §2.4(d) computes path via `parents[3]`. If plugins move (e.g., monorepo restructure), this breaks. Add explicit fallback chain: relative path → `H2T_PLUGIN_ROOT` env → fail-loud. Decide concrete fallback list in plan.

3. **Pre-existing `~/.dor/secrets.env` migration.** Currently has only `GEMINI_API_KEY`. Should the new layout be `~/.dor/secrets/secrets.env` (subdir), keeping the old `~/.dor/secrets.env` as a deprecation symlink? Or hard-cut to new location? Recommend: hard-cut, document in plan as user step 1. The old `~/.dor/secrets.env` file will be deleted by the user during migration.

4. **`get_blob()` usage in this PR.** None of the 4 follow-up issues (#109–#112) need `get_blob()` immediately — they all use env-vars, not blobs. Should we ship `get_blob()` now or defer to first user (likely future Google OAuth path migration)? Recommend: ship now with one passing unit test. ~10 LOC, no maintenance burden.

---

## 9. References

- Umbrella issue: https://github.com/lichtpfad/h2t-skills/issues/107
- This issue: https://github.com/lichtpfad/h2t-skills/issues/108
- Original drift incident: PR #106 closeout discussion
- Memory note: `feedback_h2t_secrets_runtime` (to be updated)
- Spec for envelope: `docs/superpowers/specs/2026-05-07-research-provider-envelope.md` (sibling pattern)
