# Agent Messaging Rules

## A send receipt is not delivery

`murmur_send` returns `status: "queued"`. That means the local daemon accepted the message
into its outbox. It does not mean the peer's daemon received it, and it does not mean the
agent read it. Treat a task as delivered only when the peer answers on its substance.

Measured 2026-08-27: three task messages returned `queued` and none arrived. The cause is
one line in the daemon:

```js
// scripts/murmur-daemon.mjs:49
const jetstreamEnabled = jetstreamConfig.enabled ?? process.env.MURMUR_JETSTREAM === "1";
```

JetStream is off unless configured, so the channel is core NATS pub/sub with no
persistence. A message published while the peer has no live subscription does not exist:
it is not queued on the server, it cannot be replayed, and there is nothing to collect
later. The publisher sees success either way.

The peer had already written this distinction down a day earlier — "acked means the daemon
accepted and settled the outbox, it is NOT the agent reading it" — and it was still read as
delivery three times running.

## Working rule until persistence is on

- Confirm important work by a reply about its content, never by a transport status.
- Silence beyond ~30 minutes on something that needs an answer is a reason to resend.
- Resend as a **new** message. Re-issuing the same `msgId` is rejected by the peer's dedupe.
- Ask for an explicit one-line receipt when the message carries an instruction the peer
  must act on, and stop sending until it arrives — repeated blind sends multiply noise
  without changing the odds.

## Diagnose the transport, not the addressing

Silence invites a plausible story about topics, conversation ids or filters. Those are
usually unverifiable from this side. The daemon's source and its startup log are here and
can be read: check `jetstreamEnabled`, the daemon's start time against the send time, and
whether any conversation shows traffic in that window. Prefer the check you can run over
the explanation you can only assert.

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
