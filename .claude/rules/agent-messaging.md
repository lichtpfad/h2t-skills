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
