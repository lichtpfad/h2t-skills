import json
from h2t_ops.core.output import emit
from h2t_ops.core.errors import AuthError, ProviderError


def test_emit_json_success(capsys):
    code = emit("notion", result={"id": "p1"}, fmt="json")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"ok": True, "provider": "notion", "result": {"id": "p1"}}
    assert out.err == ""


def test_emit_json_error_to_stderr_nonzero(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="json")
    out = capsys.readouterr()
    assert code == 4
    payload = json.loads(out.err)
    assert payload["ok"] is False and payload["error"]["type"] == "auth"
    assert out.out == ""


def test_emit_md_passthrough_string(capsys):
    code = emit("notion", result="# Title\n", fmt="md")
    out = capsys.readouterr()
    assert code == 0 and "# Title" in out.out


def test_emit_human_error_writes_stderr(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="human")
    out = capsys.readouterr()
    assert code == 4 and "denied" in out.err and "Set NOTION_API_TOKEN" in out.err
    assert out.out == ""


def test_emit_human_dict_result(capsys):
    code = emit("notion", result={"key": "val"}, fmt="human")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"key": "val"}


def test_emit_human_error_no_hint(capsys):
    code = emit("notion", exc=AuthError("denied"), fmt="human")
    out = capsys.readouterr()
    assert code == 4
    assert "denied" in out.err and "hint:" not in out.err
    assert out.out == ""


import io
import sys


def test_emit_utf8_content_on_cp1252_stdout(monkeypatch):
    """Cyrillic/emoji result must not crash even when the underlying
    stdout is a cp1252 stream (the real Windows console condition)."""
    buf = io.BytesIO()
    cp = io.TextIOWrapper(buf, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stdout", cp)
    code = emit("notion", result="Привет ✨ Notion", fmt="human")
    cp.flush()
    raw = buf.getvalue()
    assert code == 0
    assert "Привет ✨ Notion" in raw.decode("utf-8")  # emit forced UTF-8


def test_emit_json_success_utf8_on_cp1252(monkeypatch):
    buf = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buf, encoding="cp1252", newline=""))
    code = emit("notion", result={"t": "Привет ✨"}, fmt="json")
    sys.stdout.flush()
    assert code == 0
    payload = json.loads(buf.getvalue().decode("utf-8"))
    assert payload["result"]["t"] == "Привет ✨"


def test_emit_encode_failure_is_nonzero(monkeypatch):
    """#141 secondary symptom: if writing the success output genuinely
    fails, emit must NOT report success (no exit 0 with broken output)."""
    class _Boom:
        encoding = "ascii"
        def write(self, *a, **k): raise UnicodeEncodeError("ascii", "x", 0, 1, "boom")
        def flush(self): pass
        def reconfigure(self, *a, **k): raise OSError("cannot reconfigure")
    monkeypatch.setattr(sys, "stdout", _Boom())
    code = emit("notion", result="Привет", fmt="human")
    assert code != 0


def test_emit_json_includes_error_details(capsys):
    code = emit(
        "research",
        exc=ProviderError(
            "Exa failed",
            details={"provider_envelope": {"status": "FAILED", "reason": "exa_4xx_nonretryable"}},
        ),
        fmt="json",
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 1
    assert payload["error"]["details"] == {
        "provider_envelope": {"status": "FAILED", "reason": "exa_4xx_nonretryable"}
    }


def test_emit_json_coerces_non_json_error_details(capsys):
    code = emit(
        "research",
        exc=ProviderError("bad", details={"bad": {"x"}}),
        fmt="json",
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 1
    assert payload["error"]["details"] == {"bad": "{'x'}"}


def test_emit_tier2_buffer_not_closed(monkeypatch):
    """Stream with .buffer but no usable .reconfigure → Tier-2 wrap;
    after emit the underlying buffer must remain OPEN (detach, not close)."""
    raw = io.BytesIO()
    class _NoReconf:
        def __init__(self, b): self.buffer = b
        def reconfigure(self, *a, **k): raise OSError("no reconfigure")
        # no write/flush of its own — Tier-2 must wrap .buffer
    s = _NoReconf(raw)
    monkeypatch.setattr(sys, "stdout", s)
    code = emit("notion", result="Привет ✨", fmt="human")
    assert code == 0
    assert not raw.closed                      # detach() kept it open
    assert "Привет ✨" in raw.getvalue().decode("utf-8")


def test_emit_tier2_finalize_runs_on_write_failure(monkeypatch):
    """Fix 1: _finalize (detach) must run on the Tier-2 wrapper even when
    the print raises UnicodeEncodeError — i.e., _finalize is in finally,
    not only on the success branch inside try."""
    raw = io.BytesIO()
    detach_called = []

    class _FailWriter:
        """Tier-2-like wrapper: has .buffer (so _utf8_writer returns created=True),
        reconfigure raises so Tier-2 path is taken, but write itself explodes."""
        def __init__(self, b):
            self.buffer = b
            self.encoding = "ascii"
            self.errors = "strict"
            self.newlines = None
        def reconfigure(self, *a, **k):
            raise OSError("no reconfigure")
        def write(self, *a, **k):
            raise UnicodeEncodeError("ascii", "x", 0, 1, "boom")
        def flush(self):
            pass
        def detach(self):
            detach_called.append(True)
            return raw

    # Patch _utf8_writer directly: return (_FailWriter, created=True) so we
    # control the exact Tier-2 scenario without relying on BytesIO internals.
    import h2t_ops.core.output as _mod
    orig_utf8_writer = _mod._utf8_writer
    fw = _FailWriter(raw)

    def _fake_utf8_writer(stream):
        if stream is sys.stdout:
            return fw, True
        return orig_utf8_writer(stream)

    monkeypatch.setattr(_mod, "_utf8_writer", _fake_utf8_writer)
    code = emit("notion", result="Привет", fmt="human")
    # Non-zero: write failure → return 1 (unchanged contract)
    assert code != 0
    # _finalize must have called detach() even though write raised
    assert detach_called, "_finalize was NOT called on the Tier-2 wrapper after write failure"
