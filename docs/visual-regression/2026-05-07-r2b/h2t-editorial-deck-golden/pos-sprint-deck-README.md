# deck — HTML Presentation Generator

Claude Code skill that generates single-file HTML presentations. Two visual styles. Zero dependencies. Works offline.

## Styles

### terminal

Dark background, monospace font, scanline overlay, green accent. Hacker/engineer aesthetic.

```
bg: #0d1117 | font: JetBrains Mono | accent: #55aa88
effects: scanlines, cursor blink, fade-up animation
```

### editorial

Light background, serif headings, book-like typography, warm tones. Magazine/journal aesthetic.

```
bg: #faf9f6 | font: Playfair Display + Inter | accent: #c45a3c
effects: subtle shadows, slide-in animation, thin rules
```

## Install

```bash
mkdir -p .claude/skills/deck
cp SKILL.md .claude/skills/deck/SKILL.md
```

Or clone this repo and copy:

```bash
git clone https://github.com/ai-mindset-org/pos-sprint.git
cp -r pos-sprint/skills/deck/.  .claude/skills/deck/
```

Claude Code picks up the skill automatically.

## Usage

Say to Claude Code:

```
make a presentation about [topic]
```

or

```
/deck
```

Claude Code will:
1. Ask which style (terminal / editorial)
2. Ask about the topic and slide plan
3. Generate a single `index.html` with everything inline

Open in browser — done:

```bash
open index.html
```

## Iterate

After generating, tell Claude Code what to change:

```
add a slide with a quote after slide 3
make two columns on slide 5
change the cards on slide 4 to show different content
add a code block example on slide 6
```

## Components

Both styles include these ready-to-use components:

| Component | What it does |
|-----------|-------------|
| `cards` | Grid of cards with title, description, tag |
| `code-block` | Code/terminal block with syntax coloring |
| `quote` | Blockquote with accent border |
| `split` | Two-column layout |
| `stat-row` | Large numbers with labels |
| `layers` | Ordered items with colored borders |

## Keyboard Navigation

| Key | Action |
|-----|--------|
| `→` / `Space` / `Enter` | next slide |
| `←` / `Backspace` | previous |
| `Home` / `End` | first / last |
| swipe | mobile navigation |

## Examples

See `examples/` folder:

- **`terminal-example.html`** — 7-slide presentation "Building Your Personal OS" in terminal style
- **`editorial-example.html`** — 7-slide presentation "The Art of Knowledge Management" in editorial style

Open them in a browser to see how each style looks.

## How It Works

The skill contains:
- Complete CSS design systems for both styles (palette, typography, effects)
- HTML component templates (cards, quotes, code blocks, etc.)
- JavaScript for navigation (keyboard + touch)
- Responsive breakpoints for mobile

Claude Code reads the skill and generates a complete `index.html` following the design system. Everything is inline — no build step, no npm, no frameworks.

## File Structure

```
.claude/skills/deck/
└── SKILL.md          ← the skill file (all design systems inside)
```

Generated output:

```
my-presentation/
└── index.html        ← single file, open in browser
```
