# A deck from approved text

Read this when the deck is built from a document the user has already approved. The text
is **content** and stays word for word. Everything else is **layout**, and layout is yours:
where a slide ends, what role a fragment plays on it, the order on a slide, the visual form
of a number. Shortening, rewording, merging paragraphs, inventing lead-ins, dropping a
section or a table are content changes and are not yours to make.

This exists because it went wrong: an agent cut or reworded 26 paragraphs of an approved
document while "fitting one idea per slide" and said so only after the deck was built; it
took three rebuilds to get the text back (#599).

## The deck markdown

Write the deck as markdown first, then build the recipe from it. The markdown is what the
user reviews and what `h2t-creative verify` reads.

```markdown
---
verbatim_source: docs/approved.md
omit:                       # fragments decided not to show — each needs the owner's yes
  - text: "Image: path/to/file.svg."
    why: "internal path; the image itself is on the slide"
rename:                     # headings the owner renamed, old: new
  "Why the usual options fail": "Missing Piece"
attribution:                # quote code in the source -> caption on the slide
  I3: "from a client interview"
---

## Slide 1. Title {.cover}

## Slide 2. Market

::: kicker
1. Market — what is happening?
:::

::: thesis
The one sentence this slide exists to say.
:::

Supporting paragraph, unchanged.
```

`## Slide N.` (or `## Слайд N.`) starts a slide; `{.cover}` after its title makes it the
cover. `::: role` … `:::` marks a block's role; `verify` ignores the markup lines and checks
the text inside. `h2t-creative recipe --deck deck.md --out recipe.yaml` turns this into the
recipe: each slide one recipe slide, each marked block one entry of its `blocks` (SKILL.md,
"Blocks"), unmarked text a `text` block, a table a `table`, an image a `figure`. A
`::: kicker` that opens the slide stands above the headline; one later on stays where it is.
Figures go after the role name, in order: `::: number 44% | 72%`. In `::: quote`, a line
`«…» — I3` is a quote captioned with `attribution[I3]`, any other line the group label.
`profile`, `palette`, `lang`, `menu`, `stylesheets` and `deck_title` in the frontmatter
carry into the recipe.

## Splitting the text into blocks

Two passes. The first is mechanical and follows from the text itself; the second is a
judgment, made against a control question and shown to the user in the deck markdown.

**Pass 1 — by what the text already marks**

| In the approved text | Role |
|---|---|
| A numbered section heading, its question line | `kicker`, first on its slide |
| A paragraph the source opens as a conclusion ("Conclusion:", «Вывод:») | `conclusion` |
| A quote with its code («…» — I3) | `quote`; a lead-in before quotes is the group caption |
| A sentence with a figure | `number`: the figure large, **exactly as written**, the sentence as its caption |
| A caveat about the data, a source line | `note` |
| A table | the table as it is |
| A list whose order matters (first, then, stages) | `steps` |
| A list of parallel items | `cards` |

**Pass 2 — by meaning**

| Role | Control question | Limit |
|---|---|---|
| `thesis` | If one sentence stayed on the slide, which one? | One per slide, a whole sentence |
| plain paragraph | Does it explain the thesis rather than claim something new? | A new claim is a new slide |
| `cards` vs paragraph | Can the items be reordered without loss? | If not: `steps` or a paragraph |
| emphasis (bold) | Which sentence carries the paragraph? | Never yours to set — see below |

**Order on a slide:** kicker → thesis → support (cards, numbers, table, paragraph) → proof
(quote) → conclusion / note. A kicker in the middle of a slide means a second block started
there: give it its own slide.

## Emphasis: propose, the user chooses

Bold decides what the paragraph is about, and that is the author's decision. Do not write
`**` into the deck text unless the approved text has it. Offer one to three candidate
sentences per explanatory paragraph, each verbatim from that paragraph, and let the user
pick one or none. A thesis, a figure or a quote needs no bold: its role already sets it apart.

## Before building

- **Slide budget.** Agree on a rough slide count before laying out; a split that is faithful
  but twice too long is still a rebuild.
- **Cuts.** If the text does not fit, list the proposed `omit` entries and wait for an
  explicit yes. Never cut silently, never report cuts after the build.
- An ambiguous reference from the user ("5 and 6", "those points") is clarified in one line,
  not guessed.

## After building

```bash
h2t-creative verify --deck deck.md --page dist/index.html --json
```

It prints every `omit` and `rename` so the decisions stay visible, and exits 1 when a
fragment of the source is missing from the page word for word, when a block landed on the
wrong slide, or when an `omit` entry no longer exists in the source. Fix the deck markdown
and rebuild; do not deliver on a non-zero exit. A one-word table cell counts as present if
the same word stands anywhere on the page — check short cells by eye.
