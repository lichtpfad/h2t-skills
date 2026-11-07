"""Deck fidelity: approved text reaches the deck word for word, each block on its slide (#599)."""

from h2t_ops.tools.creative import cli
from h2t_ops.tools.creative import fidelity as f

SRC = """---
title: x
---
# Title

## 1. Block

First paragraph that
is wrapped over two lines.

- Item one.
- Item two.

[+ Data] First figure. Second figure.

[+ Client] They came like this: «Quote one.» — I3; «Quote two.» — I4

| Rival | Frame |
|---|---|
| Northside | Sport |

---
"""

REST = ("<p>First figure.</p><p>Second figure.</p><p>They came like this:</p><blockquote>«Quote one.» — I3</blockquote>"
        "<blockquote>«Quote two.» — I4</blockquote><table><tr><th>Rival</th><th>Frame</th></tr><tr><td>Northside</td><td>Sport</td></tr></table>")
HEAD = "<main><h1>Title</h1><h2>1. Block</h2>"


def test_units_cover_headings_markers_tables():
    assert f.source_units(SRC) == [
        "Title", "1. Block",
        "First paragraph that is wrapped over two lines.", "Item one.", "Item two.",
        "First figure.", "Second figure.",
        "They came like this:", "«Quote one.» — I3", "«Quote two.» — I4",
        "Rival", "Frame", "Northside", "Sport",
    ]


def test_all_present_passes_across_markup_and_line_breaks():
    page = HEAD + "<p>First paragraph\n that is wrapped over two lines.</p><ul><li>Item one.</li><li>Item two.</li></ul>" + REST + "</main>"
    assert f.missing_units(SRC, page) == []


def test_reworded_paragraph_is_reported():
    page = HEAD + "<p>First paragraph, wrapped.</p><li>Item one.</li><li>Item two.</li>" + REST + "</main>"
    assert f.missing_units(SRC, page) == ["First paragraph that is wrapped over two lines."]


def test_dropped_marker_and_cell_are_reported():
    page = HEAD + "<p>First paragraph that is wrapped over two lines.</p><li>Item one.</li><li>Item two.</li></main>"
    missing = f.missing_units(SRC, page)
    assert "Second figure." in missing and "«Quote two.» — I4" in missing and "Northside" in missing


def test_text_outside_main_and_speaker_notes_do_not_count():
    page = "<title>First figure.</title>" + HEAD + "<!-- SPEAKER NOTE: Second figure. --></main>"
    missing = f.missing_units(SRC, page)
    assert "First figure." in missing and "Second figure." in missing


def test_omit_and_rename_are_explicit():
    units, stale = f.expected_units(SRC, omit=[{"text": "Second figure.", "why": "x"}, "not there"], rename={"1. Block": "New name"})
    assert "Second figure." not in units and "New name" in units and "1. Block" not in units
    assert stale == ["not there"]


def test_html_entities_unescaped():
    assert f.missing_units("A «quote» & more.", "<main><p>A &laquo;quote&raquo; &amp; more.</p></main>") == []


def test_attribution_replaces_quote_code():
    page = "<main>" + REST.replace("— I4", "— from an interview") + "</main>"
    assert not any("Quote two" in m for m in f.missing_units(SRC, page, attribution={"I4": "from an interview"}))


def test_markdown_markup_is_ignored():
    deck = "---\nt: x\n---\n## Slide 1. Title {.cover}\n\n::: cards\n- **Spa** — long.\n- Doctor — late.\n:::\n"
    assert f.markdown_text(deck) == "Title Spa — long. Doctor — late."


DECK = "---\nt: x\n---\n## Слайд 1. One\n\nText of the first.\n\n---\n\n## Слайд 2. Two\n\n::: quote\n«Q.» — I3\n:::\n"


def test_block_on_its_slide_passes():
    page = '<section class="slide"><p>Text of the first.</p></section><section class="slide"><p>«Q.»</p><small>— from an interview</small></section>'
    assert f.misplaced_blocks(DECK, page, {"I3": "from an interview"}) == []


def test_block_on_wrong_slide_is_reported():
    page = '<section class="slide"></section><section class="slide"><p>Text of the first.</p><p>«Q.» — I3</p></section>'
    assert f.misplaced_blocks(DECK, page) == ["slide 1: Text of the first."]


def test_slide_count_mismatch_is_reported():
    assert f.misplaced_blocks(DECK, '<section class="slide"></section>') == ["slides in the markdown: 2, in the page: 1"]


def test_cli_verify_exit_codes(tmp_path, capsys):
    (tmp_path / "approved.md").write_text("Only paragraph.\n", encoding="utf-8")
    deck = tmp_path / "deck.md"
    deck.write_text("---\nverbatim_source: approved.md\n---\n## Slide 1. S\n\nOnly paragraph.\n", encoding="utf-8")
    good, bad = tmp_path / "good.html", tmp_path / "bad.html"
    good.write_text('<main><section class="slide"><p>Only paragraph.</p></section></main>', encoding="utf-8")
    bad.write_text('<main><section class="slide"><p>Retold.</p></section></main>', encoding="utf-8")
    assert cli.main(["verify", "--deck", str(deck), "--page", str(good)]) == 0
    assert "PASS" in capsys.readouterr().out
    assert cli.main(["verify", "--deck", str(deck), "--page", str(bad), "--json"]) == 1
    assert '"missing": [\n    "Only paragraph."' in capsys.readouterr().out


def test_inline_markup_in_the_source_is_formatting_not_text():
    src = "A **bold** claim, see [the site](https://example.org).\n"
    assert f.source_units(src) == ["A bold claim, see the site."]
    page = '<main><p>A <strong>bold</strong> claim, see <a href="https://example.org">the site</a>.</p></main>'
    assert f.missing_units(src, page) == []
