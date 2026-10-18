import pytest

from h2t_ops.lifecycle import session_record as sr


def test_round_trip_keeps_body_bytes():
    body = "# Session: s\r\n\nтело\n".encode()
    meta = {"session_id": "s", "machine": "m", "project": "p", "done": "a\nb"}
    raw = sr.render(meta, body)
    got, got_body = sr.parse(raw)
    assert got_body == body and got["done"] == "a\nb" and got["machine"] == "m"


@pytest.mark.parametrize("raw", [b"---\nsession_id: [\n---\nx", b"---\nno end", b"plain md"])
def test_broken_header_raises(raw):
    with pytest.raises(ValueError):
        sr.parse(raw)
