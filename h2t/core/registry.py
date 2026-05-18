"""Connector registry: explicit ConnectorSpec, lazy discovery (spec §4)."""
from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import h2t.connectors as _connectors_pkg


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    help: str
    client: str                      # lazy "module:attr" — resolved on demand only
    register: Callable[[Any], None]


def discover() -> Iterator[ConnectorSpec]:
    """Yield CONNECTOR from each h2t.connectors.<name> subpackage (cheap import).

    A connector whose __init__ raises is skipped with a stderr warning rather
    than killing discovery for every connector (plug-in registry convention).
    """
    for mod in pkgutil.iter_modules(_connectors_pkg.__path__):
        if not mod.ispkg:
            continue
        try:
            sub = importlib.import_module(f"h2t.connectors.{mod.name}")
        except Exception as e:  # noqa: BLE001 — one bad connector must not kill the registry
            print(f"h2t: warning: skipped connector {mod.name!r}: {e}", file=sys.stderr)
            continue
        spec = getattr(sub, "CONNECTOR", None)
        if isinstance(spec, ConnectorSpec):
            yield spec


def resolve_client(spec: ConnectorSpec) -> type:
    """Import and return the client class — only when actually needed."""
    module_path, sep, attr = spec.client.partition(":")
    if not sep or not attr:
        raise ValueError(f"malformed connector client spec: {spec.client!r} (expected 'module:attr')")
    return getattr(importlib.import_module(module_path), attr)
