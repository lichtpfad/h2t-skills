---
title: "h2t-ops Notion Coverage Patch — Implementation Plan (#144)"
status: "draft"
date: "2026-05-20"
milestone: ""
---
# h2t-ops Notion Coverage Patch — Implementation Plan (#144)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three audit-identified Notion connector coverage gaps without touching unrelated code: (1) restore `~/.dor/secrets.env` token resolution parity; (2) render `video` blocks instead of silently dropping them; (3) restore the `find-project-tasks` CLI command.

**Architecture:** Patch debt on the already-migrated `h2t_ops/connectors/notion/` connector. Re-wrap, do not redesign. Reuse existing `core/secrets.py` machinery and existing client methods (`query_database`, `get_database`, `database_items_to_markdown`); add one client `_block_to_markdown` branch and one `commands.py` subcommand. Tests added/updated alongside each fix per the runbook §4 review gate.

**Tech Stack:** Python (`h2t_ops` package), `pytest`, the connector runbook at `plugins/h2t-ops/references/h2t-connector-runbook.md`. No new dependencies.

**Authority documents (do not duplicate):**

- Connector runbook: `plugins/h2t-ops/references/h2t-connector-runbook.md`
- API coverage audit: `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md` (§3 "Notion — partial")
- Roadmap section: `docs/h2t-ops-roadmap.md` → `### skills: [M3] Patch Notion connector coverage gaps`

---

## File map (this plan touches ONLY these files)

| File | Why |
|---|---|
| `h2t_ops/core/secrets.py` | `resolve_notion_token()` must consult `load_secrets()` first (T1) |
| `h2t_ops/connectors/notion/client.py` | add `video` branch to `_block_to_markdown` (T2) |
| `h2t_ops/connectors/notion/commands.py` | add `find-project-tasks` subcommand + dispatch (T3) |
| `tests/core/test_secrets.py` *(new)* | covers T1 regression |
| `tests/connectors/notion/test_client.py` | adds 2 `video` tests (T2) |
| `tests/connectors/notion/test_commands.py` | adds `find-project-tasks` parser + dispatch tests (T3) |

Hard constraints (every task):

- Patch the existing Notion connector only — no new connector architecture, no new package.
- No POS dependency; no writes to `pos.db` / `dor.db` / vault / lake.
- Keep imports lazy at module scope (heavy SDK stays inside methods).
- Stage ONLY the files named in each task's commit step (the repo carries ~26 unrelated dirty files — never `git add -A`).

Runbook gate mapping for #144 (referenced inline by task):

- §3.2 client.py patterns · §3.6 tests · §4 9-item gate (1 parity, 3 auth/secrets, 4 lazy, 5 tests, 6 live smoke, 7 POS, 8 dist-no-POS, 9 writes) · §5 error map · §6 output contract · §7 POS boundary · §8 DoD.

---

### Task 1: `secrets.env` regression — `resolve_notion_token()` calls `load_secrets()` first

Runbook gates touched: **3 auth/secrets** (parity with legacy `lib/clients/notion.py:14` which did `load_dotenv(~/.dor/secrets.env, override=False)` at import). **5 tests** (new core test).

**Files:**

- Modify: `h2t_ops/core/secrets.py` (function `resolve_notion_token`, current body at lines 27–40)
- Create: `tests/core/test_secrets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_secrets.py` with EXACTLY:

```python
"""Tests for h2t_ops.core.secrets — token resolution via ~/.dor/secrets.env."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from h2t_ops.core import secrets as mod
from h2t_ops.core.errors import ConfigError


def test_resolve_notion_token_reads_secrets_env(tmp_path, monkeypatch):
    """Audit #144: when NOTION_API_TOKEN lives in ~/.dor/secrets.env and no
    other source is present, resolve_notion_token() must find it (parity with
    legacy lib/clients/notion.py's import-time load_dotenv).

    NOTE: load_secrets() mutates os.environ directly (not via monkeypatch), so
    we must clean NOTION_API_TOKEN explicitly to avoid leaking it into sibling
    tests.
    """
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=secret_t1_value\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", secrets_file)
    # Route ~/.config/notion/token to a nonexistent path so only secrets.env can satisfy.
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    try:
        assert mod.resolve_notion_token() == "secret_t1_value"
    finally:
        # load_secrets() set this key in os.environ outside monkeypatch's bookkeeping;
        # pop it so the next test starts clean.
        os.environ.pop("NOTION_API_TOKEN", None)


def test_resolve_notion_token_env_var_wins_over_secrets_env(tmp_path, monkeypatch):
    """Explicit env vars must keep precedence — load_secrets is no-override.

    monkeypatch.setenv is tracked by pytest and reverted at teardown, so no
    manual cleanup is needed here.
    """
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=from_file\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", secrets_file)
    monkeypatch.setenv("NOTION_API_TOKEN", "from_env")
    assert mod.resolve_notion_token() == "from_env"


def test_resolve_notion_token_missing_everywhere_raises_configerror(tmp_path, monkeypatch):
    """No env, no secrets.env, no ~/.config/notion/token → typed ConfigError.

    secrets.env does not exist here, so load_secrets() returns early and does
    not mutate os.environ; no extra cleanup needed.
    """
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "no-such-secrets")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    with pytest.raises(ConfigError):
        mod.resolve_notion_token()
```

- [ ] **Step 2: Run test to verify it fails on the first scenario**

```bash
uv run h2t-ops dev pytest tests/core/test_secrets.py -v
```

Expected: `test_resolve_notion_token_reads_secrets_env` **FAILs** with `ConfigError` (because the current implementation never calls `load_secrets()`). The other two tests should already pass.

- [ ] **Step 3: Implement the minimal fix in `h2t_ops/core/secrets.py`**

In `h2t_ops/core/secrets.py`, replace the body of `resolve_notion_token` so it calls `load_secrets()` before consulting `os.getenv`. The full replacement:

```python
def resolve_notion_token() -> str:
    """Env var → ~/.dor/secrets.env → ~/.config/notion/token → ConfigError.

    Parity with legacy lib/clients/notion.py, which did
    `load_dotenv(~/.dor/secrets.env, override=False)` at import. We do it
    on-demand inside token resolution instead (idempotent, no-override merge).
    The file IS read here, but only when a client actually needs the token —
    registry/help still stay lazy because they never instantiate the client.
    """
    load_secrets()  # merges ~/.dor/secrets.env into os.environ; no override
    tok = os.getenv("NOTION_API_TOKEN")
    if tok:
        return tok
    cfg = Path.home() / ".config" / "notion" / "token"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise ConfigError(
        "Notion API token not found.",
        hint="Set NOTION_API_TOKEN in ~/.dor/secrets.env or create ~/.config/notion/token",
    )
```

(`load_secrets()` is already in this same module; no new import.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/core/test_secrets.py -v
```

Expected: all three tests PASS.

- [ ] **Step 5: Run full Notion + core suite to confirm no regression**

```bash
uv run h2t-ops dev pytest tests/core tests/connectors/notion -v
```

Expected: all green (including the existing `test_missing_token_raises_configerror` which uses `monkeypatch.delenv` + `~/.config/notion/token` indirection — it must still pass because `load_secrets()` no-override means the test's monkeypatched-empty env stays empty).

- [ ] **Step 6: Commit**

```bash
git add h2t_ops/core/secrets.py tests/core/test_secrets.py
git commit -m "fix(notion): resolve token from ~/.dor/secrets.env at parity with legacy (#144)"
```

---

### Task 2: render `video` blocks instead of silently dropping them

Runbook gates touched: **1 parity** (legacy `plugins/h2t/skills/notion/scripts/notion_cli.py` rendered `video`; the connector currently returns `""`). **5 tests**.

**Files:**

- Modify: `h2t_ops/connectors/notion/client.py` (`_block_to_markdown`, branch insert after the `image` branch at lines 260–263)
- Modify: `tests/connectors/notion/test_client.py` (add two tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/connectors/notion/test_client.py`:

```python
def test_block_to_markdown_video_external_with_caption(conv):
    """Audit #144: video block must render as a Markdown link, not be dropped."""
    block = {
        "type": "video",
        "video": {
            "external": {"url": "https://example.com/demo.mp4"},
            "caption": [{"plain_text": "Demo clip"}],
        },
    }
    out = conv._block_to_markdown(block)
    assert out == "[Demo clip](https://example.com/demo.mp4)\n\n"


def test_block_to_markdown_video_file_url_default_title(conv):
    """No caption → default title 'video' (English; legacy used Russian — we
    intentionally normalize to the same fallback string the image branch uses)."""
    block = {
        "type": "video",
        "video": {
            "file": {"url": "https://files.notion.so/v.mp4"},
            "caption": [],
        },
    }
    out = conv._block_to_markdown(block)
    assert out == "[video](https://files.notion.so/v.mp4)\n\n"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/connectors/notion/test_client.py -k video -v
```

Expected: both new tests **FAIL** with `assert '' == ...` (current code returns the empty default).

- [ ] **Step 3: Implement the minimal `video` branch in `client.py`**

In `h2t_ops/connectors/notion/client.py`, in `_block_to_markdown`, **immediately after** the existing `image` branch (which ends at the `return ... if url else ""` line near line 263), insert this branch — mirror the `image` shape so `_block_to_markdown` stays uniform:

```python
        elif t == "video":
            vid = block["video"]
            caption = self._rich_text_to_markdown(vid.get("caption", []))
            url = vid.get("file", {}).get("url") or vid.get("external", {}).get("url", "")
            return f"[{caption or 'video'}]({url})\n\n" if url else ""
```

Do NOT modify anything else in the function. The `# noqa: C901` already on the function definition covers the added branch.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/notion/test_client.py -v
```

Expected: all green, including the two new video tests and the pre-existing `test_blocks_to_markdown_roundtrip` (no change to other branches).

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/notion/client.py tests/connectors/notion/test_client.py
git commit -m "fix(notion): render video blocks instead of dropping them (#144)"
```

---

### Task 3: restore `find-project-tasks` CLI command

Runbook gates touched: **1 parity** (legacy had `h2t ingest notion find-project-tasks` in `lib/cli/main.py:291–295` and in `plugins/h2t/skills/notion/scripts/notion_cli.py:787–795`). **5 tests**.

Implementation note: the client already has `query_database`, `get_database`, and `database_items_to_markdown` — this task adds ONLY a `commands.py` subparser + dispatch branch wrapping them.

**Files:**

- Modify: `h2t_ops/connectors/notion/commands.py` (add subparser in `register` and dispatch branch in `run`)
- Modify: `tests/connectors/notion/test_commands.py` (add parser test + dispatch test)

- [ ] **Step 1: Write the failing tests**

Append to `tests/connectors/notion/test_commands.py`:

```python
def test_find_project_tasks_parser_registered():
    """Audit #144: find-project-tasks must exist as a notion subcommand with the
    legacy default database id."""
    import argparse
    from h2t_ops.connectors.notion.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    args = parser.parse_args(["notion", "find-project-tasks", "proj-page-id"])
    assert args.notion_cmd == "find-project-tasks"
    assert args.project_page_id == "proj-page-id"
    assert args.database_id == "beabac7bf4314952a9327759c638d89f"  # legacy default
    assert args.limit is None


def test_find_project_tasks_dispatch_uses_relation_filter(monkeypatch):
    """find-project-tasks must build the Project-relation filter shape
    {'property':'Project','relation':{'contains': <page_id>}} and pass --limit
    through to client.query_database."""
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls: list[tuple] = []

    class _StubClient:
        def query_database(self, db, *, filter_dict=None, limit=None, **_):
            calls.append(("query", db, filter_dict, limit))
            return [{"id": "task-1"}, {"id": "task-2"}]

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _StubClient())

    args = SimpleNamespace(
        notion_cmd="find-project-tasks",
        project_page_id="proj-1",
        database_id="db-1",
        limit=5,
        as_json=True,
        fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "task-1"}, {"id": "task-2"}]
    assert calls == [(
        "query",
        "db-1",
        {"property": "Project", "relation": {"contains": "proj-1"}},
        5,
    )]


def test_find_project_tasks_dispatch_markdown_uses_database_metadata(monkeypatch):
    """Human/md output path must call get_database + database_items_to_markdown
    (mirrors `search` and `get-database` dispatch in the same module)."""
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    class _StubClient:
        def query_database(self, db, *, filter_dict=None, limit=None, **_):
            return [{"id": "task-1"}]
        def get_database(self, db):
            return {"id": db, "title": [{"plain_text": "Tasks"}]}
        def database_items_to_markdown(self, rows, meta):
            return f"# {meta['title'][0]['plain_text']} ({len(rows)} rows)"

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _StubClient())

    args = SimpleNamespace(
        notion_cmd="find-project-tasks",
        project_page_id="proj-1",
        database_id="db-1",
        limit=None,
        as_json=False,
        fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == "# Tasks (1 rows)"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/connectors/notion/test_commands.py -k find_project_tasks -v
```

Expected: all three tests **FAIL** — the parser test fails at `parser.parse_args(...)` with "invalid choice: 'find-project-tasks'"; the two dispatch tests fail at `cmds_mod.run(args)` with `UsageError("unknown notion subcommand: find-project-tasks")`.

- [ ] **Step 3: Add the subparser registration in `commands.py`**

In `h2t_ops/connectors/notion/commands.py`, in the `register` function, **after** the existing `fd = cmds.add_parser("find-databases", ...)` block (currently ending around line 30, just before `c = cmds.add_parser("create", ...)`), insert:

```python
    ft = cmds.add_parser("find-project-tasks",
                         help="List tasks whose Project relation points at <page_id>")
    ft.add_argument("project_page_id")
    ft.add_argument("--database-id", dest="database_id",
                    default="beabac7bf4314952a9327759c638d89f",
                    help="tasks database id (default: legacy workspace tasks db)")
    ft.add_argument("--limit", type=int)
    add_fmt(ft)
```

- [ ] **Step 4: Add the dispatch branch in `run`**

In the same file, in `run(args)`, **after** the `find-databases` branch (currently `if cmd == "find-databases": return client.find_databases_on_page(args.page_id)`), insert:

```python
    if cmd == "find-project-tasks":
        fdict = {"property": "Project", "relation": {"contains": args.project_page_id}}
        rows = client.query_database(args.database_id,
                                     filter_dict=fdict, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
```

Do NOT modify the rest of `run`; the existing `raise UsageError(f"unknown notion subcommand: {cmd}")` at the end stays as the catch-all.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/notion/test_commands.py -v
```

Expected: all green (including the three new `find_project_tasks` tests AND the pre-existing parser/dispatch/help/shim tests).

- [ ] **Step 6: Lazy-registry guard still green**

```bash
uv run h2t-ops dev check lazy-registry
```

Expected: PASS — we did NOT add any module-level heavy imports; the new subparser uses only `argparse`, and the dispatch branch still relies on the already-lazy `NotionClient` import inside `run`.

- [ ] **Step 7: Commit**

```bash
git add h2t_ops/connectors/notion/commands.py tests/connectors/notion/test_commands.py
git commit -m "feat(notion): restore find-project-tasks CLI (#144)"
```

---

### Task 4: full mocked suite + runbook §4 self-review + installed-CLI live smoke

Runbook gates touched: **5 tests** (cumulative), **6 live smoke**, **7 POS** + **8 dist-no-POS** (verify no regression), **9 write side effects** (verify none added).

**Files:** none modified (this task is verification + evidence — no commit unless drift surfaces).

- [ ] **Step 1: Full mocked test sweep**

```bash
uv run h2t-ops dev pytest tests/core tests/connectors -v
```

Expected: 100% green. The Notion test count grows by 8 (3 secrets + 2 video + 3 find-project-tasks); pre-existing tests unchanged.

- [ ] **Step 2: Runbook §4 9-item checklist self-review (record in issue comment)**

Open `plugins/h2t-ops/references/h2t-connector-runbook.md` §4 and the roadmap's verbatim 9-item list. For #144 the relevant gates and their evidence are:

| Gate | Evidence |
|---|---|
| 1 legacy parity | T1 secrets.env, T2 video, T3 find-project-tasks each restore a legacy capability the audit named missing |
| 2 provider API gaps | none addressed (still tracked in roadmap as future Notion follow-ups: global search, comments, users, file upload) |
| 3 auth/secrets | T1 — `load_secrets()` called inside `resolve_notion_token`; legacy parity restored without inlined dotenv |
| 4 lazy imports | unchanged; T3 added no module-level imports; `dev check lazy-registry` green |
| 5 tests | 8 new tests across core + connectors/notion |
| 6 live smoke | Step 3 below |
| 7 POS boundary | unchanged; no new `~/.dor` writes; `secrets.env` is read-only |
| 8 dist-no-POS | unchanged; no new `pos`/`dor.db`/`vault`/`lake` imports |
| 9 write side effects | none added; no new mutating verb |

- [ ] **Step 3: Install local h2t-ops from the patched main and live read-only smoke**

After T1–T3 are committed **locally** (not pushed yet — the installed CLI smoke runs against the local `C:/dev/h2t-skills` source so the patched code is exercised before any outward-facing action), run on the developer's machine (Git Bash / Claude Bash on Windows; the runbook §1 install procedure):

```bash
# uv path on Windows (resolved by the smoke harness from #139):
UV=$(pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly)
"$UV" tool install --reinstall C:/dev/h2t-skills
OPS="$HOME/.local/bin/h2t-ops.exe"
"$OPS" --version
"$OPS" doctor
# fixture: Notion "Art - Projects" read-only page (from the testing plan)
FIXTURE=10adbc1e61d04d13aa6f17210b77e0d3
"$OPS" notion get    $FIXTURE --json | head -c 200
"$OPS" notion blocks $FIXTURE --limit 3 --json | head -c 200
# Patch-specific: invoke find-project-tasks against a known project page.
# Use --json so machine-readable; --limit 1 to keep noise minimal.
# Use the legacy default tasks DB and a project page id you already know exists.
# If no such project page id is available, document and skip this step in the
# evidence comment — do NOT invent one.
PROJECT_PAGE_ID=<your-known-project-page-id>
"$OPS" notion find-project-tasks "$PROJECT_PAGE_ID" --limit 1 --json | head -c 300
```

Pass criteria:

- `--version`, `doctor` exit 0.
- `notion get` / `notion blocks` exit 0; JSON parses; the `--json` output is non-empty.
- `find-project-tasks` exit 0 with valid JSON (an array, possibly empty if the project has no tasks). If you do not have a known project page id, record "skipped — no read-only project fixture available" in the evidence; do NOT use a write-capable id.
- No token leaks: scan the smoke output with the runbook's leak guard (`secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}`) — must return empty.
- Scope guard: `~/.local/bin/h2t.exe` SHA256 unchanged across the reinstall (`5a041e6ca1ba2c74660397056a644df6a44e0cda98d3855c5911471050476c5a`).

- [ ] **Step 4: Prepare evidence for #144 — do NOT auto-post or auto-close**

Assemble the evidence block locally (date, machine, installed binary path, the four exit codes, redacted output shape, token-leak-guard result, scope-guard `~/.local/bin/h2t.exe` SHA256 before/after), in the testing-plan evidence format. **GitHub comment posting and issue closing are outward-facing actions** — they must NOT be performed by the implementer. Surface the prepared evidence to the maintainer and stop; the maintainer reviews and issues an explicit `gh issue comment 144` / `gh issue close 144` only after approval. This honors the session rule that outward-facing GitHub mutations are user-gated.

- [ ] **Step 5: (Optional) No-op commit guard**

If Steps 1–4 surfaced no code drift, this task produces zero commits. If anything needed a follow-up fix, that fix lives in this task with its own focused commit; do not re-open #144 after closing.

---

## Self-Review (run by the plan author after writing — completed)

**1. Spec coverage:**

- "secrets.env regression" → Task 1 (fix + 3 new tests, including the no-override precedence + missing-everywhere ConfigError).
- "video block rendering/data loss" → Task 2 (one branch in `_block_to_markdown`, 2 new tests covering caption + default title paths).
- "missing `find-project-tasks` CLI gap" → Task 3 (restore as a parity command; tests cover parser, JSON dispatch with correct filter shape, and Markdown dispatch via existing `database_items_to_markdown`).
- "Use the runbook procedure/checklist" → every task names the gates it touches; Task 4 §4 closes out the 9-item gate evidence.
- "Patch existing Notion connector only" / "No new connector architecture" / "No POS dependency" / "No direct writes to pos.db/dor.db/vault/lake" / "Keep lazy imports" → hard constraints block at the top + reaffirmed in T1/T2/T3 step-level guidance; T3 step 6 explicitly re-runs `dev check lazy-registry`.
- "Add/adjust targeted tests" → 8 new tests, file paths exact.
- "Include live smoke plan, read-only where possible" → Task 4 step 3 (read-only fixture + safe `--limit 1` for the new command; explicit fallback "skip with reason" if no project fixture).
- "Do not edit code yet; produce plan only" → this is a plan document only; no code changes were made writing it.

**2. Placeholder scan:**

No TBD/TODO. Every code block, test, and command is concrete. The single `<your-known-project-page-id>` token in Task 4 step 3 is a deliberate user-supplied parameter (with explicit "skip if absent" fallback, not a placeholder asking "to be implemented later"). The `<` brackets make it obvious it must be substituted before running.

**3. Type / signature consistency:**

- `resolve_notion_token` keeps `() -> str` and the `ConfigError` raise — only adds `load_secrets()` at top; T1's tests match.
- `_block_to_markdown` signature unchanged; T2's added branch uses the same `block.get(...)` / `_rich_text_to_markdown(...)` shape as the existing `image` branch.
- T3's new subcommand uses the same `_fmt(args)` helper and the same `client.query_database(...)`/`client.database_items_to_markdown(...)` calls that `search` and `get-database` already use; tests match argument names (`filter_dict`, `limit`) exactly.

No issues found.

---

## Constraints recap (every task obeys)

- Touch only the files in the file map above; never `git add -A`; preserve the 26 unrelated dirty files.
- Patch the existing Notion connector; no new architecture, no new package, no new skill.
- No POS dependency added; no `~/.dor` writes; secrets.env read-only.
- Heavy imports stay inside functions; `dev check lazy-registry` must remain green.
- The runbook §4 9-item gate evidence is the merge gate, recorded on #144 before closing.
