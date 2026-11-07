"""Deck markdown -> recipe: every role reaches its block, and the built deck passes verify."""

import pytest
import yaml

from h2t_ops.tools.creative import assembler as asm
from h2t_ops.tools.creative import cli, deckmd, fidelity

SOURCE = """---
title: approved
---
# Studio direction

## 1. Market

Question: what is already taken?

Everyone sells **optimisation** of the future.

- Spa — rest for an evening.
- Doctor. When something already hurts and a specialist has to look at it closely and explain what to do.
- Gym — effort and a plan.

- Try first.
- Talk to an expert.
- Choose a path.

[+ Data] Share of first visits: 44%. Share of revenue: 72%.

[+ Data] Bought on day one: 13 of 35.

[+ Client] They came without a problem: «Just to relax.» — I3; «I wanted to try.» — I4

| Rival | Frame |
|---|---|
| Northside | Sport |

Image: map.svg.

Conclusion: the everyday middle is free.

No data on prices yet.

Mission

«To widen what people can do for their health».
"""

DECK = """---
verbatim_source: approved.md
profile: h2t-default
lang: en
menu: numbers
omit:
  - text: "Image: map.svg."
    why: "internal path; the map is on the slide"
attribution:
  I3: "from an interview"
---
# Studio direction

## Slide 1. Studio direction {.cover}

## Slide 2. Market

::: kicker
1. Market

Question: what is already taken?
:::

::: thesis
Everyone sells **optimisation** of the future.
:::

::: cards
- Spa — rest for an evening.
- Doctor. When something already hurts and a specialist has to look at it closely and explain what to do.
- Gym — effort and a plan.
:::

::: steps
- Try first.
- Talk to an expert.
- Choose a path.
:::

---

## Slide 3. Figures

::: number 44% | 72%
- Share of first visits: 44%.
- Share of revenue: 72%.
:::

::: number 13 of 35
Bought on day one: 13 of 35.
:::

::: quote
They came without a problem:

«Just to relax.» — I3

«I wanted to try.» — I4
:::

| Rival | Frame |
|---|---|
| Northside | Sport |

![Map](map.svg)

::: conclusion
Conclusion: the everyday middle is free.
:::

::: note
No data on prices yet.
:::

## Slide 4. Mission

::: thesis
See [the site](https://example.org).
:::

::: kicker
Mission
:::

::: thesis
«To widen what people can do for their health».
:::
"""

SVG = '<?xml version="1.0"?>\n<svg viewBox="0 0 10 10"><text>map</text></svg>'


@pytest.fixture
def recipe(tmp_path):
    (tmp_path / "map.svg").write_text(SVG, encoding="utf-8")
    return deckmd.to_recipe(DECK, [tmp_path])


def _blocks(recipe, n):
    return recipe["slides"][n - 1]["content"]["blocks"]


def test_frontmatter_and_title(recipe):
    assert (recipe["type"], recipe["title"], recipe["profile"], recipe["lang"], recipe["menu"]) == (
        "deck", "Studio direction", "h2t-default", "en", "numbers")
    assert "omit" not in recipe and "verbatim_source" not in recipe


def test_cover_and_kicker_above_the_headline(recipe):
    cover, market = recipe["slides"][0], recipe["slides"][1]
    assert (cover["layout"], cover["title"]) == ("cover", "Studio direction")
    assert market["content"]["kicker"] == ["1. Market", "Question: what is already taken?"]


def test_roles_map_to_blocks(recipe):
    thesis, cards, steps = _blocks(recipe, 2)
    assert thesis == {"role": "thesis", "text": ["Everyone sells <strong>optimisation</strong> of the future."]}
    assert cards["items"][0] == "Spa — rest for an evening."
    assert cards["items"][1] == {"title": "Doctor.", "text": "When something already hurts and a specialist has to look at it closely and explain what to do."}
    assert steps == {"role": "steps", "items": ["Try first.", "Talk to an expert.", "Choose a path."]}
    two, one, quote, table, figure, conclusion, note = _blocks(recipe, 3)
    assert two == {"role": "number", "figures": ["44%", "72%"], "items": ["Share of first visits: 44%.", "Share of revenue: 72%."]}
    assert one == {"role": "number", "figures": ["13 of 35"], "text": "Bought on day one: 13 of 35."}
    assert quote["label"] == "They came without a problem:"
    assert quote["quotes"] == [{"text": "«Just to relax.»", "by": "from an interview"}, {"text": "«I wanted to try.»", "by": "I4"}]
    assert table == {"role": "table", "header": ["Rival", "Frame"], "rows": [["Northside", "Sport"]]}
    assert figure == {"role": "figure", "svg": '<svg viewBox="0 0 10 10"><text>map</text></svg>'}
    assert (conclusion["role"], note["role"]) == ("conclusion", "note")


def test_mid_slide_kicker_stays_in_place(recipe):
    first, kicker, second = _blocks(recipe, 4)
    assert first["text"] == ['See <a href="https://example.org">the site</a>.']
    assert kicker == {"role": "html", "html": '<div class="kicker"><p>Mission</p></div>'}
    assert "kicker" not in recipe["slides"][3]["content"]


def test_missing_image_stays_a_link():
    deck = "## Slide 1. S\n\n![Map](nowhere.svg)\n"
    assert deckmd.to_recipe(deck)["slides"][0]["content"]["blocks"] == [{"role": "figure", "src": "nowhere.svg", "alt": "Map"}]


def test_errors():
    with pytest.raises(ValueError, match="No slides"):
        deckmd.to_recipe("# Just a doc\n\nText.\n")
    with pytest.raises(ValueError, match="Unknown block role"):
        deckmd.to_recipe("## Slide 1. S\n\n::: banner\nx\n:::\n")


def test_built_deck_passes_verify(tmp_path, recipe):
    out = tmp_path / "out"
    asm.assemble_deck(recipe, asm.PROFILES_DIR / "h2t-default", out)
    page = (out / "index.html").read_text(encoding="utf-8")
    report = fidelity.verify(DECK, SOURCE, page)
    assert (report["missing"], report["misplaced"], report["stale_omit"], report["ok"]) == ([], [], [], True)
    assert page.index('<div class="kicker"><p>1. Market</p>') < page.index("Market</h1>")


def test_cli_recipe_writes_yaml(tmp_path, capsys):
    deck = tmp_path / "deck.md"
    deck.write_text(DECK, encoding="utf-8")
    (tmp_path / "map.svg").write_text(SVG, encoding="utf-8")
    out = tmp_path / "recipe.yaml"
    assert cli.main(["recipe", "--deck", str(deck), "--out", str(out), "--profile", "h2t-mono"]) == 0
    assert "4 slides" in capsys.readouterr().out
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["profile"] == "h2t-mono" and data["slides"][2]["content"]["blocks"][4]["role"] == "figure"
