"""h2t-core:agent-profile — deterministic project plugin profile manager.

Usage:
    python apply_agent_profile.py <mode> --cwd <repo> [options]

Modes: status recommend diff apply add remove reset sync doctor
Output: JSON on stdout (skill translates to human guidance).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Default catalog lives next to this script's parent references/
_DEFAULT_CATALOG = Path(__file__).parent.parent / "references" / "agent-profiles.json"


# ── Error helpers ────────────────────────────────────────────────────────────

def _error(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


# ── Catalog ──────────────────────────────────────────────────────────────────

def load_catalog(path: Path) -> dict:
    """Load and validate catalog JSON. Returns error dict on bad aliases."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _error("CATALOG_LOAD_FAILED", str(exc))

    plugin_ids = data.get("pluginIds", {})

    # Validate all aliases used in baseProfiles and overlays exist in pluginIds
    for section_key in ("baseProfiles", "overlays"):
        for profile_name, profile in data.get(section_key, {}).items():
            for alias in profile.get("enable", []) + profile.get("disable", []):
                if alias not in plugin_ids:
                    return _error(
                        "UNKNOWN_PLUGIN_ALIAS",
                        f"Alias '{alias}' in {section_key}.{profile_name} not in pluginIds",
                        alias=alias,
                        section=section_key,
                        profile=profile_name,
                    )

    return data


def _resolve_work_context(name: str, catalog: dict):
    """Resolve a work context ref to (layer_dict, kind_str) or error dict.

    Supports:
      profile:<name>  — explicit base-profile context
      overlay:<name>  — explicit overlay context
      <bare-name>     — overlay-first, then base-profile fallback (legacy compat)
    Returns tuple (layer_dict, kind_str) on success, or error dict on failure.
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


def resolve_effective_profile(catalog: dict, base: str, overlays: list) -> dict:
    """Merge base profile + overlays into enabled/disabled plugin id sets.

    Returns error dict on unknown base or overlay names.
    Supports profile:/overlay: prefixes and bare-name legacy fallback.
    Merge rules:
      1. Start from base enable/disable sets.
      2. Apply work contexts in order; later wins on conflict.
      3. enable removes from disabled; disable removes from enabled.
    """
    base_profiles = catalog.get("baseProfiles", {})
    plugin_ids = catalog.get("pluginIds", {})

    if base not in base_profiles:
        return _error("UNKNOWN_PROFILE", f"Unknown base profile: '{base}'", base=base,
                      available=list(base_profiles.keys()))

    # Validate all work context refs up front
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
        layer, _ = _resolve_work_context(wc, catalog)  # already validated above
        assert isinstance(layer, dict), f"unexpected error from validated ref: {wc}"
        _apply_layer(layer)

    return {"enabled": sorted(enabled), "disabled": sorted(disabled)}


# ── JSON I/O ─────────────────────────────────────────────────────────────────

def load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


# ── Project binding ──────────────────────────────────────────────────────────

def _binding_path(cwd: Path) -> Path:
    return cwd / ".claude" / "agent-profile.json"


def _settings_path(cwd: Path) -> Path:
    return cwd / ".claude" / "settings.json"


def load_project_binding(cwd: Path) -> dict:
    return load_json(_binding_path(cwd))


def write_project_binding(cwd: Path, binding: dict) -> None:
    write_json_atomic(_binding_path(cwd), binding)


def load_project_settings(cwd: Path) -> dict:
    return load_json(_settings_path(cwd))


def write_project_settings(cwd: Path, settings: dict) -> None:
    write_json_atomic(_settings_path(cwd), settings)


# ── Core apply logic ─────────────────────────────────────────────────────────

def _build_settings_patch(catalog: dict, base: str, overlays: list) -> dict:
    """Return patch dict {enabledPlugins, marker} on success, or error dict on failure."""
    result = resolve_effective_profile(catalog, base, overlays)
    if "error" in result:
        return result
    enabled_map = {}
    for pid in result["enabled"]:
        enabled_map[pid] = True
    for pid in result["disabled"]:
        enabled_map[pid] = False
    marker = {
        "base": base,
        "overlays": overlays,
        "managedBy": "h2t-core:agent-profile",
        "updatedAt": str(date.today()),
    }
    return {"enabledPlugins": enabled_map, "marker": marker}


def apply_profile(cwd: Path, base: str, overlays: list, *, dry_run: bool = False,
                  catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog

    patch = _build_settings_patch(catalog, base, overlays)
    if patch is None or "error" in patch:
        return patch or _error("APPLY_FAILED", "Unknown error building settings patch")

    binding = {
        "base": base,
        "overlays": overlays,
        "updatedAt": str(date.today()),
        "catalogVersion": catalog.get("version", 1),
    }

    settings = load_project_settings(cwd)
    new_settings = dict(settings)
    new_settings["enabledPlugins"] = patch["enabledPlugins"]
    new_settings["h2tAgentProfile"] = patch["marker"]

    diff = _compute_diff(settings, new_settings)

    if not dry_run:
        write_project_binding(cwd, binding)
        write_project_settings(cwd, new_settings)

    return {"ok": True, "dry_run": dry_run, "diff": diff, "binding": binding,
            "enabledPlugins": patch["enabledPlugins"]}


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


def remove_overlay(cwd: Path, overlay: str, *, dry_run: bool = False,
                   catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog

    binding = load_project_binding(cwd)
    base = binding.get("base", "mixed")
    overlays = [o for o in binding.get("overlays", []) if o != overlay]

    return apply_profile(cwd, base, overlays, dry_run=dry_run, catalog_path=catalog_path)


def reset_profile(cwd: Path, *, dry_run: bool = False, catalog_path: Path = None) -> dict:
    catalog_path = catalog_path or _DEFAULT_CATALOG
    binding = load_project_binding(cwd)
    base = binding.get("base", "mixed")
    return apply_profile(cwd, base, [], dry_run=dry_run, catalog_path=catalog_path)


# ── Diff helper ──────────────────────────────────────────────────────────────

def _compute_diff(old: dict, new: dict) -> dict:
    old_plugins = old.get("enabledPlugins", {})
    new_plugins = new.get("enabledPlugins", {})
    added = {k: v for k, v in new_plugins.items() if k not in old_plugins or old_plugins[k] != v}
    removed = {k: v for k, v in old_plugins.items() if k not in new_plugins}
    return {"changed": added, "removed": removed}


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


# ── Status explain ───────────────────────────────────────────────────────────

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


# ── CLI modes ────────────────────────────────────────────────────────────────

def _recommend(cwd: Path, catalog: dict) -> str:
    """Heuristic: return best base profile name for this repo."""
    if (cwd / ".claude-plugin").exists() or (cwd / ".claude-plugin" / "marketplace.json").exists():
        return "dev"
    if (cwd / "plugins" / "h2t-core").exists():
        return "dev"
    if (cwd / "h2t_ops").exists() or (cwd / "plugins" / "h2t-ops").exists():
        return "ops"
    if any(cwd.glob("*.toe")) or any(cwd.glob("*.hip")):
        return "dcc"
    if (cwd / "plugins" / "h2t-creative").exists():
        return "creative"
    return "mixed"


def run_cli(args: list, *, catalog_path: Path = None) -> dict:
    """Parse CLI args and run the requested mode. Returns JSON-serialisable dict."""
    # Extract optional catalog subcmd before argparse sees it
    _args = list(args)
    _subcmd = None
    if _args and _args[0] == "catalog" and len(_args) > 1 and not _args[1].startswith("-"):
        _subcmd = _args[1]
        _args = [_args[0]] + _args[2:]

    parser = argparse.ArgumentParser(prog="apply_agent_profile")
    parser.add_argument("mode", choices=[
        "status", "recommend", "diff", "apply", "add", "remove", "reset", "sync", "doctor",
        "catalog",
    ])
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--base", default=None)
    parser.add_argument("--overlay", default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--explain", action="store_true")
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

    cwd = Path(parsed.cwd).resolve()
    catalog_path = catalog_path or _DEFAULT_CATALOG
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return catalog

    mode = parsed.mode

    if mode == "status":
        if parsed.explain:
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

    if mode == "recommend":
        recommended = _recommend(cwd, catalog)
        return {"recommended": recommended, "cwd": str(cwd)}

    if mode == "diff":
        base = parsed.base or load_project_binding(cwd).get("base", "mixed")
        ref = parsed.context or parsed.overlay
        overlays = [ref] if ref else load_project_binding(cwd).get("overlays", [])
        result = apply_profile(cwd, base, overlays, dry_run=True, catalog_path=catalog_path)
        return result

    if mode == "apply":
        base = parsed.base
        if not base:
            return _error("MISSING_ARG", "apply requires --base")
        ref = parsed.context or parsed.overlay
        overlays = [ref] if ref else []
        return apply_profile(cwd, base, overlays, dry_run=parsed.dry_run, catalog_path=catalog_path)

    if mode == "add":
        ref = parsed.context or parsed.overlay
        if not ref:
            return _error("MISSING_ARG", "add requires --context or --overlay")
        return add_overlay(cwd, ref, dry_run=parsed.dry_run, catalog_path=catalog_path)

    if mode == "remove":
        ref = parsed.context or parsed.overlay
        if not ref:
            return _error("MISSING_ARG", "remove requires --context or --overlay")
        return remove_overlay(cwd, ref, dry_run=parsed.dry_run, catalog_path=catalog_path)

    if mode == "reset":
        return reset_profile(cwd, dry_run=parsed.dry_run, catalog_path=catalog_path)

    if mode == "sync":
        binding = load_project_binding(cwd)
        if not binding or "base" not in binding:
            return _error("NO_BINDING", "No .claude/agent-profile.json found. Run apply first.")
        base = binding["base"]
        overlays = binding.get("overlays", [])
        result = apply_profile(cwd, base, overlays, dry_run=False, catalog_path=catalog_path)
        if "error" in result:
            return result
        result["synced"] = True
        result["message"] = "Settings updated. Run /reload-plugins to apply."
        return result

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

    return _error("UNKNOWN_MODE", f"Unknown mode: {mode}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run_cli(sys.argv[1:])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
