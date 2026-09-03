# h2t-ops Changelog

## Unreleased

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
