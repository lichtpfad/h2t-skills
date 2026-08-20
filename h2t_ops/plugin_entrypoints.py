"""Thin entrypoint loaders for plugin-owned scripts.

These wrappers expose stable command names without moving the plugin scripts
into the package surface, so the root has to be discovered at runtime. It is
looked up in this order, first hit containing the requested script wins:

1. ``H2T_PLUGIN_ROOT`` — explicit operator override.
2. ``CLAUDE_PLUGIN_ROOT`` — exported by Claude Code while a skill runs, and by
   Codex for plugin hooks. It can point at a different plugin, so a miss falls
   through instead of failing.
3. ``<package parent>/plugins/h2t-core`` — an editable install from a checkout.
4. An installed plugin cache — Claude Code's or Codex's, newest version first.
5. ``h2t_ops/_plugin_payload`` — the copy force-included into the wheel.

Steps 4 and 5 are what make a non-editable ``uv tool install git+...`` work: the
wheel ships ``h2t_ops`` and ``lib`` only, so nothing named ``plugins/`` sits
beside the package and steps 1-3 all miss. Step 5 is last because it is frozen
at build time — an installed plugin can be newer.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

PLUGIN_NAME = "h2t-core"
ENV_VARS = ("H2T_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
# Plugin hosts, and the env var that relocates each one's state directory.
HOST_STATE_DIRS = (("CLAUDE_CONFIG_DIR", ".claude"), ("CODEX_HOME", ".codex"))


def _package_plugin_root() -> Path:
    """Where the plugin sits in an editable install from a repo checkout."""
    return Path(__file__).resolve().parent.parent / "plugins" / PLUGIN_NAME


def _bundled_payload_root() -> Path:
    """The copy shipped inside the wheel; absent in a source checkout."""
    return Path(__file__).resolve().parent / "_plugin_payload"


def _host_state_dirs() -> list[Path]:
    dirs = []
    for var, default in HOST_STATE_DIRS:
        override = os.environ.get(var)
        dirs.append(Path(override).expanduser() if override else Path.home() / default)
    return dirs


def _version_key(path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in path.name.split("."))
    except ValueError:
        return ()


def _cache_plugin_roots() -> list[Path]:
    """Installed versions across every host and marketplace, newest first.

    The marketplace name is whatever the catalog was registered as, so it is not
    assumed. Version directories are semver under Claude Code, but Codex names
    them `local` for local plugins and uses content hashes for curated ones, and
    Claude Code's `latest` lags behind the versioned ones — so anything that
    does not parse as semver is ordered by mtime, after the ones that do.
    """
    versioned: list[Path] = []
    dated: list[Path] = []
    for state_dir in _host_state_dirs():
        cache = state_dir / "plugins" / "cache"
        if not cache.is_dir():
            continue
        for marketplace in sorted(cache.iterdir()):
            plugin = marketplace / PLUGIN_NAME
            if not plugin.is_dir():
                continue
            for version in plugin.iterdir():
                if version.is_dir():
                    (versioned if _version_key(version) else dated).append(version)
    versioned.sort(key=_version_key, reverse=True)
    dated.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return versioned + dated


def candidate_roots() -> list[Path]:
    roots = [Path(os.environ[var]).expanduser() for var in ENV_VARS if os.environ.get(var)]
    roots.append(_package_plugin_root())
    roots.extend(_cache_plugin_roots())
    roots.append(_bundled_payload_root())
    return roots


def _not_found_message(relative_path: str) -> str:
    tried = "\n".join(f"  {root / relative_path}" for root in candidate_roots())
    return (
        f"Plugin entrypoint script not found: {relative_path}\n"
        f"tried:\n{tried}\n"
        f"Set {ENV_VARS[0]} to the {PLUGIN_NAME} plugin directory to override."
    )


def plugin_script_path(relative_path: str) -> Path:
    for root in candidate_roots():
        path = root / Path(relative_path)
        if path.is_file():
            return path
    raise FileNotFoundError(_not_found_message(relative_path))


def load_plugin_module(relative_path: str) -> ModuleType:
    script_path = plugin_script_path(relative_path)
    module_name = "_h2t_plugin_" + relative_path.replace("\\", "_").replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load plugin module spec: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_plugin_main(relative_path: str) -> int:
    module = load_plugin_module(relative_path)
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError(f"Plugin entrypoint has no callable main(): {relative_path}")
    result = main()
    return int(result) if isinstance(result, int) else 0
