# h2t-ops Drive Parity Migration — Implementation Plan (#133)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Drive to the h2t-ops standard at parity with the legacy `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` for six pure-API verbs: `list`, `search`, `folders`, `download`, `export`, `upload`. The composite `sync-meetings` workflow is **not migrated** — its disposition is tracked in **#147**. Provider-feature expansion (create-folder, share/permissions, move/copy/rename, delete, revisions, shared drives) and scope tightening (`drive.file` + `drive.readonly`) are separate follow-ups.

**Architecture:** Re-wrap not rewrite. Drive becomes the first non-Gmail/Calendar consumer of the existing `h2t_ops/core/google_auth.py` substrate — added in #132 — via a minimal `service_name="drive"` branch in `_candidate_paths()` (shared OAuth store only). The connector follows the established three-file shape (`__init__.py` + `client.py` + `commands.py`) and consumes the Google OAuth resolver exactly the way Calendar does. No new shared modules; no `ingest drive` shim (no legacy ingest entrypoint exists).

**Tech Stack:** Python (`h2t_ops` package), `pytest`, the connector runbook at `plugins/h2t-ops/references/h2t-connector-runbook.md`. No new dependencies — `google-api-python-client` is already in `pyproject.toml` (Gmail/Calendar). `html2text` is **not** declared in `pyproject.toml` or `requirements.txt`; the legacy `drive_cli.py` imports it lazily at the `export --format md` path only. #133 preserves that policy: `html2text` is an **optional** runtime dependency consumed lazily; if missing, `export --format md` raises `ConfigError` with an actionable install hint, but every other Drive verb stays functional.

**Authoritative inputs (do not duplicate their content into code):**

| Input | Path |
|---|---|
| Design (this plan's spec) | `docs/superpowers/specs/2026-05-20-h2t-ops-drive-parity-design.md` |
| Connector runbook | `plugins/h2t-ops/references/h2t-connector-runbook.md` |
| API coverage audit (Drive §3, §6.8) | `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md` |
| Calendar parity plan (pattern source) | `docs/superpowers/plans/2026-05-20-h2t-ops-calendar-parity.md` |
| Roadmap section | `docs/h2t-ops-roadmap.md` → `### skills: [TZ-1] Migrate Drive connector` |
| POS operational boundary | `plugins/h2t-ops/references/pos-operational-boundary.md` |
| Testing plan | `docs/h2t-ops-testing-plan.md` |
| Legacy script (re-wrap source) | `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` |
| Legacy skill (delegation target) | `plugins/h2t-ops/skills/drive/SKILL.md` |
| Gmail / Calendar connectors (pattern) | `h2t_ops/connectors/{gmail,calendar}/` |
| Google OAuth substrate (consumed) | `h2t_ops/core/google_auth.py` |
| Follow-up — retire sync-meetings | **#147** |

## File map (this plan touches ONLY these files)

| File | Action | Why / Task |
|---|---|---|
| `h2t_ops/core/google_auth.py` | Modify | add `service_name="drive"` branch in `_candidate_paths()` (T0) |
| `tests/core/test_google_auth.py` | Modify (append) | positive + negative test for the new branch (T0) |
| `h2t_ops/connectors/drive/__init__.py` | **Create** (T1 minimal package marker) + **Modify** (T2 full `CONNECTOR = ConnectorSpec(...)` body) | registry entry — split across T1/T2 so T1 client tests can import without `commands.py` existing |
| `h2t_ops/connectors/drive/client.py` | **Create** | `DriveClient` parity surface (T1) |
| `h2t_ops/connectors/drive/commands.py` | **Create** | CLI adapter (T2) |
| `h2t_ops/cli.py` | Modify | add `"drive"` to `_MIGRATED` (T2). **No `ingest drive` shim.** |
| `tests/connectors/drive/__init__.py` | **Create** | test package marker (T1) |
| `tests/connectors/drive/test_client.py` | **Create** | client + envelope + ambiguous-folder + missing-scopes tests (T1) |
| `tests/connectors/drive/test_commands.py` | **Create** | commands + `--print` allowed-formats + `--folder` required tests (T2) |
| `plugins/h2t-ops/skills/drive/SKILL.md` | Modify | rewrite to delegate to `h2t-ops drive …`; reframe `sync-meetings` as legacy debt pointing to #147 (T3). **Do not remove the subcommand or its DOR constants** — that is #147's DoD. |

**File-state verification (run BEFORE each task; #144-T1 overwrite lesson):**

```bash
# T0: google_auth extension. The module + tests already exist (#132 landed).
test -e h2t_ops/core/google_auth.py    || echo "T0: BLOCKED — google_auth.py missing"
test -e tests/core/test_google_auth.py || echo "T0: BLOCKED — google_auth tests missing"
grep -q 'service_name == "drive"' h2t_ops/core/google_auth.py \
  && echo "T0: drive branch ALREADY PRESENT" || echo "T0: clean Modify"

# T1/T2/T3: drive package and skill — confirmed at plan-writing time (2026-05-20).
test -d h2t_ops/connectors/drive/      && echo "T1/T2: PRE-EXISTING package"      || echo "T1/T2: clean Create"
test -d tests/connectors/drive/        && echo "T1/T2: PRE-EXISTING test pkg"     || echo "T1/T2: clean Create"
test -e plugins/h2t-ops/skills/drive/SKILL.md || echo "T3: BLOCKED — SKILL.md missing"
```

If any line reports `PRE-EXISTING` for a Create target, or `BLOCKED` for a Modify target, STOP and report BLOCKED — APPEND-vs-Create policy must be re-evaluated for that file.

## Hard constraints (every task)

- Patch the existing connector pattern; no new architecture.
- Keep imports lazy: nothing google-related at module scope of `h2t_ops/connectors/drive/`. `dev check lazy-registry` (which already covers `google*` after #132) must remain green after every task.
- No POS dependency added; no `pos`/`dor.db`/`vault`/`lake` imports; no `~/.dor` writes. The legacy `DOR_ROOT`, `VAULT_ROOT`, `MEETINGS_DIR`, `CONVERT_SCRIPT` module-level constants from `drive_cli.py:30-34` are **not** carried into `h2t_ops/connectors/drive/`.
- Token store policy: `service_name="drive"` resolves the shared Google OAuth token store **only** (no Drive-specific fallback path), mirroring Calendar.
- Required scope: `https://www.googleapis.com/auth/drive` — broad, parity with legacy `drive_cli.py:65`. Tightening to `drive.file` + `drive.readonly` is a separate follow-up.
- The bootstrap hint in `ConfigError` stays neutral — reuse the existing `_BOOTSTRAP_HINT` constant in `core/google_auth.py` verbatim; do **not** name a specific bootstrap command/skill.
- `sync-meetings` is **never** referenced from `h2t_ops/connectors/drive/`. The legacy subcommand stays in `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` until #147 closes; this plan does not delete or move it.
- The Drive client embedded in `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py:612-755` is **not** touched here — de-duplication belongs to #134 MeetGeek migration.
- `download` never writes binary content to stdout; the only `--print` path is `export --print` with text formats (`text`, `csv`, `md`). Binary export formats (`docx`, `xlsx`, `pdf`, `pptx`) with `--print` → `UsageError`.
- `upload --folder NAME` is required (no interactive prompt); 0 matches → `NotFoundError`, ≥ 2 matches → `UsageError("ambiguous folder")`. `--folder-id` is **not** part of #133.
- Gmail's and Calendar's public APIs stay byte-identical — Drive only adds a branch to `google_auth.py:_candidate_paths()`; neither service's resolution path changes.
- Stage ONLY the files named in each task's commit step (the repo carries 26 unrelated tracked-modified + 10 untracked files — never `git add -A`).
- Verification snippets are written for Git Bash / Claude Bash on Windows. PowerShell users use `Select-String` / `Test-Path` equivalents — do not skip the checks.

## Per-task verification (run at the END of every task)

```bash
cd C:/dev/h2t-skills
# A. scope gate: only the named task files were touched
git status --porcelain -- h2t_ops/ tests/ plugins/h2t-ops/skills/drive/ | sort
# B. no unrelated connector code touched (cumulative across the plan)
git diff --name-only origin/main..HEAD -- h2t_ops/ tests/ plugins/h2t-ops/skills/drive/ \
  | grep -vE '^(h2t_ops/(core/google_auth\.py|cli\.py|connectors/drive/(__init__|client|commands)\.py)|tests/(core/test_google_auth\.py|connectors/drive/(__init__|test_client|test_commands)\.py)|plugins/h2t-ops/skills/drive/SKILL\.md)$' \
  | head \
  && echo "OUT-OF-SCOPE FILE" || echo "OK: plan-scope only"
# C. lazy-registry remains green
uv run h2t-ops dev check lazy-registry
# D. existing Gmail + Calendar regression stays green
uv run h2t-ops dev pytest tests/connectors/gmail tests/connectors/calendar -q
```

If any of A/B/C/D surfaces a violation, STOP and report BLOCKED.

---

### Task 0: extend `core/google_auth.py` with `service_name="drive"` branch

Runbook gates touched: **3 auth/secrets** (shared substrate accepts new consumer with zero behavioural change for existing services); **5 tests** (positive + negative for the new branch).

**Files:**

- Modify: `h2t_ops/core/google_auth.py` — `_candidate_paths()` only
- Modify: `tests/core/test_google_auth.py` — append two tests

- [ ] **Step 1: Write failing tests (append-only)**

Append to `tests/core/test_google_auth.py` AFTER existing tests, preserving the existing imports and helpers:

```python
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def test_resolve_drive_uses_shared_store_only(tmp_path, monkeypatch):
    """service_name='drive': shared OAuth store only, NO drive-specific fallback."""
    # A bogus drive-specific token at ~/.config/drive/ must be ignored.
    bogus_drive_store = tmp_path / ".config" / "drive" / "token.json"
    _write_token(bogus_drive_store, [DRIVE_SCOPE])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("drive", [DRIVE_SCOPE])
    # Hint stays neutral (same constant Calendar uses).
    assert "Google OAuth bootstrap" in ei.value.hint
    assert "drive_cli" not in (ei.value.hint or "")


def test_resolve_drive_happy_path_via_shared_store(tmp_path, monkeypatch):
    """service_name='drive': token in shared store with drive scope → creds returned."""
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [DRIVE_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("drive", [DRIVE_SCOPE])
    assert creds is not None
```

- [ ] **Step 2: Run helper tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/core/test_google_auth.py -v
```

Expected: the two new tests FAIL with `ConfigError("google_auth: unknown service_name 'drive'")` (current behaviour for unknown services). All other tests in the file stay green.

- [ ] **Step 3: Apply the minimal `_candidate_paths()` edit**

Open `h2t_ops/core/google_auth.py` and locate `_candidate_paths()` (currently at `:90`). Insert the drive branch BEFORE the trailing `raise ConfigError("unknown service_name …")`:

```python
    if service_name == "drive":
        return [shared]
```

No other change to the module. Lazy-import seams, scope validation, refresh / writeback paths, and bootstrap hint stay byte-identical.

- [ ] **Step 4: Verify tests pass**

```bash
uv run h2t-ops dev pytest tests/core/test_google_auth.py -v
```

Expected: all tests in the file pass (existing 6 + 2 new = 8). If any pre-existing test broke, STOP — the edit drifted out of scope.

- [ ] **Step 5: Per-task verification**

Run the A/B/C/D block above. Expected: A shows only `M h2t_ops/core/google_auth.py` and `M tests/core/test_google_auth.py`; B `OK: plan-scope only`; C `OK lazy-registry`; D Gmail+Calendar green.

- [ ] **Step 6: Commit (T0)**

```bash
git add h2t_ops/core/google_auth.py tests/core/test_google_auth.py
git diff --cached --stat
git commit -F - <<'EOF'
feat(google_auth): recognize service_name="drive" (#133)

Add a 3-line branch to _candidate_paths() so the Drive connector (#133)
can consume the shared Google OAuth substrate the same way Gmail and
Calendar do. Drive resolves the shared OAuth token store only — no
Drive-specific fallback path — mirroring Calendar's policy.

Behaviour for existing services (gmail, calendar) is byte-identical;
unknown service_name still raises ConfigError. Two new tests cover the
positive happy path and the negative "no Drive-specific fallback"
guarantee.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

T0 is purely additive and is safe to ship independently if review on T1–T3 stalls.

---

### Task 1: Create Drive package — `__init__.py` + `client.py` + client tests

Runbook gates touched: **1 legacy parity** (six re-wrapped verbs); **2 provider API gaps** (acknowledged in design, out of scope here); **3 auth/secrets** (consumes shared substrate); **4 lazy imports** (no module-level google); **5 tests** (client + envelopes + ambiguous folder + missing scopes + html2text guard).

**Files:**

- Create: `h2t_ops/connectors/drive/__init__.py` (minimal package marker — see Step below for body)
- Create: `h2t_ops/connectors/drive/client.py`
- Create: `tests/connectors/drive/__init__.py` (empty)
- Create: `tests/connectors/drive/test_client.py`

- [ ] **Step 1: Write failing client tests (Create)**

Create `tests/connectors/drive/test_client.py`. The implementer writes the test file as one cohesive module following the Calendar `tests/connectors/calendar/test_client.py` mocking pattern (mocked `service`, monkey-patched `h2t_ops.core.google_auth.resolve_google_credentials` and `build_google_service`, `_install_app_flow` asserts non-reach).

**Required test contract — every test below MUST have a real body with at least one `assert` or `pytest.raises(...)`. Bare `...` (Ellipsis) bodies are forbidden because they parse as a no-op pass and would silently green a test that proves nothing.**

Required tests (one function each):

| Test name | Purpose |
|---|---|
| `test_module_has_no_module_level_google_import` | grep the file's source for `^import google`, `^from google`, `^import googleapiclient`, `^from googleapiclient`; all four must be absent (regression guard for the lazy-import policy). |
| `test_client_init_consumes_shared_substrate` | patch the resolver and `build_google_service` capturing args; `DriveClient()` must call `resolve_google_credentials("drive", [DRIVE_SCOPE])`. |
| `test_list_files_paginates_and_returns_rows` | mock `service.files().list().execute()` to return two pages with `nextPageToken`; assert flattened rows of length sum, each row has `id/name/mimeType/modifiedTime` keys. |
| `test_search_files_applies_mime_filter` | for `mime_filter="docx"` and `"folder"`, assert the `q=` arg passed to `service.files().list` contains the matching `mimeType=` clause. |
| `test_list_folders_returns_folder_rows` | mock `service.files().list` such that returned rows all carry the folder mimeType; assert `q=` includes `mimeType='application/vnd.google-apps.folder'`. |
| `test_download_default_dest_is_cwd_with_original_name` | mock `files.get_media` + `MediaIoBaseDownload` to yield bytes; with `dest=None`, asserts `saved_path == Path.cwd() / <name>`. |
| `test_download_envelope_size_is_optional` | when `files.get(fields="...,size")` returns no `size`, the result dict must NOT include the `size` key (`"size" not in result`). |
| `test_download_never_writes_to_stdout` | use `capsys`; assert `captured.out == ""` and `captured.err == ""` after `download_file`. |
| `test_export_text_format_returns_text` | mock `files.export(mimeType=text/plain)` returning bytes; assert result text equals the decoded body and the result envelope carries `source_mime`/`export_mime`/`format="text"`. |
| `test_export_md_requires_html2text` | `monkeypatch.setitem(sys.modules, "html2text", None)`; `pytest.raises(ConfigError)` on `export_file(..., fmt="md")`. |
| `test_export_print_rejects_binary_formats` | parametrize over `("docx", "xlsx", "pdf", "pptx")`; `pytest.raises(UsageError)` with `to_stdout=True`. |
| `test_upload_requires_folder_name` | `pytest.raises(UsageError)` when `folder` is `None` or empty string. |
| `test_upload_resolves_folder_by_name` | mock `_resolve_folder_id` to return a single match; assert `files.create` is called with `parents=[<folder_id>]`. |
| `test_upload_ambiguous_folder_raises_usageerror` | mock `files.list` to return 2 folders with the same name; `pytest.raises(UsageError)` whose message contains `"ambiguous folder"`. |
| `test_upload_missing_folder_raises_notfounderror` | mock `files.list` to return `[]`; `pytest.raises(NotFoundError)`. |
| `test_http_401_maps_to_autherror` | `googleapiclient.errors.HttpError` (or a duck-typed stand-in) with `resp.status=401` mapped through `_map_http_error` → `AuthError`. |
| `test_http_404_maps_to_notfounderror` | same shape, status 404 → `NotFoundError`. |
| `test_http_500_maps_to_providererror` | status 500 → `ProviderError`. |
| `test_transport_timeout_maps_to_networkerror` | raise a `TimeoutError`/`socket.timeout`-shaped exception inside the mocked call → `NetworkError`. |
| `test_missing_drive_scope_raises_configerror` | drop a token with Gmail+Calendar scopes only into a tmp shared store, `monkeypatch.setattr(Path, "home", lambda: tmp_path)`, then call `DriveClient()`; `pytest.raises(ConfigError)` with the neutral hint substring. |

**Bare-Ellipsis sentinel (run BEFORE Step 2):**

```bash
# Any line whose entire content is `...` inside a test file is a forbidden
# Ellipsis-body. Match both with and without trailing whitespace.
if grep -RnE '^[[:space:]]*\.\.\.[[:space:]]*$' tests/connectors/drive/ ; then
  echo "BLOCKED: bare Ellipsis bodies present in drive tests — replace with real assertions before continuing"
  exit 1
fi
```

If the sentinel fires, STOP and report BLOCKED before running pytest — pytest will give false-green results otherwise.

- [ ] **Step 2: Run client tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/connectors/drive/test_client.py -v
```

Expected: ALL FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.drive.client'` (or `cannot import name 'DriveClient'`).

- [ ] **Step 3: Create minimal package marker**

Create `h2t_ops/connectors/drive/__init__.py`:

```python
"""Drive connector — populated in T2 (registry entry).

T1 ships the package marker + client.py only; T2 wires CONNECTOR and commands.
This split lets T1 client tests import the package without commands.py existing.
"""
```

- [ ] **Step 4: Create `h2t_ops/connectors/drive/client.py`**

Implement `DriveClient` mirroring the Calendar client shape, consuming `h2t_ops.core.google_auth.resolve_google_credentials("drive", DRIVE_SCOPES)` and `build_google_service("drive", "v3", creds)`. Methods:

- `list_files(folder=None, max_results=None)` — re-wrap of `drive_cli.list_files` (paginated; `_resolve_folder_id` reused internally for non-None `folder`).
- `search_files(query, mime_filter=None, max_results=None)` — re-wrap of `drive_cli.search_files`.
- `list_folders(parent=None, max_results=50)` — re-wrap of `drive_cli.list_folders_cmd`.
- `download_file(file_id, dest=None)` — re-wrap of `drive_cli.download_file`; default `dest = Path.cwd() / name`; return `{saved_path, file_id, name, mimeType}` plus `size` ONLY if `meta.get("size")` was present.
- `export_file(file_id, fmt=None, dest=None, to_stdout=False)` — re-wrap of `drive_cli.export_file`; `to_stdout=True` allowed only for `fmt in {"text", "csv", "md"}`; binary `fmt` with `to_stdout=True` → `UsageError`; `md` lazy-imports `html2text` and raises `ConfigError` if absent.
- `upload_file(file_path, folder, no_convert=False)` — re-wrap of `drive_cli.upload_file`; `folder` is required (kw-only or positional, but never default `None`); `_resolve_folder_id` with the rules at the design's "upload" contract (0 → `NotFoundError`, ≥2 → `UsageError`).

`_map_http_error(e, *, op)` mirrors `h2t_ops/connectors/gmail/client.py:137`. Lazy google imports only via `core.google_auth`. Module-level constants limited to:

```python
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
GOOGLE_EXPORT_FORMATS = {...}   # carried verbatim from drive_cli.py
UPLOAD_CONVERT_MAP = {...}      # carried verbatim from drive_cli.py
PRINT_ALLOWED_FORMATS = frozenset({"text", "csv", "md"})
```

No `DOR_ROOT`, `VAULT_ROOT`, `MEETINGS_DIR`, `CONVERT_SCRIPT` — those stay in the legacy script.

- [ ] **Step 5: Run client tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/drive/test_client.py -v
```

Expected: all client tests pass (count depends on the parametrize fan-out, ≈ 18–22 tests).

- [ ] **Step 6: Per-task verification**

Run A/B/C/D. Expected: A shows only the T1 files (`h2t_ops/connectors/drive/__init__.py`, `client.py`, `tests/connectors/drive/__init__.py`, `tests/connectors/drive/test_client.py`); B `OK: plan-scope only`; C `OK lazy-registry`; D Gmail+Calendar green.

- [ ] **Step 7: Commit (T1)**

```bash
git add h2t_ops/connectors/drive/__init__.py h2t_ops/connectors/drive/client.py \
        tests/connectors/drive/__init__.py tests/connectors/drive/test_client.py
git diff --cached --stat
git commit -F - <<'EOF'
feat(drive): DriveClient parity surface + client tests (#133)

Re-wrap the six pure-API verbs from
plugins/h2t-ops/skills/drive/scripts/drive_cli.py — list, search,
folders, download, export, upload — as a typed h2t-ops client backed
by the shared core/google_auth.py substrate.

Behavioural anchors vs legacy:
- download default dest = CWD / original_name; binary bytes never go to
  stdout; envelope is {saved_path, file_id, name, mimeType} plus size
  only when provider metadata reported it (Google editor files do not).
- export --print is text-only: {text, csv, md}; binary formats {docx,
  xlsx, pdf, pptx} with --print raise UsageError.
- export --format md lazy-imports html2text and raises ConfigError if
  absent.
- upload --folder NAME is required (no interactive prompt); 0 matches
  → NotFoundError; ≥ 2 matches → UsageError("ambiguous folder").

sync-meetings is not migrated — its disposition is tracked in #147.
The Drive client embedded in meetgeek_cli.py is not touched here; that
de-duplication is part of #134.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 2: Create `commands.py` + wire `cli.py` + commands tests

Runbook gates touched: **1 legacy parity** (CLI surface mirrors legacy); **3 auth/secrets** (no extra secrets); **4 lazy imports** (parser registration must not import client at module scope); **5 tests** (parser + `--json` envelope shape + help + `--folder` required + `--print` allowed-formats).

**Files:**

- Modify: `h2t_ops/connectors/drive/__init__.py` (replace T1 marker with `CONNECTOR = ConnectorSpec(...)` body)
- Create: `h2t_ops/connectors/drive/commands.py`
- Modify: `h2t_ops/cli.py` — add `"drive"` to `_MIGRATED` (currently `{"notion","gmail","calendar"}` at `:18`)
- Create: `tests/connectors/drive/test_commands.py`

- [ ] **Step 1: Write failing commands tests (Create)**

Create `tests/connectors/drive/test_commands.py` following the Calendar `tests/connectors/calendar/test_commands.py` style (argparse construction via `register(subparsers)`, mocked client via `monkeypatch.setattr("h2t_ops.connectors.drive.commands.DriveClient", FakeClient)`).

**Required test contract — every test below MUST have a real body with at least one `assert` or `pytest.raises(...)`. Bare `...` bodies are forbidden (same rationale as T1 Step 1).**

Required tests:

| Test name | Purpose |
|---|---|
| `test_register_creates_subparsers_for_six_verbs` | call `register(subparsers)`; assert `subparsers.choices` keys equal `{"list", "search", "folders", "download", "export", "upload"}`. |
| `test_each_verb_supports_json_and_format_flags` | for each verb, `parser.parse_args([verb, "--json", ...])` succeeds without `SystemExit` and sets `args.as_json is True`; for non-export verbs, `--format md` and `--format human` succeed and set `args.fmt`; for `export`, provider `--format text|csv|md|docx|xlsx|pdf|pptx` succeeds and sets `args.export_format`; `--format json` is not part of the connector contract because JSON output is selected only via `--json`. |
| `test_help_exits_zero` | `pytest.raises(SystemExit) as ei: parser.parse_args(["drive", "--help"])`; `assert ei.value.code == 0`. Repeat per-verb `--help`. |
| `test_list_returns_envelope_rows` | fake client returns rows; result object passed through the same `emit()` test harness as Calendar uses; assert `body["rows"]` length and `body["count"]`. |
| `test_download_returns_envelope_with_saved_path` | fake client returns `{saved_path, file_id, name, mimeType}`; assert envelope body includes `saved_path` and that `size` is omitted when the fake omitted it. |
| `test_upload_returns_envelope_with_web_view_link` | fake client returns `{file_id, name, mimeType, web_view_link, folder_name}`; assert envelope body includes `web_view_link`. |
| `test_upload_without_folder_raises_usageerror` | `parser.parse_args(["upload", "/tmp/x.md"])` → `SystemExit` (argparse `required=True` enforces it); the `run_upload` handler is never reached. |
| `test_export_print_with_binary_format_raises_usageerror` | parametrize over `("docx", "xlsx", "pdf", "pptx")`; `run_export` with `--print --format <binary>` → `pytest.raises(UsageError)` BEFORE the client call (assert the fake client method was never invoked). |
| `test_export_print_allows_text_formats` | parametrize over `("text", "csv", "md")`; `run_export` with `--print --format <text>` completes without `UsageError`; fake client's `export_file` is invoked with `to_stdout=True`. |
| `test_client_imported_lazily_inside_run` | `src = Path("h2t_ops/connectors/drive/commands.py").read_text()`; assert neither `from h2t_ops.connectors.drive.client` nor `import h2t_ops.connectors.drive.client` appears at the module's top level (allow inside function bodies — i.e. lines that start with whitespace). |

**Bare-Ellipsis sentinel (run BEFORE Step 2):**

```bash
if grep -RnE '^[[:space:]]*\.\.\.[[:space:]]*$' tests/connectors/drive/ ; then
  echo "BLOCKED: bare Ellipsis bodies present in drive tests — replace with real assertions before continuing"
  exit 1
fi
```

If the sentinel fires, STOP and report BLOCKED.

- [ ] **Step 2: Run commands tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/connectors/drive/test_commands.py -v
```

Expected: ALL FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.drive.commands'` (or similar).

- [ ] **Step 3: Replace `__init__.py` marker with the full registry entry**

```python
"""Drive connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="drive",
    help="Work with Google Drive files",
    client="h2t_ops.connectors.drive.client:DriveClient",  # lazy ref (spec §4.1)
    register=register,
)
```

- [ ] **Step 4: Create `h2t_ops/connectors/drive/commands.py`**

Implement six argparse subcommands mirroring the verb contracts in the design. Constraints:

- `register(subparsers)` adds one parser per verb. Default envelope `--json` / `--format` flags are wired through a **local inline helper** defined inside `register`, mirroring Calendar `h2t_ops/connectors/calendar/commands.py:13` and Gmail `h2t_ops/connectors/gmail/commands.py:13`:

  ```python
  def add_fmt(sp):
      sp.add_argument("--json", dest="as_json", action="store_true",
                      help="raw machine-readable envelope")
      sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                      help="md = markdown/detail output, human = concise default")
  ```

  Call `add_fmt(<sub>)` on `list`, `search`, `folders`, `download`, and `upload`.
  Do **not** call `add_fmt(export_sp)`: `export` keeps legacy/provider
  `--format text|csv|md|docx|xlsx|pdf|pptx`, so it would conflict with the
  envelope `--format md|human`. For `export`, add only
  `--json` with `dest="as_json"` plus provider `--format` with
  `dest="export_format"`. There is **no** shared `add_envelope_flags(...)`
  helper in `h2t_ops.core` — both reference connectors define `add_fmt`
  locally; Drive follows the same pattern where the verb has no provider-level
  `--format`.
- Each `run_*` handler imports `DriveClient` **inside** the function (lazy seam), calls the matching client method, and returns a result object. Envelope construction happens in `core/output.py:emit()` — handlers must NOT print or build envelopes.
- `run_upload` argparse: `--folder` is `required=True`.
- `run_export` validation: when `--print` is set, `args.export_format` must be in `PRINT_ALLOWED_FORMATS` (`{"text", "csv", "md"}`); otherwise raise `UsageError` before the client call.

- [ ] **Step 5: Wire `cli.py`**

Open `h2t_ops/cli.py` and update `_MIGRATED` at `:18`:

```python
_MIGRATED = {"notion", "gmail", "calendar", "drive"}
```

No ingest shim. The registry pick-up (via `CONNECTOR` in `__init__.py`) and the `_MIGRATED` whitelist are enough.

- [ ] **Step 6: Run commands tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/drive -v
```

Expected: all client + commands tests pass.

- [ ] **Step 7: Per-task verification**

Run A/B/C/D. Expected: A shows the T2 files only; B `OK: plan-scope only`; C `OK lazy-registry`; D Gmail+Calendar green.

- [ ] **Step 8: Commit (T2)**

```bash
git add h2t_ops/connectors/drive/__init__.py h2t_ops/connectors/drive/commands.py \
        h2t_ops/cli.py tests/connectors/drive/test_commands.py
git diff --cached --stat
git commit -F - <<'EOF'
feat(drive): CLI commands + registry entry (#133)

Wire six argparse subparsers — list / search / folders / download /
export / upload — onto the parity DriveClient from T1, and add "drive"
to cli._MIGRATED so the dispatcher picks it up. No ingest shim: there
is no legacy `h2t ingest drive` entrypoint.

Contract guards:
- `drive upload` requires --folder NAME (raises UsageError otherwise).
- `drive export --print` accepts only text formats {text, csv, md};
  binary formats {docx, xlsx, pdf, pptx} with --print raise UsageError
  before the client call.

DriveClient is imported lazily inside each run_* handler — module-scope
google imports remain forbidden (dev check lazy-registry covers this).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 3: Skill `SKILL.md` rewrite — delegate to `h2t-ops drive …`

Runbook gates touched: **1 legacy parity** (skill UX preserved through delegation); **7 POS boundary** (skill text no longer presents `sync-meetings` as Drive capability for new work).

**Files:**

- Modify: `plugins/h2t-ops/skills/drive/SKILL.md`

- [ ] **Step 1: Replace `## Команды` to delegate to `h2t-ops drive …`**

For each of the six parity verbs, the skill now points at `h2t-ops drive <verb>` instead of `${CLAUDE_SKILL_DIR}/scripts/drive_cli.py <verb>`. Keep argument names and Russian inline examples; only the command prefix changes:

| Verb | New skill command |
|---|---|
| List files | `h2t-ops drive list [folder] [--max N] [--json]` |
| Search | `h2t-ops drive search "query" [--type docx\|folder] [--max N] [--json]` |
| Folders | `h2t-ops drive folders [parent] [--json]` |
| Download | `h2t-ops drive download <file_id> [--dest PATH] [--json]` |
| Export | `h2t-ops drive export <file_id> [--dest PATH] [--format text\|csv\|md\|docx\|xlsx\|pdf\|pptx] [--print] [--json]` |
| Upload | `h2t-ops drive upload <file> --folder "NAME" [--no-convert] [--json]` |

Document the `download` envelope (`{saved_path, file_id, name, mimeType, size?}`) and the `--print` text-only rule for `export`.

- [ ] **Step 2: Reframe `sync-meetings` as legacy debt**

Replace the existing `### Синхронизация транскриптов (главная команда)` section with:

```markdown
### Legacy: синхронизация транскриптов (не для нового кода)

Subcommand `sync-meetings` исторически жил в `drive_cli.py`, пока у MeetGeek
не было нормального публичного API. Он скачивает Google Doc транскрипты из
папки `MeetGeek Files/`, экспортирует в DOCX в `$DOR_ROOT/context/meetings/`
и вызывает DOR-internal конвертер. Это **coordinator/POS workflow, а не Drive
runtime**, и в `h2t-ops drive ...` он не мигрирован.

Disposition этой команды отслеживается в **#147** (`Retire Drive
sync-meetings legacy workflow`). Для нового кода используй:

- `h2t-ops drive list "MeetGeek Files"` + `h2t-ops drive export <doc_id> --print` для отдельных транскриптов, или
- `h2t-ops meetgeek …` когда #134 закроет MeetGeek connector.

Не вызывай `h2t-ops drive sync-meetings` — такого верба больше нет.
```

Keep the legacy DOR_ROOT / VAULT_ROOT env-var documentation **only inside this section**, with a note that they exist for the legacy subcommand and have no effect on `h2t-ops drive …` verbs.

- [ ] **Step 3: Update SKILL.md frontmatter**

- `compatibility:` — replace `~/.config/google-calendar-mcp/tokens.json` reference with `"Requires Google OAuth token with Drive scope. Bootstrap via the same flow as Gmail/Calendar."`
- Drop the `DOR_ROOT env var for meeting sync.` clause — it is no longer a Drive skill requirement; the legacy section covers it inline.
- Bump skill `metadata.version` from `1.0.0` to `1.1.0` (delegate-to-CLI is a contract change at the skill level).

- [ ] **Step 4: Lint the skill (no live calls)**

```bash
uv run h2t-dev docs-lint plugins/h2t-ops/skills/drive/SKILL.md || \
  echo "(docs-lint output for review; no fail expected — formatting only)"
```

- [ ] **Step 5: Per-task verification**

Run A/B/C/D. Expected: A shows only `M plugins/h2t-ops/skills/drive/SKILL.md`; B `OK: plan-scope only`; C `OK lazy-registry`; D Gmail+Calendar green.

- [ ] **Step 6: Commit (T3)**

```bash
git add plugins/h2t-ops/skills/drive/SKILL.md
git diff --cached --stat
git commit -F - <<'EOF'
docs(drive): skill delegates to h2t-ops drive ... (#133)

Rewrite plugins/h2t-ops/skills/drive/SKILL.md so the six parity verbs
(list / search / folders / download / export / upload) delegate to the
new h2t-ops drive ... CLI from T1/T2, instead of invoking the local
drive_cli.py script.

sync-meetings is reframed as legacy debt with a pointer to #147; the
actual subcommand and its DOR_ROOT/VAULT_ROOT/MEETINGS_DIR/CONVERT_SCRIPT
module-level constants in drive_cli.py are NOT removed here — that is
#147's DoD.

Skill metadata bumped 1.0.0 → 1.1.0 (delegation is a contract change at
the skill level).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 4: Closure — full pytest sweep + runbook §4 9-gate self-review + live smoke + LOCAL evidence (STOP)

Runbook gates touched: **5 tests** (cumulative); **6 live smoke**; **7 POS** + **8 dist-no-POS** + **9 write side effects** (verify none regressed).

**Files:** none modified (verification + evidence). Zero new commits unless drift surfaces.

- [ ] **Step 1: Full mocked test sweep**

```bash
uv run h2t-ops dev pytest tests/core tests/connectors -v
```

Record: total count, pass/fail. Expected: previous baseline (post-#132 — exact number captured in #132's own evidence block) + 2 (T0 google_auth drive branch) + ≈ 18–22 (T1 client) + ≈ 12–16 (T2 commands). Exact count varies by parametrize fan-out.

- [ ] **Step 2: `dev check lazy-registry`**

```bash
uv run h2t-ops dev check lazy-registry
```

Expected: `OK lazy-registry` (google* coverage already present from #132).

- [ ] **Step 3: Runbook §4 9-item gate self-review (no file write — assemble for report)**

| Gate | #133 Evidence |
|---|---|
| 1 legacy parity | T1 DriveClient: list / search / folders / download / export / upload re-wrap |
| 2 provider API gaps | NOT addressed (create-folder, share/permissions, move/copy, delete, revisions, shared drives) — separate follow-up; acknowledged in design "Non-goals" |
| 3 auth/secrets | T0 added `service_name="drive"` branch to `core/google_auth.py`; broad `drive` scope (parity); shared OAuth store only; neutral bootstrap hint reused |
| 4 lazy imports | No module-level google in `connectors/drive/*`; `dev check lazy-registry` OK after every task |
| 5 tests | T0 +2 helper + T1 ≈ 18–22 client + T2 ≈ 12–16 commands net-new |
| 6 live smoke | Step 4 below |
| 7 POS boundary | No `~/.dor` writes from any new code; DOR_ROOT/VAULT_ROOT/MEETINGS_DIR/CONVERT_SCRIPT not carried into `h2t_ops/connectors/drive/`; `sync-meetings` migration tracked in #147 |
| 8 dist-without-POS | No `pos`/`dor.db`/`vault`/`lake` imports in any new file |
| 9 write side effects | `drive upload` is the only write verb; explicit `--folder NAME` required; ambiguous-folder safeguard; covered by tests; not auto-triggered |

- [ ] **Step 4: Install local h2t-ops from local `C:/dev/h2t-skills` and run read-only live smoke**

```bash
UV=$(pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly)
"$UV" tool install --reinstall "$(pwd)"
OPS="$HOME/.local/bin/h2t-ops.exe"

# scope-guard hash before reinstall
sha256sum "$HOME/.local/bin/h2t.exe" 2>/dev/null

"$OPS" --version
"$OPS" doctor
"$OPS" connectors                       # must include drive
"$OPS" drive --help                     # exit 0; lists 6 verbs
"$OPS" drive list --json    | head -c 400
"$OPS" drive folders --json | head -c 400

# Pick a known Google Doc file id from the user's Drive; the operator
# substitutes <KNOWN_DOC_ID>. Skip if no safe id is available — record
# the skip in the evidence block, do NOT fabricate a value.
"$OPS" drive export <KNOWN_DOC_ID> --print --format text | head -c 400

# scope-guard hash after
sha256sum "$HOME/.local/bin/h2t.exe" 2>/dev/null
```

Pass criteria:

- `--version`, `doctor`, `connectors`, `drive --help` exit 0; `connectors` lists `drive`.
- `drive list --json` and `drive folders --json`: **exit 0 with valid JSON** if the current shared OAuth token has the Drive scope, OR **exit 3 (ConfigError) with the neutral bootstrap hint** if it does not.
- The exit-3 path is NOT a code failure; it is the upfront scope-validation behaviour. Classify it in evidence as "blocked on bootstrap/scope, not on code".
- `drive export … --print --format text` either succeeds with text output, or is skipped with a recorded reason (no safe doc id available, or scope missing).
- Token-leak scan over the live stdout: `secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9._\-]{20,}` → must be empty.
- Scope guard: `~/.local/bin/h2t.exe` SHA256 unchanged before/after reinstall.
- Live `drive upload` is **not** part of automatic smoke — it is a provider write and runs only if the user explicitly requests it with a test-safe folder name.

- [ ] **Step 5: Prepare the LOCAL evidence block — DO NOT POST OR CLOSE**

Format ready-to-paste on #133 (template below). Replace `<token>` placeholders with actual values. Do **not** post any GitHub comment, do **not** close #133 — outward-facing actions are user-gated.

```md
## #133 Drive parity — local evidence (not yet posted)

Date: 2026-05-20
Machine: AUTOMATA
Source: local `C:/dev/h2t-skills` (commits <T0>, <T1>, <T2>, <T3>; not pushed)
Installed binary: `C:\Users\stani\.local\bin\h2t-ops.exe`

### Mocked tests
- `tests/core tests/connectors`: <count> passed, 0 failed (+<N> vs pre-#133).
- `uv run h2t-ops dev check lazy-registry`: OK lazy-registry.

### Live read-only smoke
- `h2t-ops --version`: exit 0
- `h2t-ops doctor`: exit 0
- `h2t-ops connectors`: exit 0, lists notion / gmail / calendar / drive
- `h2t-ops drive --help`: exit 0, six verbs listed
- `h2t-ops drive list --json`: exit <0 | 3>, <JSON ok | ConfigError with neutral hint>
- `h2t-ops drive folders --json`: exit <0 | 3>, <JSON ok | ConfigError with neutral hint>
- `h2t-ops drive export <id> --print --format text`: <exit 0 with text | skipped: <reason>>

### Guards
- Token leak scan: <empty / hits>
- Scope guard h2t.exe SHA256: <before> → <after> (<HELD / VIOLATED>)
- File scope: `git log <T0>^..<T3> --name-only` — all changes inside the plan's file map.

### Runbook §4 9-item gate
(table from Step 3)

### Follow-ups deferred (not part of #133)
- #147 — Retire Drive `sync-meetings` legacy workflow.
- Drive provider features (create-folder, share/permissions, move/copy,
  delete, revisions, shared drives) — to file as separate follow-up.
- Drive scope tightening (`drive.file` + `drive.readonly`) — to file as
  separate follow-up.
- De-duplicate Drive client embedded in
  `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py:612-755` —
  part of #134 MeetGeek migration.
```

- [ ] **Step 6: Final report (no commit unless drift surfaced)**

Surface in the implementer's reply: T0/T1/T2/T3 SHAs, the mocked-test count, the lazy-registry result, the live smoke command-by-command exit codes, token-leak and scope-guard verdicts, the assembled evidence block, and explicit:

> "Did NOT push. Did NOT post any GitHub comment. Did NOT close #133. STOPPING for maintainer approval."

If Steps 1–4 surfaced a drift requiring a fix, the fix lives in this task with its own focused commit (file scope: limited to the file that drifted); do not silently expand scope.

---

## Constraints recap (every task obeys)

- Re-wrap not rewrite; copy the Notion/Gmail/Calendar three-file shape verbatim.
- No module-level google imports anywhere; `dev check lazy-registry` green after every task.
- No POS imports, no `~/.dor` writes, no DOR-coupled constants in the new connector.
- Drive scope is broad (`https://www.googleapis.com/auth/drive`) for parity — tightening is a separate follow-up.
- `download` never emits binary to stdout; envelope size is optional.
- `export --print` is text-only `{text, csv, md}`; binary `{docx, xlsx, pdf, pptx}` with `--print` → `UsageError`.
- `upload --folder NAME` is required; 0 → `NotFoundError`, ≥ 2 → `UsageError("ambiguous folder")`.
- `sync-meetings` not migrated — disposition in **#147**.
- Stage only the named files per task; never `git add -A`.
- Outward-facing actions (push, GitHub comment, close issue) are user-gated.
