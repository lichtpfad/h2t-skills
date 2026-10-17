"""Hook handlers that run in-process under `h2t-hook <name>` (spec §6.2).

Each module exposes `handle(event: dict) -> Reply`; this table maps the name the wrapper
passes (`hooks/run <name>`) to it. A name not here falls through to the 3.x path in
`h2t_ops.hook_entry`. The keys are the hooks.json handler names, so Task 12 can write
`hooks/run <name>` for each entry without a second table.
"""
from __future__ import annotations

from collections.abc import Callable

from h2t_ops.hooks import gather, inject_context
from h2t_ops.hooks.emit import Reply

HANDLERS: dict[str, Callable[[dict], Reply]] = {
    "gather-on-skill": gather.handle,
    "gather-on-prompt": gather.handle_prompt,
    "inject-h2t-context": inject_context.handle,
}
