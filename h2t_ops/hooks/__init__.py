"""Hook handlers that run in-process under `h2t-hook <name>` (spec §6.2).

Each module exposes `handle(event: dict) -> Reply`; this table maps the name the wrapper
passes (`hooks/run <name>`) to it. A name not here falls through to the 3.x path in
`h2t_ops.hook_entry`. The modules are ported into this table in Task 9b.
"""
from __future__ import annotations

from collections.abc import Callable

from h2t_ops.hooks.emit import Reply

HANDLERS: dict[str, Callable[[dict], Reply]] = {}
