"""Output emitter: --json / --format md / default human (spec §6)."""
from __future__ import annotations

import json
import sys
from typing import Any

from h2t.core.envelope import error_envelope, success_envelope
from h2t.core.errors import exit_code_for


def emit(provider: str, *, result: Any = None, exc: BaseException | None = None,
         fmt: str = "human") -> int:
    """Render to stdout (success) or stderr (error). Return exit code."""
    if exc is not None:
        code = exit_code_for(exc)
        if fmt == "json":
            print(json.dumps(error_envelope(provider, exc), ensure_ascii=False), file=sys.stderr)
        else:
            env = error_envelope(provider, exc)["error"]
            line = f"error[{env['type']}]: {env['message']}"
            if env["hint"]:
                line += f"\nhint: {env['hint']}"
            print(line, file=sys.stderr)
        return code
    if fmt == "json":
        print(json.dumps(success_envelope(provider, result), ensure_ascii=False))
    elif fmt == "md":
        print(result if isinstance(result, str)
              else json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result if isinstance(result, str)
              else json.dumps(result, ensure_ascii=False, indent=2))
    return 0
