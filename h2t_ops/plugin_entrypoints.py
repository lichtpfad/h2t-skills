"""Thin entrypoint loaders for plugin-owned scripts.

These wrappers let `uv tool install --editable` expose stable command names
without moving the original plugin scripts into the package surface.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent / "plugins" / "h2t-core"


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
