"""Read a JSON config a person may have edited by hand (D2, #541).

Windows Notepad saves UTF-8 with a byte-order mark, which `json.loads` rejects; and a
config written from an instruction often still holds a placeholder. Both should end in a
ConfigError that names the file and the fix, not a provider error with no hint.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError

_HINT = ("Re-save it as plain JSON in UTF-8 and check the value at that position — a "
         "placeholder left in, a missing quote, a trailing comma.")


def read_json_config(path: Path) -> Any:
    """Parse `path` as JSON, tolerating a UTF-8 byte-order mark."""
    text = Path(path).read_bytes().decode("utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc.msg} at line {exc.lineno} "
                          f"column {exc.colno}.", hint=_HINT) from exc
