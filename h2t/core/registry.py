"""Connector registry: explicit ConnectorSpec, lazy discovery (spec §4)."""
from __future__ import annotations

import importlib
import pkgutil
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
    """Yield CONNECTOR from each h2t.connectors.<name> subpackage (cheap import)."""
    for mod in pkgutil.iter_modules(_connectors_pkg.__path__):
        if not mod.ispkg:
            continue
        sub = importlib.import_module(f"h2t.connectors.{mod.name}")
        spec = getattr(sub, "CONNECTOR", None)
        if isinstance(spec, ConnectorSpec):
            yield spec


def resolve_client(spec: ConnectorSpec) -> type:
    """Import and return the client class — only when actually needed."""
    module_path, _, attr = spec.client.partition(":")
    return getattr(importlib.import_module(module_path), attr)
