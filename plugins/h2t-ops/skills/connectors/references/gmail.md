# Gmail Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list recent messages | `h2t-ops gmail list --max 10 --json` |
| search mail | `h2t-ops gmail search "from:example@example.com newer_than:7d" --max 10 --json` |
| read message | `h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json` |
| list labels | `h2t-ops gmail labels --json` |
| create draft | `h2t-ops gmail draft person@example.com "Subject" "Body" --json` |
| send email | `h2t-ops gmail send person@example.com "Subject" "Body" --json` |
| modify labels | `h2t-ops gmail label MESSAGE_ID_FROM_SEARCH --add LabelName --json` |

## Safety

- List, search, read, and labels are read-only.
- Draft, send, and label modification require explicit user intent.
- Prefer draft over send when user intent is ambiguous.
- Do not include raw email bodies, addresses, or private snippets in GitHub issues.

## Commands

```bash
h2t-ops gmail list --max 10 --json
h2t-ops gmail search "subject:invoice newer_than:30d" --max 10 --json
h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json
h2t-ops gmail draft person@example.com "Follow-up" "Draft body" --json
```

## Auth

Gmail reuses Google OAuth credentials under `~/.config/google-calendar-mcp/` or `~/.config/gmail/`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Commands Reference (P0)

```bash
# Reply to a thread (draft by default)
h2t-ops gmail reply THREAD_ID --body "My reply" --json
# Reply and actually send (requires both flags)
h2t-ops gmail reply THREAD_ID --body "My reply" --send --confirm-send --json

# Forward a message (draft by default)
h2t-ops gmail forward MESSAGE_ID --to recipient@example.com --json
# Forward and actually send (requires both flags)
h2t-ops gmail forward MESSAGE_ID --to recipient@example.com --send --confirm-send --json

# Create a label
h2t-ops gmail label-create "Project X" --json

# Delete a label (requires exact name match guard)
h2t-ops gmail label-delete LABEL_ID --confirm-name "Project X" --json
```

## Safety (P0 additions)

- `reply` and `forward` always default to draft — real send requires both `--send` AND `--confirm-send`.
- `label-delete` requires `--confirm-name` with the exact label name (case-insensitive match).

## Manual E2E Smoke Recipe

> Automated live E2E never sends real messages. All commands default to draft.
> Real send requires both `--send` and `--confirm-send`.
> Run only with `$env:H2T_E2E_CONNECTORS="1"`.

### Draft smoke (safe, no real send)

```python
import subprocess, sys

to_addr = "your-test-address@example.com"

# Step 1: Create a seed draft
result = subprocess.run([sys.executable, "-m", "h2t_ops.cli",
    "gmail", "send", to_addr, "h2t-e2e-connector-api-gmail",
    "--body", "seed", "--draft", "--json"],
    capture_output=True, text=True, check=True)
import json
seed = json.loads(result.stdout)
# Note: draft id is seed["id"], but no thread_id exposed via send draft — use gmail search

# Step 2: Search for the draft to get thread_id
search_result = subprocess.run([sys.executable, "-m", "h2t_ops.cli",
    "gmail", "search", "subject:h2t-e2e-connector-api-gmail", "--max", "1", "--json"],
    capture_output=True, text=True, check=True)
msgs = json.loads(search_result.stdout)
thread_id = msgs[0]["threadId"] if msgs else None

# Step 3: Reply as draft (no real send)
if thread_id:
    result2 = subprocess.run([sys.executable, "-m", "h2t_ops.cli",
        "gmail", "reply", thread_id, "--body", "reply draft", "--json"],
        capture_output=True, text=True, check=True)
    reply = json.loads(result2.stdout)
    assert reply.get("draft") is True

# Cleanup: Delete drafts manually from Gmail Drafts folder.
```

## Common Failures

- Missing OAuth token: run Google OAuth setup.
- Expired token: refresh OAuth through the configured Google auth flow.
- Write command ambiguity: create a draft unless the user explicitly says send.
