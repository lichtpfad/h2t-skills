# h2t-ops Changelog

## Unreleased

- fix(research): index and object JSON is written to a sibling temp file and moved into place
  with `os.replace`, so a crash or a second writer can no longer leave a short new version
  followed by the tail of the old one. Object files whose id holds a colon live in NTFS
  alternate streams on Windows and cannot be renamed into; those are still written in place
  (#494)

- fix(research): a corrupt index no longer blocks work. `crawl` and the other writers save the
  object, leave the unreadable index untouched and warn on stderr to run `rebuild-indexes`.
  `rebuild-indexes` regenerates an unreadable aliases index from objects instead of refusing;
  the old file is kept as `aliases.index.json.corrupt` because non-url alias rows cannot be
  derived from objects (#495)

- fix(gmail): `reply` no longer addresses the account owner when the owner wrote last. It took
  the newest message's From; a 2026-09-28 reply with delivery questions for an external partner
  went to the owner's own inbox and sat unnoticed for six days. The recipient now follows
  Gmail's Reply: own drafts are skipped, the owner's messages are known by the SENT label and
  every From seen on them (so a send-as alias counts), an incoming message is answered at its
  Reply-To, a newest own message answers its other To recipients, else the last other sender,
  and a thread of only own messages or a message without a sender fails loud. `reply` and `forward` print the
  resolved `to` in human and JSON output. `In-Reply-To` / `References` now carry the RFC 822
  Message-ID (plus the prior References chain) instead of the Gmail API id, which other mail
  clients could not thread. Cc of an own message is not added — Gmail's Reply does not either
  (#498)

- feat(research): four method references the skill was missing — how to judge a claim before
  it enters a report (logic traps, bias sweep, hidden assumptions, red flags), per-domain
  source tiers and anti-patterns, search expansion and citation chaining, and PICO/STEEP/
  PROFIT/CREAM query shaping. Extracted from a legacy multi-agent `/research` command that is
  being retired; its memory-fallback, self-fact-checking and vault-write parts were dropped
  as they contradict this skill's no-silent-fallback rule and evidence-grounded-synthesis
  (#481)

- fix(meetgeek): the missing-ffmpeg error named a Windows path inside `~/.h2t/venv`, a
  directory the installer never creates and which has no pip when it exists. It now names
  the package and `uv pip install` (#443)

- fix(research): the screenshot step no longer names `h2t-tools:screenshot`, a Windows-only
  skill hardcoded to `C:/dev/h2t-tools/.venv/Scripts/python.exe`. It points at a browser
  agent when one is installed and, when none is, says the capture is missing rather than
  substituting prose for it (#460)

- fix(notion): the markdown converter knew nine block shapes and four inline ones, and a link
  was in neither set — every form arrived with `href` null, which makes a page body built
  from markdown unnavigable. `- [ ] task` arrived as a bullet carrying the literal `[ ]`, and
  `_block_to_markdown` had no `to_do` branch, so a page with checkboxes read back as blank
  lines. Both sides of the seam are fixed together and the round trip is asserted (#465, #467)

- fix(notion): `parse_inline` is an ordered tokenizer rather than two passes. A URL inside
  code or bold is no longer linkified, a link label keeps its annotations, targets accept
  balanced parentheses, and a lone `*` or backtick survives instead of being dropped (#465)

- fix(gmail): `read` and `list` returned empty `To` and `Subject` for any draft this package
  composed. `email.message` stores a field name verbatim, so the raw MIME carries lowercase
  `to:` and `subject:` while Gmail returns each header in the case the sender wrote it.
  Headers are now read case-insensitively, which also recovers drafts already in the mailbox
  — fixing the writer alone would have left those unreadable (#468)

- fix(telegram): `mentions` failed with `SESSION_INCOMPATIBLE` on every chat id while
  `dialogs` and `messages` worked on the same session, so the remedy on offer was to delete a
  session file that was fine. It handed `--chat-id` straight to Telethon instead of resolving
  it through the candidate forms its sibling uses; an unresolvable peer now raises
  `PEER_UNRESOLVED` naming the peer, not an auth error naming the session (#466)

- fix(telegram): `list_messages` buffers rows per candidate. A candidate that yielded rows and
  then failed left them in the result, and the next candidate appended the same messages again
