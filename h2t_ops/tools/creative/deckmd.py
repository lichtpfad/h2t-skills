"""Deck markdown -> deck recipe: the slides and block roles a reviewer reads become `blocks`.

The deck markdown is described in the deck skill (references/from-approved-text.md):

    ## Slide 2. Market                 one slide; `## Слайд N.` works too; `{.cover}` -> cover
    ::: kicker                         block role, up to the closing `:::`; a kicker that opens
                                       the slide stands above the headline, a later one in place
    1. Market — what is happening?
    :::
    ::: number 44% | 72%               figures after the role name, in order
    - Share of first visits: 44%.
    - Share of revenue: 72%.
    :::
    Plain paragraph.                   unmarked text -> `text`; a table -> `table`;
                                       `![alt](file)` -> `figure`; a list -> a bulleted list

Inside a role, paragraphs before a list are its label (`cards`, `steps`) or caption
(`number`); in `quote`, a line `«…» — CODE` is a quote whose caption is `attribution[CODE]`
and any other line is the group label. Text keeps the markdown inline marks `**`, `*`,
`[text](url)` as HTML; nothing else is rewritten, so `verify` finds the text unchanged.

Frontmatter keys copied into the recipe when present: profile, palette, lang, menu,
stylesheets; the title is `deck_title`, else the first `# ` heading.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from h2t_ops.tools.creative import fidelity

SLIDE = re.compile(r"^## (?:Слайд|Slide) \d+\.\s*(.+)$", flags=re.M)
ROLE = re.compile(r"^::: (\w+)[ \t]*(.*?)\n(.*?)^:::[ \t]*$", flags=re.M | re.S)
QUOTE = re.compile(r"((?:«.*»|“.*”))\s*—\s*([^\s;,]+)", flags=re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
RECIPE_KEYS = ("profile", "palette", "lang", "menu", "stylesheets")


def inline(text: str) -> str:
    """Markdown inline marks to HTML; the text itself is not touched."""
    out = html.escape(" ".join(text.split()), quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])", r"<em>\1</em>", out)


def _paragraphs(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip() and b.strip() != "---"]


def _label_items(text: str) -> tuple[list[str], list[str]]:
    label, items = [], []
    for block in _paragraphs(text):
        if block.startswith("- "):
            items += [inline(i) for i in re.split(r"^- ", block, flags=re.M) if i.strip()]
        else:
            label.append(inline(block))
    return label, items


def _card(item: str):
    # a short first sentence or «Label:» becomes the card title when text follows it
    m = re.match(r"(.+?[.:])\s+(.+)", item)
    if m and len(m.group(1)) <= 40 and len(item) > 70:
        return {"title": m.group(1), "text": m.group(2)}
    return item


def _table(block: str) -> dict:
    rows = [[inline(c) for c in r.strip().strip("|").split("|")]
            for r in block.splitlines() if not re.fullmatch(r"[\s|:-]+", r)]
    return {"role": "table", "header": rows[0], "rows": rows[1:]}


def _figure(alt: str, src: str, assets: list[Path]) -> dict:
    for d in assets:
        f = d / src
        if src.endswith(".svg") and f.is_file():
            svg = f.read_text(encoding="utf-8")
            return {"role": "figure", "svg": svg[svg.index("<svg"):]}
    return {"role": "figure", "src": src, "alt": alt}


def _role(role: str, arg: str, inner: str, attribution: dict) -> dict:
    if role in ("thesis", "conclusion", "note"):
        return {"role": role, "text": [inline(p) for p in _paragraphs(inner)]}
    label, items = _label_items(inner)
    if role in ("cards", "steps"):
        block = {"role": role, "items": [_card(i) for i in items] if role == "cards" else items}
        if label:
            block["label"] = " ".join(label)
        return block
    if role == "number":
        block = {"role": "number", "figures": [f.strip() for f in arg.split("|") if f.strip()]}
        if items:
            block["items"] = items
        else:
            block["text"] = " ".join(label)
        return block
    if role == "quote":
        block, quotes = {"role": "quote"}, []
        for p in _paragraphs(inner):
            m = QUOTE.fullmatch(" ".join(p.split()))
            if m:
                quotes.append({"text": inline(m.group(1)), "by": str(attribution.get(m.group(2), m.group(2)))})
            else:
                block["label"] = inline(p)
        block["quotes"] = quotes
        return block
    raise ValueError(f"Unknown block role in the deck markdown: '{role}'")


def _plain(chunk: str, assets: list[Path]) -> list[dict]:
    blocks = []
    for p in _paragraphs(chunk):
        img = IMAGE.fullmatch(p)
        if img:
            blocks.append(_figure(img.group(1), img.group(2), assets))
        elif p.startswith("|"):
            blocks.append(_table(p))
        elif p.startswith("- "):
            lis = "".join(f"<li>{inline(i)}</li>" for i in re.split(r"^- ", p, flags=re.M) if i.strip())
            blocks.append({"role": "html", "html": f"<ul>{lis}</ul>"})
        else:
            blocks.append({"role": "text", "text": inline(p)})
    return blocks


def _slide(title: str, chunk: str, attribution: dict, assets: list[Path]) -> dict:
    cover = bool(re.search(r"\{\.cover\}\s*$", title))
    title = re.sub(r"\s*\{\.[\w-]+\}\s*$", "", title).strip()
    content: dict = {"headline": inline(title)}
    blocks, pos = [], 0
    for m in ROLE.finditer(chunk):
        blocks += _plain(chunk[pos:m.start()], assets)
        if m.group(1) == "kicker" and not blocks:
            content.setdefault("kicker", []).extend(inline(p) for p in _paragraphs(m.group(3)))
        elif m.group(1) == "kicker":  # mid-slide: it labels what follows, so it stays in place
            lines = "".join(f"<p>{inline(p)}</p>" for p in _paragraphs(m.group(3)))
            blocks.append({"role": "html", "html": f'<div class="kicker">{lines}</div>'})
        else:
            blocks.append(_role(m.group(1), m.group(2), m.group(3), attribution))
        pos = m.end()
    blocks += _plain(chunk[pos:], assets)
    content["blocks"] = blocks
    return {"title": title, "layout": "cover" if cover else "title-body", "content": content}


def to_recipe(deck_md: str, assets: list[Path] | None = None) -> dict:
    """The deck recipe for `h2t-creative assemble`. `assets`: where `![…](file.svg)` is inlined from."""
    meta = fidelity.frontmatter(deck_md)
    body = deck_md.split("---\n", 2)[2] if deck_md.startswith("---\n") else deck_md
    parts = SLIDE.split(body)
    if len(parts) < 3:
        raise ValueError("No slides: the deck markdown needs `## Slide N. Title` headings")
    heading = re.search(r"^# (.+)$", parts[0], flags=re.M)
    recipe = {"type": "deck", "title": meta.get("deck_title") or (heading.group(1).strip() if heading else "Deck")}
    recipe.update({k: meta[k] for k in RECIPE_KEYS if k in meta})
    attribution = meta.get("attribution") or {}
    recipe["slides"] = [_slide(t, c, attribution, assets or []) for t, c in zip(parts[1::2], parts[2::2])]
    return recipe
