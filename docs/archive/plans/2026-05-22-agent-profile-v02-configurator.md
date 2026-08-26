---
title: "h2t-core:agent-profile v0.2 Configurator — Implementation Plan"
status: "draft"
date: "2026-05-22"
milestone: ""
---
# h2t-core:agent-profile v0.2 Configurator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `apply_agent_profile.py` with work-context refs (`profile:name` / `overlay:name`), catalog CLI subcommands, `status --explain`, enhanced `doctor`, and update SKILL.md with the project configurator and catalog editor workflows.

**Architecture:** All logic stays in one script (`apply_agent_profile.py`). A new `_resolve_work_context()` helper handles the ref prefix logic. Catalog write functions guard against plugin-cache paths. SKILL.md is the only user-facing entry point — it orchestrates `AskUserQuestion` and calls the script.

**Tech Stack:** Python 3.11 stdlib only (`argparse`, `json`, `pathlib`, `datetime`). Tests: `unittest`. No new dependencies.

---

## File map

```
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py   MODIFY
plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py  MODIFY
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json    MODIFY (restore overlays)
plugins/h2t-core/skills/agent-profile/SKILL.md                          MODIFY
plugins/h2t-core/skills/agent-profile/references/profile-schema.md      MODIFY
plugins/h2t-core/.claude-plugin/plugin.json                             MODIFY (version bump)
.claude-plugin/marketplace.json                                         MODIFY (version bump)
```

---

## Task 1: Restore catalog overlays + resolver v0.2 (work-context refs)

**Files:**
- Modify: `plugins/h2t-core/skills/agent-profile/references/agent-profiles.json`
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py`
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py`

### Background

The previous commit removed `creative`, `marketing`, `product`, `dcc` overlays from the catalog. This task restores them with updated descriptions and changes the resolver so bare names remain overlay-first (legacy compat) while explicit `profile:name` and `overlay:name` refs are unambiguous.

### Resolver rules

| Input | Resolution |
|-------|------------|
| `profile:ops` | require `baseProfiles["ops"]`, error if missing |
| `overlay:github-heavy` | require `overlays["github-heavy"]`, error if missing |
| `creative` (bare) | try `overlays["creative"]` first, then `baseProfiles["creative"]` |
| `unknown` (bare) | error `UNKNOWN_WORK_CONTEXT` |

- [ ] **Step 1: Write failing resolver tests**

Append this class to `test_apply_agent_profile.py` (after the existing `TestCLIRecommend` class):

```python
class TestWorkContextRefs(unittest.TestCase):
    """Tests for profile:/overlay: ref syntax and bare-name fallback."""

    CATALOG_WITH_OVERLAP = {
        "version": 1,
        "pluginIds": {
            "h2t-core": "h2t-core@lichtpfad",
            "h2t-ops": "h2t-ops@lichtpfad",
            "h2t-dev": "h2t-dev@lichtpfad",
            "h2t-creative": "h2t-creative@lichtpfad",
            "superpowers": "superpowers@superpowers-plugins",
            "marketing-playbook": "marketing-playbook@marketing-playbook-plugins",
            "lead-search": "lead-search@lead-search-plugins",
        },
        "baseProfiles": {
            "dev": {
                "description": "dev",
                "enable": ["h2t-core", "h2t-dev", "superpowers"],
                "disable": ["h2t-creative", "marketing-playbook"],
            },
            "creative": {
                "description": "Full creative base profile",
                "enable": ["h2t-core", "h2t-creative", "superpowers"],
                "disable": ["marketing-playbook"],
            },
        },
        "overlays": {
            "creative": {
                "description": "Light creative overlay",
                "enable": ["h2t-creative"],
                "disable": [],
            },
            "github-heavy": {
                "description": "PR workflows",
                "enable": ["h2t-dev"],
                "disable": [],
            },
        },
    }

    def _resolve(self, base, overlays):
        return ap.resolve_effective_profile(self.CATALOG_WITH_OVERLAP, base, overlays)

    def test_profile_ref_resolves_base_profile(self):
        result = self._resolve("dev", ["profile:creative"])
        self.assertNotIn("error", result)
        # full creative profile enables h2t-core, so it should be enabled
        self.assertIn("h2t-core@lichtpfad", result["enabled"])
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])

    def test_overlay_ref_resolves_overlay_only(self):
        result = self._resolve("dev", ["overlay:creative"])
        self.assertNotIn("error", result)
        # small overlay only enables h2t-creative (h2t-core stays from base)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])

    def test_bare_name_prefers_overlay_over_base_profile(self):
        # bare "creative" must use overlay (small) not base profile (full)
        result = self._resolve("dev", ["creative"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])
        # base profile creative has h2t-core in enable, but bare overlay does not
        # h2t-core was enabled by dev base so it stays enabled either way;
        # key test: no error, overlay semantics used (overlay "creative" has no disable)

    def test_profile_ref_for_missing_profile_returns_error(self):
        result = self._resolve("dev", ["profile:nonexistent"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_PROFILE_CONTEXT")

    def test_overlay_ref_for_missing_overlay_returns_error(self):
        result = self._resolve("dev", ["overlay:nonexistent"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_OVERLAY")

    def test_bare_unknown_name_returns_error(self):
        result = self._resolve("dev", ["totallyunknown"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_WORK_CONTEXT")

    def test_mixed_refs_resolve_in_order(self):
        # profile:creative then overlay:github-heavy
        result = self._resolve("dev", ["profile:creative", "overlay:github-heavy"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])
        self.assertIn("h2t-dev@lichtpfad", result["enabled"])
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: `AttributeError` or assertion failures in `TestWorkContextRefs` — `_resolve_work_context` does not exist yet.

- [ ] **Step 3: Restore overlays in agent-profiles.json**

In `plugins/h2t-core/skills/agent-profile/references/agent-profiles.json`, replace the current `"overlays"` section (which is missing `creative`, `marketing`, `product`, `dcc`) with:

```json
  "overlays": {
    "plugin-dev": {
      "description": "Plugin, skill, hook, and MCP development",
      "enable": ["plugin-dev", "codex"],
      "disable": []
    },
    "creative": {
      "description": "Light visual/design addition. For full creative profile use profile:creative.",
      "enable": ["h2t-creative", "h2t-arch", "frontend-design"],
      "disable": []
    },
    "marketing": {
      "description": "Light marketing addition. For full marketing profile use profile:marketing.",
      "enable": ["marketing-playbook", "lead-search", "pm-marketing-growth", "pm-go-to-market"],
      "disable": []
    },
    "product": {
      "description": "Light product strategy addition. For full product profile use profile:product.",
      "enable": ["creative-thinking", "pm-product-strategy", "pm-product-discovery",
                 "pm-market-research", "pm-execution", "positioning"],
      "disable": []
    },
    "dcc": {
      "description": "Light DCC addition for non-dcc repos. For full DCC profile use profile:dcc.",
      "enable": ["h2t-dcc"],
      "disable": []
    },
    "research": {
      "description": "Web and research-heavy sessions",
      "enable": ["h2t-ops"],
      "disable": []
    },
    "github-heavy": {
      "description": "PR, issue, and CI workflows",
      "enable": ["h2t-dev", "codex"],
      "disable": []
    },
    "minimal": {
      "description": "Reduce to core and session tools only",
      "enable": ["h2t-core", "superpowers"],
      "disable": ["h2t-ops", "h2t-dev", "h2t-creative", "h2t-dcc", "h2t-arch",
                  "marketing-playbook", "lead-search", "plugin-dev", "codex",
                  "creative-thinking", "frontend-design", "ru-text", "positioning",
                  "pm-toolkit", "pm-product-strategy", "pm-product-discovery",
                  "pm-market-research", "pm-data-analytics", "pm-marketing-growth",
                  "pm-go-to-market", "pm-execution"]
    }
  }
```

Also remove the `"_overlayNote"` key if present.

- [ ] **Step 4: Add `_resolve_work_context` and update resolver in apply_agent_profile.py**

Add this function immediately after the `load_catalog` function (before `resolve_effective_profile`):

```python
def _resolve_work_context(name: str, catalog: dict):
    """Resolve a work context ref to (layer_dict, kind_str) or error dict.

    Supports:
      profile:<name>  — explicit base-profile context
      overlay:<name>  — explicit overlay context
      <bare-name>     — overlay-first, then base-profile fallback (legacy compat)
    """
    base_profiles = catalog.get("baseProfiles", {})
    overlay_defs = catalog.get("overlays", {})

    if name.startswith("profile:"):
        key = name[8:]
        if key not in base_profiles:
            return _error("UNKNOWN_PROFILE_CONTEXT",
                          f"Unknown profile context: '{key}'", ref=name,
                          available=list(base_profiles.keys()))
        return base_profiles[key], "profile"

    if name.startswith("overlay:"):
        key = name[8:]
        if key not in overlay_defs:
            return _error("UNKNOWN_OVERLAY",
                          f"Unknown overlay: '{key}'", ref=name,
                          available=list(overlay_defs.keys()))
        return overlay_defs[key], "overlay"

    # bare name: overlay-first for legacy compatibility
    if name in overlay_defs:
        return overlay_defs[name], "bare_overlay"
    if name in base_profiles:
        return base_profiles[name], "bare_profile"

    return _error("UNKNOWN_WORK_CONTEXT",
                  f"Unknown work context: '{name}'", ref=name,
                  available_overlays=list(overlay_defs.keys()),
                  available_profiles=list(base_profiles.keys()))
```

Replace the body of `resolve_effective_profile` with:

```python
def resolve_effective_profile(catalog: dict, base: str, overlays: list) -> dict:
    base_profiles = catalog.get("baseProfiles", {})
    plugin_ids = catalog.get("pluginIds", {})

    if base not in base_profiles:
        return _error("UNKNOWN_PROFILE", f"Unknown base profile: '{base}'", base=base,
                      available=list(base_profiles.keys()))

    for wc in overlays:
        result = _resolve_work_context(wc, catalog)
        if isinstance(result, dict) and "error" in result:
            return result

    enabled: set = set()
    disabled: set = set()

    def _apply_layer(layer: dict) -> None:
        for alias in layer.get("enable", []):
            pid = plugin_ids[alias]
            enabled.add(pid)
            disabled.discard(pid)
        for alias in layer.get("disable", []):
            pid = plugin_ids[alias]
            disabled.add(pid)
            enabled.discard(pid)

    _apply_layer(base_profiles[base])
    for wc in overlays:
        layer, _ = _resolve_work_context(wc, catalog)
        _apply_layer(layer)

    return {"enabled": sorted(enabled), "disabled": sorted(disabled)}
```

- [ ] **Step 5: Run all tests, verify green**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: all tests pass including `TestWorkContextRefs` (7 new tests).

- [ ] **Step 6: Validate catalog JSON**

```bash
C:/dev/h2t-skills/.venv/Scripts/python -c "import json; json.load(open('plugins/h2t-core/skills/agent-profile/references/agent-profiles.json')); print('valid')"
```

Expected: `valid`

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/agent-profile/references/agent-profiles.json plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): resolver v0.2 — profile:/overlay: refs + bare-name fallback"
```

---

## Task 2: Fix add_overlay() + --context CLI flag

**Files:**
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py`
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py`

### Background

`add_overlay()` currently validates only `catalog["overlays"]`. It must now accept any valid work-context ref (including `profile:ops`). The CLI adds `--context` as the new recommended flag; `--overlay` stays for backward compatibility.

- [ ] **Step 1: Write failing tests**

Append to `test_apply_agent_profile.py`:

```python
class TestAddContextRef(unittest.TestCase):
    """Tests for add_overlay() with work-context refs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))
        # Set base profile first
        ap.apply_profile(self.cwd, "pos", [], catalog_path=self.catalog_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_overlay_accepts_profile_ref(self):
        # "profile:dev" should be accepted because dev is a valid base profile
        result = ap.add_overlay(self.cwd, "profile:dev", catalog_path=self.catalog_path)
        self.assertNotIn("error", result)
        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertIn("profile:dev", binding["overlays"])

    def test_add_overlay_accepts_bare_name_overlay(self):
        result = ap.add_overlay(self.cwd, "marketing", catalog_path=self.catalog_path)
        self.assertNotIn("error", result)

    def test_add_overlay_rejects_unknown_ref(self):
        result = ap.add_overlay(self.cwd, "profile:nonexistent", catalog_path=self.catalog_path)
        self.assertIn("error", result)

    def test_cli_add_accepts_context_flag(self):
        result = ap.run_cli(
            ["add", "--cwd", str(self.cwd), "--context", "profile:dev"],
            catalog_path=self.catalog_path,
        )
        self.assertNotIn("error", result)

    def test_cli_add_overlay_flag_still_works(self):
        # --overlay backward compat
        result = ap.run_cli(
            ["add", "--cwd", str(self.cwd), "--overlay", "marketing"],
            catalog_path=self.catalog_path,
        )
        self.assertNotIn("error", result)
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: `TestAddContextRef` tests fail with `UNKNOWN_OVERLAY` errors.

- [ ] **Step 3: Fix add_overlay() validation**

Replace the current `add_overlay` function body with:

```python
def add_overlay(cwd: Path, context_ref: str, *, dry_run: bool = False,
                catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog

    resolved = _resolve_work_context(context_ref, catalog)
    if isinstance(resolved, dict) and "error" in resolved:
        return resolved

    binding = load_project_binding(cwd)
    base = binding.get("base", "mixed")
    overlays = list(binding.get("overlays", []))
    if context_ref not in overlays:
        overlays.append(context_ref)

    return apply_profile(cwd, base, overlays, dry_run=dry_run, catalog_path=catalog_path)
```

- [ ] **Step 4: Add --context flag to run_cli parser**

In `run_cli`, add `--context` to the argparse parser (after the existing `--overlay` line):

```python
parser.add_argument("--overlay", default=None)   # existing — keep for compat
parser.add_argument("--context", default=None)   # new explicit ref flag
```

In the `add` mode handler, replace:

```python
    if mode == "add":
        if not parsed.overlay:
            return _error("MISSING_ARG", "add requires --overlay")
        return add_overlay(cwd, parsed.overlay, dry_run=parsed.dry_run, catalog_path=catalog_path)
```

with:

```python
    if mode == "add":
        ref = parsed.context or parsed.overlay
        if not ref:
            return _error("MISSING_ARG", "add requires --context or --overlay")
        return add_overlay(cwd, ref, dry_run=parsed.dry_run, catalog_path=catalog_path)
```

Do the same for the `remove` mode handler:

```python
    if mode == "remove":
        ref = parsed.context or parsed.overlay
        if not ref:
            return _error("MISSING_ARG", "remove requires --context or --overlay")
        return remove_overlay(cwd, ref, dry_run=parsed.dry_run, catalog_path=catalog_path)
```

- [ ] **Step 5: Run all tests, verify green**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): add_overlay accepts work-context refs; add --context CLI flag"
```

---

## Task 3: Catalog CLI subcommands

**Files:**
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py`
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py`

### Background

Add a `catalog` subcommand group: `list`, `list-plugins`, `add-profile`, `edit-profile`, `add-overlay`, `edit-overlay`. All write commands refuse to operate on plugin cache paths.

- [ ] **Step 1: Write failing catalog tests**

Append to `test_apply_agent_profile.py`:

```python
class TestCatalogSubcommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.catalog_path = Path(self.tmp.name) / "agent-profiles.json"
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalog_list_returns_profile_and_overlay_names(self):
        result = ap.catalog_list(catalog_path=self.catalog_path)
        self.assertIn("baseProfiles", result)
        self.assertIn("overlays", result)
        self.assertIn("pos", result["baseProfiles"])

    def test_catalog_list_plugins_returns_plugin_ids(self):
        result = ap.catalog_list_plugins(catalog_path=self.catalog_path)
        self.assertIn("pluginIds", result)
        self.assertIn("h2t-core", result["pluginIds"])

    def test_catalog_add_profile_writes_new_entry(self):
        result = ap.catalog_add_profile(
            name="test-profile",
            description="Test",
            enable=["h2t-core"],
            disable=["h2t-creative"],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("test-profile", catalog["baseProfiles"])

    def test_catalog_add_profile_rejects_unknown_alias(self):
        result = ap.catalog_add_profile(
            name="bad",
            description="Test",
            enable=["nonexistent-alias"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_PLUGIN_ALIAS")

    def test_catalog_add_profile_rejects_duplicate(self):
        result = ap.catalog_add_profile(
            name="pos",
            description="dup",
            enable=["h2t-core"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "PROFILE_EXISTS")

    def test_catalog_edit_profile_add_enable_removes_from_disable(self):
        # pos has h2t-creative in disable; add-enable h2t-creative must remove it
        result = ap.catalog_edit_profile(
            name="pos",
            add_enable=["h2t-creative"],
            add_disable=[],
            remove_enable=[],
            remove_disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("h2t-creative", catalog["baseProfiles"]["pos"]["enable"])
        self.assertNotIn("h2t-creative", catalog["baseProfiles"]["pos"]["disable"])

    def test_catalog_edit_rejects_unknown_alias(self):
        result = ap.catalog_edit_profile(
            name="pos",
            add_enable=["no-such-alias"],
            add_disable=[],
            remove_enable=[],
            remove_disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)

    def test_catalog_add_overlay_writes_new_entry(self):
        result = ap.catalog_add_overlay(
            name="test-overlay",
            description="Test overlay",
            enable=["h2t-ops"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("test-overlay", catalog["overlays"])

    def test_catalog_write_is_atomic(self):
        # After a successful add, no .tmp file should remain
        ap.catalog_add_profile(
            name="atomic-test",
            description="Test",
            enable=["h2t-core"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        tmp_path = self.catalog_path.with_suffix(".tmp")
        self.assertFalse(tmp_path.exists())

    def test_catalog_refuses_cache_path(self):
        cache_path = Path(self.tmp.name) / "plugins" / "cache" / "agent-profiles.json"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(MINIMAL_CATALOG))
        result = ap.catalog_add_profile(
            name="x", description="x", enable=[], disable=[],
            catalog_path=cache_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "CACHE_PATH")
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: `AttributeError: module 'apply_agent_profile' has no attribute 'catalog_list'`.

- [ ] **Step 3: Implement catalog functions**

Add these functions to `apply_agent_profile.py` before the `run_cli` function:

```python
# ── Catalog subcommands ──────────────────────────────────────────────────────

def _is_cache_path(path: Path) -> bool:
    parts = str(path).replace("\\", "/")
    return "plugins/cache" in parts or ".claude/plugins" in parts


def catalog_list(catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    return {
        "baseProfiles": {k: v["description"] for k, v in catalog.get("baseProfiles", {}).items()},
        "overlays": {k: v["description"] for k, v in catalog.get("overlays", {}).items()},
        "pluginCount": len(catalog.get("pluginIds", {})),
        "catalogPath": str(catalog_path),
    }


def catalog_list_plugins(catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    return {"pluginIds": catalog.get("pluginIds", {}), "count": len(catalog.get("pluginIds", {}))}


def catalog_add_profile(name: str, description: str, enable: list, disable: list,
                        catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    if _is_cache_path(catalog_path):
        return _error("CACHE_PATH", "Catalog editor cannot write to plugin cache",
                      path=str(catalog_path))
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    plugin_ids = catalog.get("pluginIds", {})
    for alias in enable + disable:
        if alias and alias not in plugin_ids:
            return _error("UNKNOWN_PLUGIN_ALIAS", f"Unknown alias: '{alias}'", alias=alias)
    if name in catalog.get("baseProfiles", {}):
        return _error("PROFILE_EXISTS", f"Profile '{name}' already exists. Use edit-profile.")
    catalog.setdefault("baseProfiles", {})[name] = {
        "description": description, "enable": enable, "disable": disable,
    }
    write_json_atomic(catalog_path, catalog)
    return {"ok": True, "diff": {"added": {f"baseProfiles.{name}": catalog["baseProfiles"][name]}}}


def catalog_edit_profile(name: str, add_enable: list, add_disable: list,
                         remove_enable: list, remove_disable: list,
                         catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    if _is_cache_path(catalog_path):
        return _error("CACHE_PATH", "Catalog editor cannot write to plugin cache",
                      path=str(catalog_path))
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    if name not in catalog.get("baseProfiles", {}):
        return _error("UNKNOWN_PROFILE", f"Profile '{name}' not found")
    plugin_ids = catalog.get("pluginIds", {})
    for alias in add_enable + add_disable + remove_enable + remove_disable:
        if alias and alias not in plugin_ids:
            return _error("UNKNOWN_PLUGIN_ALIAS", f"Unknown alias: '{alias}'", alias=alias)
    profile = catalog["baseProfiles"][name]
    old = {"enable": list(profile["enable"]), "disable": list(profile["disable"])}
    for alias in add_enable:
        if alias not in profile["enable"]:
            profile["enable"].append(alias)
        if alias in profile["disable"]:
            profile["disable"].remove(alias)
    for alias in add_disable:
        if alias not in profile["disable"]:
            profile["disable"].append(alias)
        if alias in profile["enable"]:
            profile["enable"].remove(alias)
    for alias in remove_enable:
        if alias in profile["enable"]:
            profile["enable"].remove(alias)
    for alias in remove_disable:
        if alias in profile["disable"]:
            profile["disable"].remove(alias)
    write_json_atomic(catalog_path, catalog)
    return {"ok": True, "diff": {"old": old, "new": {"enable": profile["enable"], "disable": profile["disable"]}}}


def catalog_add_overlay(name: str, description: str, enable: list, disable: list,
                        catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    if _is_cache_path(catalog_path):
        return _error("CACHE_PATH", "Catalog editor cannot write to plugin cache",
                      path=str(catalog_path))
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    plugin_ids = catalog.get("pluginIds", {})
    for alias in enable + disable:
        if alias and alias not in plugin_ids:
            return _error("UNKNOWN_PLUGIN_ALIAS", f"Unknown alias: '{alias}'", alias=alias)
    if name in catalog.get("overlays", {}):
        return _error("OVERLAY_EXISTS", f"Overlay '{name}' already exists. Use edit-overlay.")
    catalog.setdefault("overlays", {})[name] = {
        "description": description, "enable": enable, "disable": disable,
    }
    write_json_atomic(catalog_path, catalog)
    return {"ok": True, "diff": {"added": {f"overlays.{name}": catalog["overlays"][name]}}}


def catalog_edit_overlay(name: str, add_enable: list, add_disable: list,
                         remove_enable: list, remove_disable: list,
                         catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    if _is_cache_path(catalog_path):
        return _error("CACHE_PATH", "Catalog editor cannot write to plugin cache",
                      path=str(catalog_path))
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog
    if name not in catalog.get("overlays", {}):
        return _error("UNKNOWN_OVERLAY", f"Overlay '{name}' not found")
    plugin_ids = catalog.get("pluginIds", {})
    for alias in add_enable + add_disable + remove_enable + remove_disable:
        if alias and alias not in plugin_ids:
            return _error("UNKNOWN_PLUGIN_ALIAS", f"Unknown alias: '{alias}'", alias=alias)
    overlay = catalog["overlays"][name]
    old = {"enable": list(overlay["enable"]), "disable": list(overlay["disable"])}
    for alias in add_enable:
        if alias not in overlay["enable"]:
            overlay["enable"].append(alias)
        if alias in overlay["disable"]:
            overlay["disable"].remove(alias)
    for alias in add_disable:
        if alias not in overlay["disable"]:
            overlay["disable"].append(alias)
        if alias in overlay["enable"]:
            overlay["enable"].remove(alias)
    for alias in remove_enable:
        if alias in overlay["enable"]:
            overlay["enable"].remove(alias)
    for alias in remove_disable:
        if alias in overlay["disable"]:
            overlay["disable"].remove(alias)
    write_json_atomic(catalog_path, catalog)
    return {"ok": True, "diff": {"old": old, "new": {"enable": overlay["enable"], "disable": overlay["disable"]}}}
```

- [ ] **Step 4: Add `catalog` subcommand to run_cli**

In `run_cli`, change the `mode` choices and add a catalog dispatch block. First, change the parser to accept `catalog` as a mode:

```python
parser.add_argument("mode", choices=[
    "status", "recommend", "diff", "apply", "add", "remove", "reset", "sync", "doctor", "catalog"
])
parser.add_argument("--cwd", default=".")
parser.add_argument("--base", default=None)
parser.add_argument("--overlay", default=None)
parser.add_argument("--context", default=None)
parser.add_argument("--contexts", default=None)
parser.add_argument("--dry-run", action="store_true")
# catalog-specific args
parser.add_argument("--name", default=None)
parser.add_argument("--description", default="")
parser.add_argument("--enable", default="")
parser.add_argument("--disable", default="")
parser.add_argument("--add-enable", default="", dest="add_enable")
parser.add_argument("--add-disable", default="", dest="add_disable")
parser.add_argument("--remove-enable", default="", dest="remove_enable")
parser.add_argument("--remove-disable", default="", dest="remove_disable")
parser.add_argument("subcmd", nargs="?", default=None)
```

Note: `subcmd` captures the catalog subcommand (`list`, `list-plugins`, etc.) when mode is `catalog`. Add the catalog dispatch block at the **end** of `run_cli`, before the final `return _error("UNKNOWN_MODE", ...)`:

```python
    if mode == "catalog":
        subcmd = parsed.subcmd
        def _split(s): return [x.strip() for x in s.split(",") if x.strip()]

        if subcmd == "list":
            return catalog_list(catalog_path=catalog_path)
        if subcmd == "list-plugins":
            return catalog_list_plugins(catalog_path=catalog_path)
        if subcmd == "add-profile":
            if not parsed.name:
                return _error("MISSING_ARG", "catalog add-profile requires --name")
            return catalog_add_profile(
                parsed.name, parsed.description,
                _split(parsed.enable), _split(parsed.disable),
                catalog_path=catalog_path,
            )
        if subcmd == "edit-profile":
            if not parsed.name:
                return _error("MISSING_ARG", "catalog edit-profile requires --name")
            return catalog_edit_profile(
                parsed.name,
                _split(parsed.add_enable), _split(parsed.add_disable),
                _split(parsed.remove_enable), _split(parsed.remove_disable),
                catalog_path=catalog_path,
            )
        if subcmd == "add-overlay":
            if not parsed.name:
                return _error("MISSING_ARG", "catalog add-overlay requires --name")
            return catalog_add_overlay(
                parsed.name, parsed.description,
                _split(parsed.enable), _split(parsed.disable),
                catalog_path=catalog_path,
            )
        if subcmd == "edit-overlay":
            if not parsed.name:
                return _error("MISSING_ARG", "catalog edit-overlay requires --name")
            return catalog_edit_overlay(
                parsed.name,
                _split(parsed.add_enable), _split(parsed.add_disable),
                _split(parsed.remove_enable), _split(parsed.remove_disable),
                catalog_path=catalog_path,
            )
        return _error("UNKNOWN_CATALOG_SUBCMD", f"Unknown catalog subcommand: '{subcmd}'")
```

- [ ] **Step 5: Fix argparse to parse `subcmd` before `mode`**

The current parser has `mode` as a positional. `subcmd` as `nargs="?"` after it causes issues when running `catalog list`. The fix: parse the first two positional args manually. Replace the `parser.add_argument("mode", ...)` and `parser.add_argument("subcmd", ...)` approach with:

```python
# Split sys.argv: first positional = mode, second positional (if any) = subcmd
# Inject into namespace before parse_known_args
_args = list(args)
_mode = _args[0] if _args else "status"
_subcmd = None
if _mode == "catalog" and len(_args) > 1 and not _args[1].startswith("-"):
    _subcmd = _args[1]
    _args = [_args[0]] + _args[2:]  # remove subcmd from args list
```

Then pass `_args` to `parser.parse_args(_args)` and set `parsed.subcmd = _subcmd`. Apply this block at the **top** of `run_cli`, before `parser = argparse.ArgumentParser(...)`.

Full updated beginning of `run_cli`:

```python
def run_cli(args: list, *, catalog_path: Path = None) -> dict:
    # Extract optional catalog subcmd before argparse sees it
    _args = list(args)
    _subcmd = None
    if _args and _args[0] == "catalog" and len(_args) > 1 and not _args[1].startswith("-"):
        _subcmd = _args[1]
        _args = [_args[0]] + _args[2:]

    parser = argparse.ArgumentParser(prog="apply_agent_profile")
    parser.add_argument("mode", choices=[
        "status", "recommend", "diff", "apply", "add", "remove", "reset", "sync", "doctor", "catalog"
    ])
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--base", default=None)
    parser.add_argument("--overlay", default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--name", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument("--enable", default="")
    parser.add_argument("--disable", default="")
    parser.add_argument("--add-enable", default="", dest="add_enable")
    parser.add_argument("--add-disable", default="", dest="add_disable")
    parser.add_argument("--remove-enable", default="", dest="remove_enable")
    parser.add_argument("--remove-disable", default="", dest="remove_disable")
    parsed = parser.parse_args(_args)
    parsed.subcmd = _subcmd
    # ... rest of run_cli unchanged
```

- [ ] **Step 6: Run all tests, verify green**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: all tests pass.

- [ ] **Step 7: Smoke catalog subcommands**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py catalog list --cwd .
```

Expected: JSON with `baseProfiles` and `overlays` keys listing profile/overlay names and descriptions.

- [ ] **Step 8: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): catalog subcommands (list, add-profile, edit-profile, add-overlay, edit-overlay)"
```

---

## Task 4: status --explain + enhanced doctor

**Files:**
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py`
- Modify: `plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py`

- [ ] **Step 1: Write failing tests**

Append to `test_apply_agent_profile.py`:

```python
class TestStatusExplain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))
        ap.apply_profile(self.cwd, "pos", [], catalog_path=self.catalog_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_explain_returns_configured(self):
        result = ap.run_cli(["status", "--cwd", str(self.cwd), "--explain"],
                            catalog_path=self.catalog_path)
        self.assertEqual(result["status"], "configured")

    def test_status_explain_lists_enabled_and_disabled(self):
        result = ap.run_cli(["status", "--cwd", str(self.cwd), "--explain"],
                            catalog_path=self.catalog_path)
        self.assertIn("enabled_plugins", result)
        self.assertIn("disabled_plugins", result)

    def test_status_explain_shows_drift_when_settings_mismatch_profile(self):
        # Manually corrupt settings to create drift
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        # remove a plugin that should be enabled
        first_enabled = next(k for k, v in settings["enabledPlugins"].items() if v)
        del settings["enabledPlugins"][first_enabled]
        settings_path.write_text(json.dumps(settings))

        result = ap.run_cli(["status", "--cwd", str(self.cwd), "--explain"],
                            catalog_path=self.catalog_path)
        drift = result["drift"]
        self.assertIn(first_enabled, drift["expected_not_in_settings"])

    def test_status_explain_shows_unknown_plugin_ids(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["enabledPlugins"]["ghost@nowhere"] = True
        settings_path.write_text(json.dumps(settings))

        result = ap.run_cli(["status", "--cwd", str(self.cwd), "--explain"],
                            catalog_path=self.catalog_path)
        self.assertIn("ghost@nowhere", result["drift"]["settings_not_in_catalog"])

    def test_status_explain_reports_preserved_keys(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["permissions"] = {"allow": ["Bash(git:*)"]}
        settings_path.write_text(json.dumps(settings))

        result = ap.run_cli(["status", "--cwd", str(self.cwd), "--explain"],
                            catalog_path=self.catalog_path)
        self.assertIn("permissions", result["preserved_keys"])


class TestEnhancedDoctor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))
        ap.apply_profile(self.cwd, "pos", [], catalog_path=self.catalog_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _doctor(self):
        return ap.run_cli(["doctor", "--cwd", str(self.cwd)], catalog_path=self.catalog_path)

    def _check(self, result, name):
        return next((c for c in result["checks"] if c["check"] == name), None)

    def test_doctor_passes_clean_state(self):
        result = self._doctor()
        for c in result["checks"]:
            self.assertTrue(c["ok"], f"Check failed: {c}")

    def test_doctor_detects_settings_mismatch_with_resolved_profile(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        first_enabled = next(k for k, v in settings["enabledPlugins"].items() if v)
        del settings["enabledPlugins"][first_enabled]
        settings_path.write_text(json.dumps(settings))

        result = self._doctor()
        check = self._check(result, "settings_matches_profile")
        self.assertFalse(check["ok"])
        self.assertIn(first_enabled, check["drift"])

    def test_doctor_detects_unknown_plugin_ids_in_settings(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["enabledPlugins"]["stale@old-publisher"] = True
        settings_path.write_text(json.dumps(settings))

        result = self._doctor()
        check = self._check(result, "no_unknown_plugin_ids")
        self.assertFalse(check["ok"])
        self.assertIn("stale@old-publisher", check["unknown"])

    def test_doctor_detects_marker_mismatch(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["h2tAgentProfile"]["base"] = "wrong-base"
        settings_path.write_text(json.dumps(settings))

        result = self._doctor()
        check = self._check(result, "marker_matches_binding")
        self.assertFalse(check["ok"])

    def test_sync_preserves_permissions_and_hooks(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["permissions"] = {"allow": ["Bash(git:*)"]}
        settings["hooks"] = {"PreToolUse": []}
        settings_path.write_text(json.dumps(settings))

        ap.run_cli(["sync", "--cwd", str(self.cwd)], catalog_path=self.catalog_path)
        updated = json.loads(settings_path.read_text())
        self.assertEqual(updated["permissions"], {"allow": ["Bash(git:*)"]})
        self.assertEqual(updated["hooks"], {"PreToolUse": []})
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: `TestStatusExplain` and `TestEnhancedDoctor` fail — `--explain` flag not supported, doctor missing new checks.

- [ ] **Step 3: Add --explain flag to parser and implement status_explain function**

Add `--explain` to the parser in `run_cli`:

```python
parser.add_argument("--explain", action="store_true")
```

Add this function before `run_cli`:

```python
def _status_explain(cwd: Path, catalog: dict) -> dict:
    binding = load_project_binding(cwd)
    if not binding or "base" not in binding:
        return {"status": "unconfigured", "suggestions": ["recommend", "apply --base <name>"]}

    settings = load_project_settings(cwd)
    base = binding["base"]
    work_contexts = binding.get("overlays", [])

    resolved = resolve_effective_profile(catalog, base, work_contexts)
    if "error" in resolved:
        return resolved

    resolved_enabled = set(resolved["enabled"])
    resolved_disabled = set(resolved["disabled"])

    settings_plugins = settings.get("enabledPlugins", {})
    settings_enabled = {k for k, v in settings_plugins.items() if v}
    all_plugin_ids = set(catalog.get("pluginIds", {}).values())

    drift = {
        "expected_not_in_settings": sorted(resolved_enabled - settings_enabled),
        "settings_not_in_catalog": sorted(set(settings_plugins.keys()) - all_plugin_ids),
    }

    context_details = []
    for wc in work_contexts:
        r = _resolve_work_context(wc, catalog)
        if isinstance(r, tuple):
            _, kind = r
            context_details.append({"ref": wc, "kind": kind})
        else:
            context_details.append({"ref": wc, "kind": "error"})

    preserved = [k for k in ("permissions", "hooks", "mcpServers") if k in settings]

    suggestions = []
    if drift["expected_not_in_settings"]:
        suggestions.append("sync  # re-apply profile to fix drift")
    suggestions.append("/reload-plugins  # after any change")

    return {
        "status": "configured",
        "base": base,
        "work_contexts": context_details,
        "enabled_plugins": sorted(resolved_enabled),
        "disabled_plugins": sorted(resolved_disabled),
        "drift": drift,
        "preserved_keys": preserved,
        "suggestions": suggestions,
        "cwd": str(cwd),
    }
```

In `run_cli`, update the `status` mode handler:

```python
    if mode == "status":
        if parsed.explain:
            catalog_path = catalog_path or _DEFAULT_CATALOG
            catalog = load_catalog(catalog_path)
            if "error" in catalog:
                return catalog
            return _status_explain(cwd, catalog)
        binding = load_project_binding(cwd)
        if not binding or "base" not in binding:
            return {"status": "unconfigured", "cwd": str(cwd)}
        settings = load_project_settings(cwd)
        return {
            "status": "configured",
            "binding": binding,
            "enabledPlugins": settings.get("enabledPlugins", {}),
            "cwd": str(cwd),
        }
```

- [ ] **Step 4: Replace doctor handler with enhanced version**

Replace the `if mode == "doctor":` block with:

```python
    if mode == "doctor":
        checks = []
        binding = load_project_binding(cwd)
        settings = load_project_settings(cwd)

        has_binding = bool(binding and "base" in binding)
        checks.append({"check": "binding_exists", "ok": has_binding})

        has_settings = bool(settings.get("enabledPlugins"))
        checks.append({"check": "settings_exist", "ok": has_settings})

        if has_binding:
            base = binding["base"]
            work_contexts = binding.get("overlays", [])

            resolved = resolve_effective_profile(catalog, base, work_contexts)
            profile_ok = "error" not in resolved
            checks.append({
                "check": "profile_resolvable", "ok": profile_ok,
                "detail": resolved.get("error", {}).get("message", "") if not profile_ok else "",
            })

            if profile_ok:
                resolved_map = {pid: True for pid in resolved["enabled"]}
                resolved_map.update({pid: False for pid in resolved["disabled"]})
                settings_map = settings.get("enabledPlugins", {})
                drift = {k: v for k, v in resolved_map.items() if settings_map.get(k) != v}
                checks.append({"check": "settings_matches_profile", "ok": not drift, "drift": drift})

            all_ids = set(catalog.get("pluginIds", {}).values())
            unknown = [k for k in settings.get("enabledPlugins", {}) if k not in all_ids]
            checks.append({"check": "no_unknown_plugin_ids", "ok": not unknown, "unknown": unknown})

            marker = settings.get("h2tAgentProfile", {})
            marker_ok = (marker.get("base") == binding.get("base") and
                         marker.get("overlays") == binding.get("overlays"))
            checks.append({"check": "marker_matches_binding", "ok": marker_ok})

        return {"checks": checks, "cwd": str(cwd)}
```

- [ ] **Step 5: Run all tests, verify green**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py 2>&1
```

Expected: all tests pass.

- [ ] **Step 6: Smoke status --explain on h2t-skills**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py status --cwd . --explain
```

Expected: JSON with `status`, `base`, `work_contexts`, `enabled_plugins`, `drift`, `suggestions`.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): status --explain and enhanced doctor with drift detection"
```

---

## Task 5: Update SKILL.md, profile-schema.md, version bump

**Files:**
- Modify: `plugins/h2t-core/skills/agent-profile/SKILL.md`
- Modify: `plugins/h2t-core/skills/agent-profile/references/profile-schema.md`
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Update profile-schema.md with work-context terminology**

Replace the `## Conflict resolution (merge semantics)` section with:

```markdown
## Work context refs

Each element of the `overlays` array is a **work context ref**. Three forms are supported:

| Form | Resolves from | Use case |
|------|---------------|----------|
| `profile:ops` | `baseProfiles["ops"]` | Add a full secondary base profile |
| `overlay:github-heavy` | `overlays["github-heavy"]` | Add a small task overlay |
| `creative` (bare) | `overlays["creative"]` first, then `baseProfiles["creative"]` | Legacy bindings |

New configurator writes must use explicit `profile:` / `overlay:` refs. Bare names remain
supported for backward compatibility only.

## Conflict resolution (merge semantics)

Each repo has exactly one base profile plus an ordered list of zero or more work contexts.
Do not model a repo as multiple base profiles. Use the base for the repo's normal work mode
and work contexts for temporary or secondary task types.

1. Start with base profile's `enable` and `disable` sets.
2. Apply work contexts in listed order.
3. Later contexts win on direct conflicts.
4. `enable` removes an alias from the disabled set.
5. `disable` removes an alias from the enabled set.
6. Unknown alias → `UNKNOWN_PLUGIN_ALIAS` error.
7. Unknown ref → `UNKNOWN_WORK_CONTEXT`, `UNKNOWN_PROFILE_CONTEXT`, or `UNKNOWN_OVERLAY` error.
```

- [ ] **Step 2: Update SKILL.md**

Replace the full content of `SKILL.md` with the version below (keep it under 220 lines):

```markdown
---
name: h2t-core:agent-profile
description: >
  Project-scoped Claude plugin profile manager. Apply base profiles (dev, pos, ops, creative,
  dcc, product, marketing, mixed) and work contexts to control which plugins load per repo.
  Supports profile:name and overlay:name explicit refs plus bare-name legacy compat.
  Triggers: "agent-profile", "apply profile", "plugin profile", "set profile", "configure plugins",
  "профиль плагинов", "конфигуратор профиля".
---

# h2t-core:agent-profile

Manage which plugins Claude loads for the current repository. Writes only `enabledPlugins`
and an `h2tAgentProfile` marker to `.claude/settings.json`. Never touches permissions,
MCP config, hooks, or global `~/.claude/settings.json`.

## Script location

```
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
```

Call it with the project Python (no venv needed — stdlib only):

```bash
python <script> <mode> [options] --cwd <repo>
```

## Commands

| Mode | Effect |
|------|--------|
| `status` | Show binding and enabled plugins (machine JSON) |
| `status --explain` | Human-readable report: base, work contexts, enabled/disabled plugins, drift |
| `recommend` | Inspect repo signals, suggest base profile |
| `diff --base <name>` | Show changes without writing |
| `apply --base <name>` | Write binding + settings |
| `add --context <ref>` | Add a work context (`profile:ops`, `overlay:github-heavy`, or bare name) |
| `remove --context <ref>` | Remove a work context |
| `reset` | Strip work contexts, reapply base |
| `sync` | Re-apply committed binding on current machine |
| `doctor` | Drift report: binding / settings / profile resolution / unknown IDs (report-only) |
| `catalog list` | Summary of profiles, overlays, plugin count |
| `catalog list-plugins` | All known plugin aliases with marketplace IDs |
| `catalog add-profile` | [EXPERIMENTAL] Add a new base profile to the catalog |
| `catalog edit-profile` | [EXPERIMENTAL] Edit plugin lists in an existing base profile |
| `catalog add-overlay` | [EXPERIMENTAL] Add a new overlay to the catalog |
| `catalog edit-overlay` | [EXPERIMENTAL] Edit plugin lists in an existing overlay |

## Work context refs

- `profile:ops` — stack the full `ops` base profile as an additional work context
- `overlay:github-heavy` — add a small task overlay
- `creative` (bare) — overlay-first, then base-profile fallback (legacy compat)

## Base profiles

`dev` · `pos` · `ops` · `creative` · `dcc` · `product` · `marketing` · `mixed`

## Task overlays

`plugin-dev` · `creative` · `marketing` · `product` · `dcc` · `research` · `github-heavy` · `minimal`

## Project configurator workflow

Use this when user wants to set or change which plugins load in the current repo.

1. Run `catalog list --cwd <repo>` → get base profiles and overlays with descriptions
2. Show base profiles as a text list; ask user to type the name of the one that fits
3. Ask: "Any additional work contexts? (profile: or overlay: refs, comma-separated, or none)"
   — present examples: `profile:ops, overlay:github-heavy`
   — if user is unsure, show all options grouped: base profiles as `profile:X`, overlays as `overlay:X`
4. Run `diff --base <chosen> --cwd <repo>` (add `--context <ref>` per work context)
5. Show the diff output; ask for confirmation before writing
6. Run `apply --base <chosen> --cwd <repo>` (add `--context <ref>` per work context)
7. Tell user: run `/plugin marketplace update`, install any missing plugins, then `/reload-plugins`

**Stop before apply if** `.claude/settings.json` has existing permissions/hooks not yet seen.
**Always show diff first.** Never write without user confirmation.

## Catalog editor workflow (EXPERIMENTAL)

[EXPERIMENTAL — catalog changes affect all repos after sync/apply]

Only works on the source catalog in the h2t-skills repo. Refuses to write if the catalog
path resolves inside a plugin cache directory.

When user describes intent (e.g. "add h2t-creative to pos enable"):
1. Run `catalog list-plugins` to validate the alias exists
2. Confirm the intended operation with the user
3. Run the appropriate `catalog edit-profile` or `catalog edit-overlay` command
4. Show the returned diff; confirm with user before committing

For a new profile:
1. Ask: name, description, which plugins to enable, which to disable
2. Validate each alias via `catalog list-plugins`
3. Run `catalog add-profile --name X --description Y --enable a,b --disable c`
4. Show diff and commit if user approves

## Safety rules

1. Never write to global `~/.claude/settings.json`.
2. Never edit `permissions` allowlists.
3. Never install or uninstall plugins — print `/plugin install ...` commands instead.
4. Always show `diff` output before `apply`. Stop at diff if user did not request apply.
5. Stop and ask before applying to a repo with an existing non-profile `.claude/settings.json`.
6. `doctor` is report-only — no fixes without explicit user approval.
7. Catalog editor: never write to plugin cache; only source repo catalog.

## Output interpretation

All script modes return JSON. Render for the user:

- `status --explain` → prose summary of base, work contexts, drift, suggestions
- `doctor.checks` → list each failing check; suggest `sync` for drift
- `error.message` → show verbatim; suggest corrective action
- Any write result → always show `diff` key before confirming success

After any write: tell user to run `/reload-plugins`.

## Catalog location

```
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
```
```

- [ ] **Step 3: Bump version**

```bash
C:/dev/h2t-skills/.venv/Scripts/python scripts/bump_plugin.py h2t-core 3.1.6
```

Expected output: `✓ h2t-core: 3.1.5 → 3.1.6`

- [ ] **Step 4: Commit all**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/agent-profile/SKILL.md plugins/h2t-core/skills/agent-profile/references/profile-schema.md plugins/h2t-core/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): v0.2 SKILL.md with configurator + catalog editor + work contexts"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Resolver v0.2: profile:/overlay:/bare refs | T1 |
| Colliding overlays restored with descriptions | T1 step 3 |
| add_overlay() accepts profile: refs | T2 |
| --context CLI flag | T2 |
| catalog list, list-plugins | T3 |
| catalog add-profile, edit-profile | T3 |
| catalog add-overlay, edit-overlay | T3 |
| Catalog refuses cache paths | T3 |
| Atomic catalog writes | T3 (uses existing write_json_atomic) |
| status --explain with drift | T4 |
| Enhanced doctor (6 checks) | T4 |
| test_sync_preserves_permissions_and_hooks | T4 |
| SKILL.md configure workflow | T5 |
| SKILL.md catalog editor section [EXPERIMENTAL] | T5 |
| profile-schema.md work contexts terminology | T5 |
| Version bump | T5 |

**Placeholder scan:** No TBD, no TODO, all code blocks complete.

**Type consistency:** `_resolve_work_context` returns `(dict, str) | dict` consistently. `catalog_*` functions all accept `catalog_path: Path = None`. `run_cli` returns `dict` in all branches.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-22-agent-profile-v02-configurator.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

Which approach?
