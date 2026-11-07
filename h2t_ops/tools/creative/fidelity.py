"""Deck fidelity: the text of an approved source reaches the built deck unchanged.

Content is fixed, layout is free. A deck built from approved text keeps every fragment of
it word for word; splitting slides, reordering on a slide and the visual form of a number
are the agent's choice. This module checks the content half (#599).

Inputs are the deck markdown, whose frontmatter names the source, and the built page:

    verbatim_source: docs/approved.md     # the approved text
    omit:                                  # fragments decided not to show, each with a reason
      - text: "Image: path/to/file.svg."
        why: "internal path; the image itself is on the slide"
    rename:                                # headings renamed by the owner, old: new
      "Old heading": "New heading"
    attribution:                           # quote code in the source -> caption on the slide
      I3: "from a client interview"

Units of the source: headings, paragraphs, list items, table cells, and marker lines
(`[+ Label] text`). A marker line with quotes (`«…» — I3`) splits into the quotes and the
lead-in around them; one without quotes splits into sentences; the label itself is not
checked. Only the `---` separator is skipped; `**` and link markup are dropped, the page
shows them as formatting. Matching is against the visible text of the
page, whitespace collapsed, so a line break or a tag inside a fragment does not matter.
A unit counts as present when it occurs anywhere in that text: a one-word table cell can be
satisfied by the same word elsewhere on the page.

`misplaced_blocks` adds the check the verbatim one cannot make: that each block of the deck
markdown landed on its own slide (`## Slide N.` / `## Слайд N.`), not on a neighbour.
"""
from __future__ import annotations

import html
import re

import yaml

QUOTE = re.compile(r"(?:«[^»]*»|“[^”]*”)\s*—\s*[^\s;,]+")
QUOTE_CODE = re.compile(r"((?:«.*»|“.*”)\s*—\s*)([^\s;,]+)", flags=re.S)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z0-9«“])")
SLIDE_HEADING = re.compile(r"^## (?:Слайд|Slide) \d+\..*$", flags=re.M)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _unmark(text: str) -> str:
    """Inline markdown a page shows as formatting, not as text: `**bold**`, `[text](url)`."""
    return re.sub(r"(?<!!)\[([^\]]+)\]\([^)\s]+\)", r"\1", text).replace("**", "")


def _body(md_text: str) -> str:
    return md_text.split("---\n", 2)[2] if md_text.startswith("---\n") else md_text


def frontmatter(md_text: str) -> dict:
    if not md_text.startswith("---\n"):
        return {}
    return yaml.safe_load(md_text.split("---\n", 2)[1]) or {}


def _marker_units(block: str) -> list[str]:
    rest = _flat(re.match(r"\[\+[^\]]*\]\s*(.*)", block, flags=re.S).group(1))
    quotes = QUOTE.findall(rest)
    if quotes:
        lead = QUOTE.sub("", rest).strip(" ;")
        return ([lead] if lead else []) + quotes
    return [s for s in SENTENCE_END.split(rest) if s]


def _table_units(block: str) -> list[str]:
    cells = []
    for row in block.splitlines():
        if re.fullmatch(r"[\s|:-]+", row):
            continue
        cells += [_flat(c) for c in row.strip().strip("|").split("|") if c.strip()]
    return cells


def source_units(md_text: str) -> list[str]:
    """Every checkable fragment of the approved text, frontmatter excluded."""
    units = []
    for block in re.split(r"\n\s*\n", _body(md_text)):
        block = block.strip()
        if not block or block == "---":
            continue
        if block.startswith("#"):
            units.append(_flat(block.lstrip("#")))
        elif block.startswith("|"):
            units += _table_units(block)
        elif block.startswith("[+"):
            units += _marker_units(block)
        elif block.startswith("- "):
            units += [_flat(i) for i in re.split(r"^- ", block, flags=re.M) if i.strip()]
        else:
            units.append(_flat(block))
    return [_unmark(u) for u in units]


def _attribute(text: str, attribution: dict) -> str:
    m = QUOTE_CODE.fullmatch(text)
    if m and m.group(2) in attribution:
        return m.group(1) + str(attribution[m.group(2)])
    return text


def expected_units(source_md: str, omit=(), rename=None, attribution=None) -> tuple[list[str], list[str]]:
    """Fragments the deck must contain, and `omit` entries not found in the source."""
    rename, attribution = rename or {}, attribution or {}
    units = source_units(source_md)
    omit_texts = [_flat(o["text"] if isinstance(o, dict) else o) for o in omit]
    stale = [o for o in omit_texts if o not in units]
    out = [_attribute(rename.get(u, u), attribution) for u in units if u not in omit_texts]
    return out, stale


INLINE_TAG = re.compile(r"</?(?:a|strong|em|i|code|small|sup|sub)\b[^>]*>")


def visible_text(page_html: str) -> str:
    """Page text after `<main`: inline tags vanish, any other tag is a word break.

    `<b>` and `<span>` stay word breaks: deck figures use them as separate lines
    (`<b>44%</b><span>of revenue</span>`)."""
    body = INLINE_TAG.sub("", page_html.split("<main", 1)[-1])
    return _flat(html.unescape(re.sub(r"<[^>]+>", " ", body)))


def markdown_text(deck_md: str) -> str:
    """Visible text of the deck markdown: no frontmatter, block markup or inline tags."""
    lines = []
    for line in _body(deck_md).splitlines():
        if line.startswith(":::") or re.fullmatch(r"[\s|:-]+", line or "x"):
            continue
        line = re.sub(r"^## (?:Слайд|Slide) \d+\.\s*", "", line)
        line = re.sub(r"\s*\{\.[\w-]+\}\s*$", "", line)
        line = _unmark(re.sub(r"^- ", "", line))
        if line.startswith("|"):
            line = " ".join(line.strip().strip("|").split("|"))
        lines.append(line)
    return _flat(re.sub(r"<[^>]+>", " ", INLINE_TAG.sub("", "\n".join(lines))))


def missing_units(source_md: str, page_html: str, omit=(), rename=None, attribution=None) -> list[str]:
    page = visible_text(page_html)
    units, _ = expected_units(source_md, omit, rename, attribution)
    return [u for u in units if u not in page]


def _md_slides(deck_md: str) -> list[str]:
    return [s.strip().rstrip("-").strip() for s in SLIDE_HEADING.split(_body(deck_md))[1:]]


def misplaced_blocks(deck_md: str, page_html: str, attribution=None) -> list[str]:
    """Blocks of the deck markdown that are not on the slide with the same number."""
    attribution = attribution or {}
    md_slides = _md_slides(deck_md)
    sections = re.findall(r'<section class="slide[^"]*">(.*?)</section>', page_html, flags=re.S)
    if len(md_slides) != len(sections):
        return [f"slides in the markdown: {len(md_slides)}, in the page: {len(sections)}"]
    bad = []
    for n, (md, sec) in enumerate(zip(md_slides, sections), 1):
        text = visible_text("<main>" + sec)
        blocks = []
        for block in re.split(r"\n\s*\n", md):
            lines = [line for line in block.splitlines() if not line.startswith(":::")]
            if lines and all(line.startswith("- ") for line in lines):
                blocks += lines  # list items one by one: a figure may stand between them
            else:
                blocks.append(block)
        for block in blocks:
            want = _attribute(markdown_text(block), attribution)
            if want and not want.startswith("![") and want not in text:
                bad.append(f"slide {n}: {want[:80]}")
    return bad


def verify(deck_md: str, source_md: str | None, page_html: str) -> dict:
    """All checks for one deck. `source_md` is None when the deck names no source."""
    meta = frontmatter(deck_md)
    omit, rename, attribution = meta.get("omit") or [], meta.get("rename") or {}, meta.get("attribution") or {}
    report = {"misplaced": misplaced_blocks(deck_md, page_html, attribution) if _md_slides(deck_md) else [],
              "missing": [], "stale_omit": [], "omitted": omit, "renamed": rename}
    if source_md is not None:
        _, report["stale_omit"] = expected_units(source_md, omit, rename, attribution)
        report["missing"] = missing_units(source_md, page_html, omit, rename, attribution)
    report["ok"] = not (report["misplaced"] or report["missing"] or report["stale_omit"])
    return report
