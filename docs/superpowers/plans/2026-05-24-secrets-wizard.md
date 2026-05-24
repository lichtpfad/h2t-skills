# Secrets Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5-step guided wizard to `h2t-core:setup` that creates `~/.dor/secrets/secrets.env`, walks a new user through obtaining API keys, triggers Google OAuth, and guides Telegram auth.

**Architecture:** Hybrid — `setup_h2t.py` gets two new subcommands (`secrets skeleton`, `secrets preflight`) backed by a `known_secrets.yaml` registry; SKILL.md gets an explicit numbered wizard section. The backend is stateless and tested in isolation; the skill owns sequencing and UX.

**Tech Stack:** Python 3.11+ stdlib only (no PyYAML — custom minimal parser), pytest, argparse

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `plugins/h2t-core/skills/setup/known_secrets.yaml` | Create | Registry of API-key credentials (not Google/Telegram) |
| `plugins/h2t-core/skills/setup/scripts/setup_h2t.py` | Modify | Add YAML loader, `secrets skeleton`, `secrets preflight`, parser entries, dispatch |
| `plugins/h2t-core/skills/setup/SKILL.md` | Modify | Add `## Secrets Wizard` section with 5-step flow |
| `tests/test_setup_secrets.py` | Create | Unit tests for skeleton and preflight (no real credentials) |

---

## Task 1: Create `known_secrets.yaml` registry

**Files:**
- Create: `plugins/h2t-core/skills/setup/known_secrets.yaml`

- [ ] **Step 1: Create the registry file**

```yaml
EXA_API_KEY:
  description: "Exa semantic search API key"
  url: "https://dashboard.exa.ai/api-keys"
  validator: uuid
  connector: research

NOTION_API_TOKEN:
  description: "Notion integration token"
  url: "https://www.notion.so/profile/integrations"
  validator: "starts_with:secret_"
  connector: notion

MEETGEEK_API_KEY:
  description: "MeetGeek API key"
  url: "https://app.meetgeek.ai/settings/api"
  validator: nonempty
  connector: meetgeek
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-core/skills/setup/known_secrets.yaml
git commit -m "feat(setup): add known_secrets.yaml registry for secrets wizard"
```

---

## Task 2: Add YAML loader and `secrets skeleton` to `setup_h2t.py`

**Files:**
- Modify: `plugins/h2t-core/skills/setup/scripts/setup_h2t.py`
- Create: `tests/test_setup_secrets.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_setup_secrets.py`:

```python
"""Tests for secrets skeleton and preflight in setup_h2t.py."""
import json
import sys
from pathlib import Path

import pytest

# setup_h2t.py is standalone — add its directory to sys.path
SCRIPTS_DIR = Path(__file__).parent.parent / "plugins" / "h2t-core" / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import setup_h2t  # noqa: E402


REGISTRY = {
    "EXA_API_KEY": {
        "description": "Exa key",
        "url": "https://dashboard.exa.ai/api-keys",
        "validator": "uuid",
        "connector": "research",
    },
    "NOTION_API_TOKEN": {
        "description": "Notion token",
        "url": "https://www.notion.so/profile/integrations",
        "validator": "starts_with:secret_",
        "connector": "notion",
    },
    "MEETGEEK_API_KEY": {
        "description": "MeetGeek key",
        "url": "https://app.meetgeek.ai/settings/api",
        "validator": "nonempty",
        "connector": "meetgeek",
    },
}


# --- secrets_skeleton tests ---

def test_skeleton_creates_file_when_absent(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert result["kind"] == "h2t_secrets_skeleton/v1"
    assert set(result["added"]) == {"EXA_API_KEY", "NOTION_API_TOKEN", "MEETGEEK_API_KEY"}
    assert result["skipped"] == []
    assert secrets_file.is_file()
    content = secrets_file.read_text()
    assert "EXA_API_KEY=" in content
    assert "NOTION_API_TOKEN=" in content
    assert "MEETGEEK_API_KEY=" in content


def test_skeleton_values_are_empty(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    for line in secrets_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            assert line.split("=", 1)[1] == "", f"Value should be empty: {line}"


def test_skeleton_skips_existing_keys(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("EXA_API_KEY=some-existing-value\n")
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert "EXA_API_KEY" in result["skipped"]
    assert "NOTION_API_TOKEN" in result["added"]
    assert "MEETGEEK_API_KEY" in result["added"]
    # Existing value must be preserved
    assert "EXA_API_KEY=some-existing-value" in secrets_file.read_text()


def test_skeleton_creates_parent_dir(tmp_path):
    secrets_file = tmp_path / "new_dir" / "secrets.env"
    setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert secrets_file.is_file()


def test_skeleton_result_path_is_str(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert isinstance(result["path"], str)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_setup_secrets.py -v 2>&1 | head -30
```

Expected: `AttributeError: module 'setup_h2t' has no attribute 'secrets_skeleton'`

- [ ] **Step 3: Add `_load_known_secrets` and `secrets_skeleton` to `setup_h2t.py`**

Add the constant after the existing KIND constants (around line 22):

```python
KIND_SECRETS_SKELETON = "h2t_secrets_skeleton/v1"
KIND_SECRETS_PREFLIGHT = "h2t_secrets_preflight/v1"
```

Add these two functions before `build_parser()`:

```python
def _load_known_secrets(registry_path: Path) -> dict[str, dict[str, str]]:
    """Parse known_secrets.yaml without PyYAML — handles only this file's flat structure."""
    if not registry_path.is_file():
        raise FileNotFoundError(f"known_secrets.yaml not found: {registry_path}")
    result: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in registry_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            current = line.rstrip(":").strip()
            result[current] = {}
        elif current and ":" in line:
            k, _, v = line.strip().partition(":")
            result[current][k.strip()] = v.strip().strip('"').strip("'")
    return result


def secrets_skeleton(secrets_file: Path, registry: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Create or extend secrets.env with placeholder KEY= lines for missing keys.

    Uses atomic write (temp file + rename) so a crash leaves no partial state.
    """
    import tempfile
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    existing_content = ""
    existing_keys: set[str] = set()
    if secrets_file.is_file():
        existing_content = secrets_file.read_text(encoding="utf-8")
        for raw in existing_content.splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                existing_keys.add(line.split("=", 1)[0].strip())
    added: list[str] = []
    skipped: list[str] = []
    new_lines: list[str] = []
    for key, meta in registry.items():
        if key in existing_keys:
            skipped.append(key)
        else:
            desc = meta.get("description", "")
            url = meta.get("url", "")
            new_lines.append(f"# {desc}")
            if url:
                new_lines.append(f"# Get at: {url}")
            new_lines.append(f"{key}=")
            new_lines.append("")
            added.append(key)
    if new_lines:
        separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
        full_content = existing_content + separator + "\n".join(new_lines)
        tmp = secrets_file.with_suffix(".env.tmp")
        tmp.write_text(full_content, encoding="utf-8")
        tmp.replace(secrets_file)
    return {
        "kind": KIND_SECRETS_SKELETON,
        "path": str(secrets_file),
        "added": added,
        "skipped": skipped,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_setup_secrets.py -v -k "skeleton"
```

Expected: all 5 skeleton tests PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/setup/scripts/setup_h2t.py tests/test_setup_secrets.py
git commit -m "feat(setup): add secrets_skeleton command and tests"
```

---

## Task 3: Add `secrets preflight` and validators

**Files:**
- Modify: `plugins/h2t-core/skills/setup/scripts/setup_h2t.py`
- Modify: `tests/test_setup_secrets.py`

- [ ] **Step 1: Write the failing preflight tests — append to `tests/test_setup_secrets.py`**

```python
# --- secrets_preflight tests ---

def test_preflight_found_and_uuid_valid(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("EXA_API_KEY=12345678-1234-1234-1234-123456789012\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["kind"] == "h2t_secrets_preflight/v1"
    r = result["results"][0]
    assert r["key"] == "EXA_API_KEY"
    assert r["found"] is True
    assert r["valid"] is True
    assert r["connector"] == "research"


def test_preflight_invalid_uuid(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("EXA_API_KEY=not-a-uuid\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["found"] is True
    assert result["results"][0]["valid"] is False


def test_preflight_starts_with_validator(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=secret_abc123\n")
    registry = {"NOTION_API_TOKEN": {"validator": "starts_with:secret_", "connector": "notion", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["valid"] is True


def test_preflight_starts_with_invalid(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=wrong_prefix\n")
    registry = {"NOTION_API_TOKEN": {"validator": "starts_with:secret_", "connector": "notion", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["valid"] is False


def test_preflight_missing_key(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("OTHER_KEY=value\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["found"] is False
    assert result["results"][0]["valid"] is False


def test_preflight_no_values_in_output(tmp_path):
    """Security: key values must never appear in the result JSON."""
    secrets_file = tmp_path / "secrets.env"
    secret_value = "12345678-1234-1234-1234-123456789012"
    secrets_file.write_text(f"EXA_API_KEY={secret_value}\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert secret_value not in json.dumps(result)


def test_preflight_nonempty_validator(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("MEETGEEK_API_KEY=anything\n")
    registry = {"MEETGEEK_API_KEY": {"validator": "nonempty", "connector": "meetgeek", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["valid"] is True


def test_preflight_nonempty_fails_empty(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("MEETGEEK_API_KEY=\n")
    registry = {"MEETGEEK_API_KEY": {"validator": "nonempty", "connector": "meetgeek", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(secrets_file, registry)
    assert result["results"][0]["found"] is False
    assert result["results"][0]["valid"] is False


def test_preflight_live_calls_runner(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("EXA_API_KEY=12345678-1234-1234-1234-123456789012\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    calls = []
    def fake_runner(cmd, timeout):
        calls.append(cmd)
        return {"exit_code": 0, "stdout": '{"ok": true}', "stderr": ""}
    result = setup_h2t.secrets_preflight(secrets_file, registry, live=True, runner=fake_runner)
    assert result["results"][0]["live"]["status"] == "ok"
    assert any("research" in str(c) for c in calls)
```

- [ ] **Step 2: Run to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_setup_secrets.py -v -k "preflight"
```

Expected: `AttributeError: module 'setup_h2t' has no attribute 'secrets_preflight'`

- [ ] **Step 3: Add `_validate_key` and `secrets_preflight` to `setup_h2t.py`**

Add after `secrets_skeleton`:

```python
def _read_secrets_env(secrets_file: Path) -> dict[str, str]:
    """Read KEY=VALUE pairs from secrets.env. Returns empty string for blank values."""
    values: dict[str, str] = {}
    if not secrets_file.is_file():
        return values
    for raw in secrets_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _validate_key(value: str, validator: str) -> bool:
    """Apply format validator. Never receives empty string (caller checks found first)."""
    import re
    if validator == "uuid":
        return bool(re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            value,
            re.IGNORECASE,
        ))
    if validator.startswith("starts_with:"):
        prefix = validator[len("starts_with:"):]
        return value.startswith(prefix)
    if validator == "nonempty":
        return bool(value)
    return bool(value)  # unknown validator: treat as nonempty


def secrets_preflight(
    secrets_file: Path,
    registry: dict[str, dict[str, str]],
    *,
    live: bool = False,
    runner: Runner = _run,
) -> dict[str, Any]:
    """Check each key in registry: present, non-empty, and format-valid. Never returns values.

    With live=True, also runs h2t-ops <connector> preflight for connectors that support it.
    """
    h2t_ops = resolve_h2t_ops()
    h2t_ops_path = h2t_ops.get("path", "")
    env = _read_secrets_env(secrets_file)
    results: list[dict[str, Any]] = []
    live_commands = {"research": "research preflight --json"}
    for key, meta in registry.items():
        value = env.get(key, "")
        found = bool(value)
        valid = found and _validate_key(value, meta.get("validator", "nonempty"))
        entry: dict[str, Any] = {
            "key": key,
            "found": found,
            "valid": valid,
            "connector": meta.get("connector", ""),
        }
        if live and found and h2t_ops_path:
            connector = meta.get("connector", "")
            live_cmd = live_commands.get(connector)
            if live_cmd:
                cmd = [h2t_ops_path] + live_cmd.split()
                live_result = runner(cmd, 30)
                entry["live"] = {
                    "status": "ok" if live_result.get("exit_code") == 0 else "error",
                    "exit_code": live_result.get("exit_code"),
                }
        results.append(entry)
    return {
        "kind": KIND_SECRETS_PREFLIGHT,
        "results": results,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_setup_secrets.py -v
```

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/setup/scripts/setup_h2t.py tests/test_setup_secrets.py
git commit -m "feat(setup): add secrets_preflight, validators, and security tests"
```

---

## Task 4: Wire `secrets` subcommands into CLI parser and `main()`

**Files:**
- Modify: `plugins/h2t-core/skills/setup/scripts/setup_h2t.py`

- [ ] **Step 1: Add subparser entries to `build_parser()`**

In `build_parser()`, add before `return parser`:

```python
    sk = sub.add_parser("secrets")
    sk_sub = sk.add_subparsers(dest="secrets_cmd", required=True)
    sk_skel = sk_sub.add_parser("skeleton")
    sk_skel.add_argument("--json", action="store_true")
    sk_pre = sk_sub.add_parser("preflight")
    sk_pre.add_argument("--json", action="store_true")
    sk_pre.add_argument("--live", action="store_true", help="Run live connector smoke tests")
```

- [ ] **Step 2: Add dispatch in `main()`**

In `main()`, add elif branch after the `install-h2t-ops` branch (before the `else: raise AssertionError`):

```python
        elif args.command == "secrets":
            script_dir = Path(__file__).parent
            registry_path = script_dir.parent / "known_secrets.yaml"
            try:
                registry = _load_known_secrets(registry_path)
            except FileNotFoundError as exc:
                result = {"kind": "h2t_setup_error/v1", "status": "error", "error": str(exc)}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 3
            secrets_file = _home() / ".dor" / "secrets" / "secrets.env"
            if args.secrets_cmd == "skeleton":
                result = secrets_skeleton(secrets_file, registry)
            elif args.secrets_cmd == "preflight":
                result = secrets_preflight(secrets_file, registry, live=args.live)
            else:
                raise AssertionError(args.secrets_cmd)
```

- [ ] **Step 3: Smoke test the CLI**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/setup/scripts/setup_h2t.py secrets skeleton --json
```

Expected: JSON with `kind: h2t_secrets_skeleton/v1`, `added` and `skipped` lists (no values).

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/setup/scripts/setup_h2t.py secrets preflight --json
```

Expected: JSON with `kind: h2t_secrets_preflight/v1`, per-key status (no values).

- [ ] **Step 4: Run full test suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_setup_secrets.py -v
```

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/setup/scripts/setup_h2t.py
git commit -m "feat(setup): wire secrets skeleton/preflight into CLI parser"
```

---

## Task 5: Add wizard section to SKILL.md

**Files:**
- Modify: `plugins/h2t-core/skills/setup/SKILL.md`

- [ ] **Step 1: Add `## Secrets Wizard` section at end of SKILL.md**

Append after the existing content:

```markdown
## Secrets Wizard

Triggered by user intent: "setup secrets", "configure credentials", "h2t-core:setup --secrets",
or when `connectors-check` reports any connector as `missing`.

### Step 1 — Skeleton

```bash
python setup_h2t.py secrets skeleton --json
```

From the result, show the user:
- Path to `secrets.env`
- For each key in `added`: its description and URL from `known_secrets.yaml`

### Step 2 — Fill API Keys

Tell the user:

> "Open `~/.dor/secrets/secrets.env` and paste your API keys. Here is where to get each one:
> - **EXA_API_KEY** — https://dashboard.exa.ai/api-keys
> - **NOTION_API_TOKEN** — https://www.notion.so/profile/integrations
> - **MEETGEEK_API_KEY** — https://app.meetgeek.ai/settings/api"

Open the file in an editor:

```bash
# macOS / Linux
code ~/.dor/secrets/secrets.env

# Windows
code $env:USERPROFILE\.dor\secrets\secrets.env
```

Wait for user to say "done" or "готово" before proceeding.

### Step 3 — Google OAuth

Google OAuth is triggered lazily. Always run all three trigger commands — they complete
silently if already authenticated (exit 0), or open a browser flow if not.

```bash
h2t-ops calendar list --max 1 --json
h2t-ops gmail list --max 1 --json
h2t-ops drive folders --max 1 --json
```

If any returns exit code 4 (AuthError), report the specific connector and ask the user
to re-run that connector's trigger manually.

### Step 4 — Telegram Auth

Phase 1 — check status:

```bash
h2t-ops telegram auth status
```

If already authenticated: skip to Step 5.

Phase 2 — request code (ask user for phone number first):

```bash
h2t-ops telegram auth request-code --phone <phone>
```

Phase 3 — complete login (ask user for the code from Telegram):

```bash
h2t-ops telegram auth complete --code <code>
```

If 2FA is enabled, also ask for password:

```bash
h2t-ops telegram auth complete --code <code> --password <password>
```

Confirm by re-running `auth status`.

### Step 5 — Preflight

Default (format-only, free):

```bash
python setup_h2t.py secrets preflight --json
```

If user asks for a live check (costs Exa tokens — confirm first):

```bash
python setup_h2t.py secrets preflight --live --json
```

Show a summary table: key → found/valid/connector.
Flag any `found: false` or `valid: false` with the URL from the registry.
```

- [ ] **Step 2: Verify SKILL.md renders correctly**

```bash
C:/dev/h2t-skills/.venv/Scripts/python -c "
from pathlib import Path
content = Path('plugins/h2t-core/skills/setup/SKILL.md').read_text()
assert '## Secrets Wizard' in content
assert 'secrets skeleton' in content
assert 'telegram auth status' in content
print('SKILL.md OK')
"
```

Expected: `SKILL.md OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-core/skills/setup/SKILL.md
git commit -m "feat(setup): add secrets wizard section to SKILL.md"
```

---

## Task 6: Bump version and push

**Files:**
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Bump h2t-core version**

```bash
python scripts/bump_plugin.py h2t-core <next-patch>
```

Check current version first: `cat plugins/h2t-core/.claude-plugin/plugin.json | python -c "import json,sys; print(json.load(sys.stdin)['version'])"`

- [ ] **Step 2: Push**

```bash
git add plugins/h2t-core/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(h2t-core): bump version for secrets wizard release"
git push origin main
```

- [ ] **Step 3: Reload plugin in Claude Code**

```
/plugin marketplace update
/plugin uninstall h2t-core@lichtpfad
/plugin install h2t-core@lichtpfad
/reload-plugins
```

- [ ] **Step 4: Close issue**

```bash
gh issue close 112 --repo lichtpfad/h2t-skills --comment "Implemented in commits feat(setup): secrets wizard. Wizard section in SKILL.md, skeleton+preflight in setup_h2t.py, known_secrets.yaml registry."
```
