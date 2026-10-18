"""core.downloads names: one plain segment that is a file on every platform (#548 R47)."""
import pytest

from h2t_ops.core.downloads import last_segment, plain_name


@pytest.mark.parametrize("raw, want", [
    ("CON", "_CON"), ("nul.txt", "_nul.txt"), ("Com1.log", "_Com1.log"), ("LPT9", "_LPT9"),
    ("aux .tar.gz", "_aux .tar.gz"), ("prn", "_prn"),
    ("report. ", "report"), ("report...", "report"), ("a b ", "a b"),
    ("console.txt", "console.txt"), ("COM10", "COM10"), ("nulls.csv", "nulls.csv"),
])
def test_device_names_and_trailing_dots_are_neutralised(raw, want):
    assert plain_name(raw) == want


def test_separators_drive_colon_and_leading_dots_still_go():
    assert plain_name("..\\..\\C:x/y") == "_.._C_x_y"
    assert last_segment("../a/CON.pdf") == "_CON.pdf"
