import pytest

from h2t_ops.lifecycle import session_record as sr


def test_round_trip_keeps_body_bytes():
    body = "# Session: s\r\n\nтело\n".encode()
    meta = {"session_id": "s", "machine": "m", "project": "p", "done": "a\nb"}
    raw = sr.render(meta, body)
    got, got_body = sr.parse(raw)
    assert got_body == body and got["done"] == "a\nb" and got["machine"] == "m"


@pytest.mark.parametrize("encoding", ["lf", "crlf", "bom-lf", "bom-crlf"])
def test_crlf_and_bom_records_parse_with_their_body_exact(encoding):
    """A record a Windows editor or autocrlf rewrote is the same record: same meta, and the
    body is the bytes after the closing fence, untouched."""
    meta = {"session_id": "s", "machine": "m", "project": "p", "done": "a"}
    raw = sr.render(meta, b"# Session: s\n\nbody\n")
    if "crlf" in encoding:
        raw = raw.replace(b"\n", b"\r\n")
    if encoding.startswith("bom"):
        raw = b"\xef\xbb\xbf" + raw
    got, body = sr.parse(raw)
    assert got == meta
    assert body == (b"# Session: s\r\n\r\nbody\r\n" if "crlf" in encoding else b"# Session: s\n\nbody\n")


@pytest.mark.parametrize("raw", [b"---\nsession_id: [\n---\nx", b"---\nno end", b"plain md"])
def test_broken_header_raises(raw):
    with pytest.raises(ValueError):
        sr.parse(raw)
