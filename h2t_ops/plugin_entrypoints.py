"""Thin entrypoint loaders for plugin-owned scripts.

These wrappers expose stable command names without moving the plugin scripts
into the package surface, so the root has to be discovered at runtime. It is
looked up in this order, first hit containing the requested script wins:

1. ``H2T_PLUGIN_ROOT`` — explicit operator override.
2. ``CLAUDE_PLUGIN_ROOT`` — exported by the harness while a skill runs. It can
   point at a different plugin, so a miss falls through instead of failing.
3. ``<package parent>/plugins/h2t-core`` — an editable install from a checkout.
4. The installed plugin cache, highest version first.

Step 4 is what makes a non-editable ``uv tool install git+...`` work: the wheel
ships ``h2t_ops`` only, so nothing named ``plugins/`` sits beside the package
and steps 1-3 all miss.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

PLUGIN_NAME = "h2t-core"
ENV_VARS = ("H2T_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")


def _package_plugin_root() -> Path:
    """Where the plugin sits in an editable install from a repo checkout."""
    return Path(__file__).resolve().parent.parent / "plugins" / PLUGIN_NAME


def _version_key(path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in path.name.split("."))
    except ValueError:
        return ()


def _cache_plugin_roots() -> list[Path]:
    """Installed plugin versions, newest first; the `latest` dir can lag behind."""
    base = Path.home() / ".claude" / "plugins" / "cache" / "lichtpfad" / PLUGIN_NAME
    if not base.is_dir():
        return []
    versioned = sorted(
        (p for p in base.iterdir() if p.is_dir() and _version_key(p)),
        key=_version_key,
        reverse=True,
    )
    latest = base / "latest"
    return versioned + ([latest] if latest.is_dir() else [])


def candidate_roots() -> list[Path]:
    roots = [Path(os.environ[var]).expanduser() for var in ENV_VARS if os.environ.get(var)]
    roots.append(_package_plugin_root())
    roots.extend(_cache_plugin_roots())
    return roots


def plugin_root() -> Path:
    for root in candidate_roots():
        if root.is_dir():
            return root
    raise FileNotFoundError(_not_found_message(""))


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
