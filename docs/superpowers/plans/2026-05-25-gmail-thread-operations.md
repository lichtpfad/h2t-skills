---
title: "Gmail Thread Operations Implementation Plan"
status: "draft"
date: "2026-05-25"
milestone: ""
---
# Gmail Thread Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the real public CLI gap behind `#172` by adding thread-level read/list operations and exposing reply-in-thread flags on `gmail send`.

**Architecture:** Keep this as a narrow public-surface patch. `GmailClient` already knows how to send with `thread_id` and reply headers; the missing work is to add thread read/list methods, expose them via `gmail threads`, `gmail thread <id>`, and surface `--thread-id` / `--reply-to` on `gmail send` without changing existing message parsing behavior.

**Tech Stack:** Python, argparse, Gmail REST via existing `GmailClient`, pytest.

---

## File Map

- Modify: `h2t_ops/connectors/gmail/client.py`
  - Add thread-level list/get helpers that reuse existing message parsing.
- Modify: `h2t_ops/connectors/gmail/commands.py`
  - Register `threads` and `thread` verbs.
  - Expose `--thread-id` and `--reply-to` on `gmail send`.
- Modify: `tests/connectors/gmail/test_client.py`
  - Add client coverage for thread listing/get and send path thread forwarding.
- Modify: `tests/connectors/gmail/test_commands.py`
  - Add parser/dispatch coverage for the new public CLI surface.

### Task 1: Expose reply-in-thread on `gmail send`

**Files:**
- Modify: `h2t_ops/connectors/gmail/commands.py`
- Test: `tests/connectors/gmail/test_commands.py`

- [ ] **Step 1: Write the failing command-surface tests**

```python
def test_register_adds_send_thread_flags():
    ns = _parser().parse_args([
        "gmail", "send", "a@example.com", "Subject",
        "--thread-id", "T1", "--reply-to", "<mid@x>",
    ])
    assert ns.thread_id == "T1"
    assert ns.reply_to == "<mid@x>"


def test_send_dispatch_forwards_thread_flags(monkeypatch):
    calls = {}

    class _Stub:
        def send_message(self, **kwargs):
            calls.update(kwargs)
            return {"id": "m1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(
        gmail_cmd="send",
        to="a@example.com",
        subject="Subject",
        body="Body",
        file=None,
        attach=None,
        draft=False,
        thread_id="T1",
        reply_to="<mid@x>",
        as_json=True,
        fmt="human",
    ))
    assert out == {"id": "m1", "draft": False}
    assert calls["thread_id"] == "T1"
    assert calls["reply_to_message_id"] == "<mid@x>"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv.exe run pytest tests/connectors/gmail/test_commands.py -k "thread_flags" -q`

Expected: parser rejects flags or dispatch omits them.

- [ ] **Step 3: Add the flags and forward them**

```python
snp = cmds.add_parser("send", help="Send a message")
snp.add_argument("to"); snp.add_argument("subject"); snp.add_argument("body", nargs="?")
snp.add_argument("--file"); snp.add_argument("--attach", nargs="+")
snp.add_argument("--thread-id", dest="thread_id")
snp.add_argument("--reply-to", dest="reply_to")
snp.add_argument("--draft", action="store_true"); add_fmt(snp)
```

```python
result = client.send_message(
    to=args.to,
    subject=args.subject,
    body=body,
    attachments=args.attach,
    as_draft=as_draft,
    thread_id=getattr(args, "thread_id", None),
    reply_to_message_id=getattr(args, "reply_to", None),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv.exe run pytest tests/connectors/gmail/test_commands.py -k "thread_flags" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/commands.py tests/connectors/gmail/test_commands.py
git commit -m "feat(gmail): expose reply-in-thread send flags"
```

### Task 2: Add thread-level client methods

**Files:**
- Modify: `h2t_ops/connectors/gmail/client.py`
- Test: `tests/connectors/gmail/test_client.py`

- [ ] **Step 1: Write failing client tests for thread list/get**

```python
def test_get_thread_returns_parsed_messages():
    payload = {
        "id": "thr1",
        "messages": [
            {
                "id": "m1",
                "threadId": "thr1",
                "labelIds": [],
                "snippet": "hello",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@example.com"},
                        {"name": "To", "value": "b@example.com"},
                        {"name": "Subject", "value": "Subject"},
                        {"name": "Date", "value": "Tue"},
                    ],
                    "body": {"data": "Qm9keQ=="},
                },
            }
        ],
    }
    class _Svc(_FakeService):
        def threads(self): return self
        def get(self, **kwargs): return _Exec(payload)

    c, _ = _client_with(_Svc())
    out = c.get_thread("thr1")
    assert out["id"] == "thr1"
    assert out["messages"][0]["id"] == "m1"
    assert out["messages"][0]["body"] == "Body"


def test_list_threads_returns_thread_summaries():
    class _Svc(_FakeService):
        def threads(self): return self
        def list(self, **kwargs):
            return _Exec({"threads": [{"id": "thr1"}]})
        def get(self, **kwargs):
            return _Exec({"id": "thr1", "messages": []})

    c, _ = _client_with(_Svc())
    out = c.list_threads(max_results=5, query="label:inbox")
    assert out == [{"id": "thr1", "messages": []}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv.exe run pytest tests/connectors/gmail/test_client.py -k "thread" -q`

Expected: `AttributeError` / missing methods.

- [ ] **Step 3: Add minimal thread methods**

```python
def get_thread(self, thread_id: str) -> Dict[str, Any]:
    try:
        thread = self.service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        return {
            "id": thread["id"],
            "messages": [self._parse_message(msg) for msg in thread.get("messages", [])],
        }
    except HttpError as e:
        raise _map_http_error(e, op=f"get thread {thread_id}") from e


def list_threads(
    self,
    max_results: int = 10,
    query: Optional[str] = None,
    unread_only: bool = False,
) -> List[Dict[str, Any]]:
    try:
        if unread_only and query:
            query = f"is:unread {query}"
        elif unread_only:
            query = "is:unread"
        results = self.service.users().threads().list(
            userId="me", maxResults=max_results, q=query
        ).execute()
        threads = results.get("threads", [])
        return [self.get_thread(row["id"]) for row in threads]
    except HttpError as e:
        raise _map_http_error(e, op="list threads") from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv.exe run pytest tests/connectors/gmail/test_client.py -k "thread" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/client.py tests/connectors/gmail/test_client.py
git commit -m "feat(gmail): add thread-level client operations"
```

### Task 3: Add `gmail threads` and `gmail thread <id>` CLI verbs

**Files:**
- Modify: `h2t_ops/connectors/gmail/commands.py`
- Test: `tests/connectors/gmail/test_commands.py`

- [ ] **Step 1: Write failing parser/dispatch tests**

```python
def test_register_adds_thread_subcommands():
    parser = _parser()
    assert parser.parse_args(["gmail", "threads", "--max", "5"]).gmail_cmd == "threads"
    assert parser.parse_args(["gmail", "thread", "thr1"]).gmail_cmd == "thread"


def test_threads_json_returns_raw(monkeypatch):
    class _Stub:
        def list_threads(self, **kwargs):
            return [{"id": "thr1", "messages": []}]

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="threads", max=5, unread=False, query=None, as_json=True, fmt="human"))
    assert out == [{"id": "thr1", "messages": []}]


def test_thread_human_returns_summary(monkeypatch):
    class _Stub:
        def get_thread(self, thread_id):
            return {"id": thread_id, "messages": [{"id": "m1", "subject": "S", "from": "f", "date": "d", "body": "B"}]}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="thread", thread_id="thr1", as_json=False, fmt="human"))
    assert "thr1" in out and "m1" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv.exe run pytest tests/connectors/gmail/test_commands.py -k "threads or thread_human" -q`

Expected: parser rejects verbs or dispatch raises unknown subcommand.

- [ ] **Step 3: Add the verbs with minimal human formatter**

```python
tp = cmds.add_parser("threads", help="List threads")
tp.add_argument("--max", type=int, default=10)
tp.add_argument("--unread", action="store_true")
tp.add_argument("--query", default=None); add_fmt(tp)

thp = cmds.add_parser("thread", help="Read a thread")
thp.add_argument("thread_id"); add_fmt(thp)
```

```python
def format_thread_detail(thread: Dict[str, Any]) -> str:
    lines = [f"# Thread {thread['id']}", ""]
    for msg in thread.get("messages", []):
        lines.extend([
            f"## {msg.get('subject', '')}",
            f"From: {msg.get('from', '')}",
            f"Date: {msg.get('date', '')}",
            f"Message ID: `{msg.get('id', '')}`",
            "",
            msg.get("body", ""),
            "",
        ])
    return "\n".join(lines).strip()
```

```python
if cmd == "threads":
    rows = client.list_threads(max_results=args.max, query=args.query, unread_only=args.unread)
    return rows if _fmt(args) == "json" else format_thread_list(rows)
if cmd == "thread":
    row = client.get_thread(args.thread_id)
    return row if _fmt(args) == "json" else format_thread_detail(row)
```

- [ ] **Step 4: Run the focused and full Gmail suites**

Run: `uv.exe run pytest tests/connectors/gmail/test_commands.py tests/connectors/gmail/test_client.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/commands.py h2t_ops/connectors/gmail/client.py tests/connectors/gmail/test_commands.py tests/connectors/gmail/test_client.py
git commit -m "feat(gmail): add thread cli surface"
```

## Self-Review

- Spec coverage: this plan covers the narrowed real gap behind `#172`: public `send` thread flags, thread list, and thread get. It intentionally does not introduce attachment download or trash/delete because those belong to `#173/#174`.
- Placeholder scan: no TBD/TODO placeholders left; every task points to exact files and commands.
- Type consistency: use `thread_id` in argparse and `reply_to_message_id` only at client call boundary, matching the existing `send_message(...)` signature.
