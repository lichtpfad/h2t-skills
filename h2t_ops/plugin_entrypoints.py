"""Thin entrypoint loaders for plugin-owned scripts.

These wrappers let `uv tool install --editable` expose stable command names
without moving the original plugin scripts into the package surface.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType


def _ver_key(p: Path) -> tuple:
    try:
        return tuple(int(x) for x in p.name.split("."))
    except ValueError:
        return (0,)


def plugin_root() -> Path:
    # Explicit override (useful when site-packages copy is stale)
    env = os.environ.get("H2T_CORE_PLUGIN_ROOT")
    if env:
        return Path(env)

    # Editable install: __file__ lives in the repo source tree
    candidate = Path(__file__).resolve().parent.parent / "plugins" / "h2t-core"
    if candidate.exists():
        return candidate

    # Non-editable / stale tool install: pick latest from Claude plugin cache
    cache_root = Path.home() / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-core"
    if cache_root.exists():
        versions = sorted((p for p in cache_root.iterdir() if p.is_dir()), key=_ver_key, reverse=True)
        if versions:
            return versions[0]

    raise RuntimeError(
        f"Cannot locate h2t-core plugin root (tried {candidate}).\n"
        "Fix: uv tool install --editable <path-to-h2t-skills>  "
        "or set H2T_CORE_PLUGIN_ROOT=<path>"
    )


def plugin_script_path(relative_path: str) -> Path:
    path = plugin_root() / Path(relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"Plugin entrypoint script not found: {path}")
    return path


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
