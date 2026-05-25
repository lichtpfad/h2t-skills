# Telegram Send Command Design

**Date:** 2026-05-25  
**Issue:** `#181`  
**Status:** draft

## Goal

Add a minimal write surface to the Telegram connector:

```text
h2t-ops telegram send <entity> --message "text" [--file path]
```

This closes the biggest interactive gap in the otherwise read-only Telegram CLI
without turning the connector into a full workflow/coordinator layer.

## Scope

### In scope for v1

- send one text message to a resolved Telegram entity;
- accept message text either from:
  - `--message "..."`, or
  - `--file path` (UTF-8 text file);
- return a normal machine-readable envelope with the sent message id and target.

### Out of scope for v1

- media/file uploads as Telegram attachments;
- rich formatting controls;
- bulk send;
- scheduled send;
- workflow automation like digest/task/research delegation.

## CLI Shape

```text
h2t-ops telegram send <entity> --message "text" [--json] [--format human|md]
h2t-ops telegram send <entity> --file path/to/message.txt [--json] [--format human|md]
```

### Validation rules

- exactly one of `--message` or `--file` is required;
- empty text after load/strip is rejected with `UsageError`;
- `entity` is passed through the same resolution path already used by
  `telegram messages <entity>`.

## Architecture

This should stay a narrow connector-level capability:

- `telegram/commands.py` adds a `send` verb;
- `TelegramClientAdapter` gets `send_message(entity, text)`; it should reuse the
  existing lazy Telethon connection path and typed error handling;
- no new workflow module is introduced.

The command should behave like Gmail send: direct action, no extra coordinator
layer, no productized confirmation step.

## Output Contract

Success result shape:

```json
{
  "entity": "me",
  "message_id": 12345,
  "date": "2026-05-25T12:00:00+00:00",
  "text": "hello"
}
```

Human output can stay concise, for example:

```text
✓ Message sent (ID: 12345)
```

## Testing

### Unit tests

- parser registers `telegram send`;
- parser enforces `--message` xor `--file`;
- command dispatch forwards the resolved text to client;
- client method uses connected Telethon client and returns normalized result.

### Live smoke

Safe target for first smoke:

- `h2t-ops telegram send me --message "test"`

That keeps the first write-path test self-addressed and avoids accidental
delivery to third-party chats.

## Acceptance

`#181` is done when:

- `telegram send` exists in public CLI help;
- text can be provided from inline arg or UTF-8 file;
- JSON and human output are both valid;
- at least one safe live smoke to `me` passes.
