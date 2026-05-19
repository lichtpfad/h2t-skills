"""Output emitter: --json / --format md / default human (spec §6)."""
from __future__ import annotations

import io
import json
import sys
from typing import Any


from h2t_ops.core.envelope import error_envelope, success_envelope
from h2t_ops.core.errors import exit_code_for


def _utf8_writer(stream: Any) -> tuple[Any, bool]:
    """Return ``(writer, created)`` — a UTF-8-capable writer for *stream*,
    without permanently mutating the real process streams.

    ``created`` is True ONLY when this function constructed a brand-new
    ``io.TextIOWrapper`` over ``stream.buffer`` (Tier 2). In that case the
    caller MUST ``detach()`` the writer once done so GC does not close the
    underlying ``sys.stdout``/``sys.stderr`` buffer.

    Tiers:
      1. ``stream.reconfigure(encoding="utf-8")`` in-place — real Windows
         console / pytest streams that support it. created=False.
      2. ``io.TextIOWrapper(stream.buffer, encoding="utf-8")`` — wraps the
         raw binary buffer. created=True (caller must detach).
      3. Fall back to the original stream (StringIO / capsys capture — they
         already accept any str). created=False.
    """
    # Tier 1: reconfigure in place — works on real Windows console
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
            return stream, False
        except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
            pass
    # Tier 2: wrap the underlying binary buffer (caller must detach)
    if hasattr(stream, "buffer"):
        try:
            return io.TextIOWrapper(stream.buffer, encoding="utf-8",
                                    errors="strict", newline=""), True
        except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
            pass
    # Tier 3: fall back to original stream (StringIO, capsys, etc.)
    return stream, False


def _finalize(writer: Any, created: bool) -> None:
    """Flush *writer*; if it was a Tier-2 wrapper we created, detach it so
    GC does not close the real underlying process buffer (one-shot use)."""
    if hasattr(writer, "flush"):
        writer.flush()
    if created and hasattr(writer, "detach"):
        try:
            writer.detach()
        except (ValueError, AttributeError):
            pass


def emit(provider: str, *, result: Any = None, exc: BaseException | None = None,
         fmt: str = "human") -> int:
    """Render to stdout (success) or stderr (error). Return exit code."""
    if exc is not None:
        code = exit_code_for(exc)
        env_dict = error_envelope(provider, exc)
        err_writer, err_created = _utf8_writer(sys.stderr)
        if fmt == "json":
            print(json.dumps(env_dict, ensure_ascii=False), file=err_writer)
        else:
            env = env_dict["error"]
            line = f"error[{env['type']}]: {env['message']}"
            if env["hint"]:
                line += f"\nhint: {env['hint']}"
            print(line, file=err_writer)
        _finalize(err_writer, err_created)
        return code

    out_writer, out_created = _utf8_writer(sys.stdout)
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
        _finalize(out_writer, out_created)
    except (UnicodeEncodeError, OSError) as write_exc:
        # Writing the success output failed — surface as a non-zero exit so
        # callers never see exit 0 with broken/missing output (#141).
        err_writer, err_created = _utf8_writer(sys.stderr)
        try:
            print(f"error[runtime]: output encoding failed: {write_exc}",
                  file=err_writer)
            _finalize(err_writer, err_created)
        except Exception:
            pass
        return 1
    return 0
