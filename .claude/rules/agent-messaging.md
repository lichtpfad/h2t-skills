# Agent Messaging Rules

## Murmur transport, delivery and wake: see the owner rule

How Murmur delivers, persists and wakes sessions is not specific to this repository, so it
lives in one place every session on every machine reads:
`~/.h2t/config/rules/agent-messaging.md` (indexed in `~/.h2t/config/rules/index.md`).

It replaced a section here that said persistence was off. Measured 2026-11-16, JetStream is
on with a durable consumer on both stas-mac and stas-automata. Quote neither file from
memory: re-read `agent-config.json` and the daemon start log first.

## A diagnosis that travels becomes an instruction, and loses its evidence

A peer reports what they saw and why they think it happens. By the time the report has
crossed one or two hands, the observation and the explanation are one sentence, and the
explanation is what arrives as the thing to do.

Measured 2026-08-27. The peer observed a bare `/session-start` in the command menu,
concluded "Claude Code does not namespace plugin skills; the driver is `name:` in
SKILL.md", and the operator relayed the remedy: restore `name: h2t-core:*` to the three
session skills, bump, ship.

Three checks, each one command, said the opposite:

- `tests/core/test_skill_frontmatter.py` fails on exactly that change, with the text
  `renders as /h2t-core:h2t-core:session-start`.
- #358 (bf66819) had already fixed the mirror-image complaint — the menu offering
  `/h2t-core:h2t-core:handoff` and 32 more — by removing the prefix from frontmatter.
  Applying the remedy would have been a knowing return to the state that issue left.
- In the session doing the work: every `name:` bare on disk, every skill namespaced in
  the listing. The harness prepends. The premise was false where it mattered.

The observation was real. What did not survive the trip was everything needed to test
the explanation. Both replacement explanations offered from this side were wrong too — a
stale `h2t` plugin cache, and leftover bare skills in `~/.claude/skills/` — and the peer
refuted both by looking, which is the point: the machine that can answer is the machine
that saw it.

The actual cause was neither. Claude Code 2.1.160 renders a plugin skill in the command
menu as its short name with the plugin in parentheses. Nothing was broken; a display
format was read as a defect, and the reading travelled further than the display did.

So: **act on the observation, verify the explanation.** Ask for what was typed, what
happened, and what was expected — the peer asked the operator for exactly that shape
earlier the same day and was right to. And when a remedy contradicts a deliberate
decision in this repository, find that decision and read it before overriding it; both
directions of this particular change have now been shipped once each.
