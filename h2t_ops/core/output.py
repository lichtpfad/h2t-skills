"""Output emitter: --json / --format md / default human (spec §6)."""
from __future__ import annotations

import io
import json
import sys
from typing import Any

from h2t_ops.core.envelope import error_envelope, success_envelope
from h2t_ops.core.errors import exit_code_for


def _utf8_writer(stream: Any) -> Any:
    """Return a UTF-8-capable writer for *stream*, without mutating the real
    process streams permanently.  Priority:
      1. reconfigure() in-place (Python 3.7+ TextIOWrapper) — works for real
         Windows console and pytest-captured streams that support it.
      2. Wrap stream.buffer directly (TextIOWrapper over the raw buffer).
      3. Fall back to the original stream (e.g. StringIO / capsys capture) —
         those already accept any str; no reconfiguration needed.
    Returns (writer, reconfigured) where reconfigured=True means we replaced
    the stream object and the caller should use writer, not stream.
    """
    # Try reconfigure — works on real Windows console TextIOWrapper
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
            return stream
        except (AttributeError, OSError, io.UnsupportedOperation):
            pass
    # Try wrapping the underlying binary buffer
    if hasattr(stream, "buffer"):
        try:
            return io.TextIOWrapper(stream.buffer, encoding="utf-8",
                                    errors="strict", newline="")
        except (AttributeError, OSError, io.UnsupportedOperation):
            pass
    # Fall back to original stream (StringIO, capsys, etc.)
    return stream


def emit(provider: str, *, result: Any = None, exc: BaseException | None = None,
         fmt: str = "human") -> int:
    """Render to stdout (success) or stderr (error). Return exit code."""
    if exc is not None:
        code = exit_code_for(exc)
        env_dict = error_envelope(provider, exc)
        err_writer = _utf8_writer(sys.stderr)
        if fmt == "json":
            print(json.dumps(env_dict, ensure_ascii=False), file=err_writer)
        else:
            env = env_dict["error"]
            line = f"error[{env['type']}]: {env['message']}"
            if env["hint"]:
                line += f"\nhint: {env['hint']}"
            print(line, file=err_writer)
        return code

    out_writer = _utf8_writer(sys.stdout)
    try:
        if fmt == "json":
            print(json.dumps(success_envelope(provider, result), ensure_ascii=False),
                  file=out_writer)
        elif fmt == "md":
            # NOTE: md and human are identical for now; they diverge in Task 9
            # (md → markdown tables, human → concise). Keep branches separate.
            print(result if isinstance(result, str)
                  else json.dumps(result, ensure_ascii=False, indent=2),
                  file=out_writer)
        else:  # human
            print(result if isinstance(result, str)
                  else json.dumps(result, ensure_ascii=False, indent=2),
                  file=out_writer)
        if hasattr(out_writer, "flush"):
            out_writer.flush()
    except (UnicodeEncodeError, OSError) as write_exc:
        # Writing the success output failed — surface as a non-zero exit so
        # callers never see exit 0 with broken/missing output (#141).
        err_writer = _utf8_writer(sys.stderr)
        try:
            print(f"error[runtime]: output encoding failed: {write_exc}",
                  file=err_writer)
        except Exception:
            pass
        return 1
    return 0
