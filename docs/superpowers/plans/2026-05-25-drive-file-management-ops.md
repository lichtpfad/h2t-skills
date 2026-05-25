---
title: "Drive File Management Ops Implementation Plan"
status: "draft"
date: "2026-05-25"
milestone: ""
---
# Drive File Management Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe public CLI support for Drive file rename, copy, and move operations in `h2t-ops`.

**Architecture:** Extend the existing `DriveClient` with three focused write operations: `rename_file`, `copy_file`, and `move_file`. Keep the CLI surface in `h2t_ops/connectors/drive/commands.py`, reuse the repo’s typed error conventions from `h2t_ops.core.errors`, and validate destination folder MIME before mutating parent links.

**Tech Stack:** Python, Google Drive API v3, `pytest`, existing `h2t-ops` CLI/output envelope conventions.

---

## File Structure

- Modify: `h2t_ops/connectors/drive/client.py`
  - Add `rename_file(...)`
  - Add `copy_file(...)`
  - Add `move_file(...)`
  - Reuse `_resolve_folder_id(...)`
  - Add a tiny internal metadata helper only if needed for parent validation
- Modify: `h2t_ops/connectors/drive/commands.py`
  - Register `rename`, `copy`, `move`
  - Dispatch each verb to `DriveClient`
- Modify: `tests/connectors/drive/test_client.py`
  - Add focused unit tests for request shape, MIME validation, and parent replacement semantics
- Modify: `tests/connectors/drive/test_commands.py`
  - Add parser/help/dispatch coverage for the new verbs

## Acceptance Rules

- Public CLI must exist:
  - `h2t-ops drive rename <file-id> <new-name>`
  - `h2t-ops drive copy <file-id> [--name <new-name>] [--folder <folder-id>]`
  - `h2t-ops drive move <file-id> --to <folder-id>`
- All commands must support `--json`
- All write paths must use `supportsAllDrives=True`
- `copy` and `move` must define `root` behavior explicitly instead of emitting invalid parent IDs
- `move` must explicitly validate that the destination is a folder
- `move` must replace old parent links rather than silently adding an extra parent
- Issue `#179` does **not** close until tests are green **and** safe live smoke passes

---

### Task 1: Add CLI parser and dispatch surface

**Files:**
- Modify: `h2t_ops/connectors/drive/commands.py`
- Test: `tests/connectors/drive/test_commands.py`

- [ ] **Step 1: Write the failing parser/dispatch tests**

Add these tests to `tests/connectors/drive/test_commands.py`:

```python
def test_register_creates_subparsers_for_drive_verbs():
    parser = _build_parser()
    cases = [
        ("rename", ["file1", "renamed.txt"]),
        ("copy", ["file1"]),
        ("move", ["file1", "--to", "folder1"]),
    ]
    for cmd, extra in cases:
        ns = parser.parse_args(["drive", cmd, *extra])
        assert ns.drive_cmd == cmd


def test_rename_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def rename_file(self, file_id, new_name):
            return {
                "file_id": file_id,
                "name": new_name,
                "mimeType": "text/plain",
                "web_view_link": "https://drive/file1",
                "modifiedTime": "2026-05-25T18:00:00Z",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="rename",
        file_id="file1",
        new_name="renamed.txt",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["name"] == "renamed.txt"


def test_copy_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def copy_file(self, file_id, *, new_name=None, folder=None):
            return {
                "file_id": "copy1",
                "source_file_id": file_id,
                "name": new_name or "Copy of file",
                "parents": [folder] if folder else [],
                "mimeType": "text/plain",
                "web_view_link": "https://drive/copy1",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="copy",
        file_id="file1",
        new_name="copy.txt",
        folder="folder1",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["file_id"] == "copy1"
    assert out["result"]["parents"] == ["folder1"]


def test_move_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def move_file(self, file_id, *, destination_folder_id):
            return {
                "file_id": file_id,
                "name": "report.txt",
                "parents": [destination_folder_id],
                "mimeType": "text/plain",
                "web_view_link": "https://drive/file1",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="move",
        file_id="file1",
        destination_folder_id="folder1",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["parents"] == ["folder1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_commands.py -q
```

Expected: FAIL with missing `rename`, `copy`, `move` parser or dispatch branches.

- [ ] **Step 3: Add minimal CLI parser surface**

Patch `h2t_ops/connectors/drive/commands.py` by adding new subcommands near `create-folder` / `docs-tab`:

```python
    rp = cmds.add_parser("rename", help="Rename a Drive file in place")
    rp.add_argument("file_id")
    rp.add_argument("new_name")
    add_fmt(rp)

    cp = cmds.add_parser("copy", help="Copy a Drive file")
    cp.add_argument("file_id")
    cp.add_argument("--name", dest="new_name")
    cp.add_argument("--folder")
    add_fmt(cp)

    mp = cmds.add_parser("move", help="Move a Drive file to another folder")
    mp.add_argument("file_id")
    mp.add_argument("--to", dest="destination_folder_id", required=True)
    add_fmt(mp)
```

And in `run(args)`:

```python
    if cmd == "rename":
        return client.rename_file(args.file_id, args.new_name)
    if cmd == "copy":
        return client.copy_file(
            args.file_id,
            new_name=args.new_name,
            folder=args.folder,
        )
    if cmd == "move":
        return client.move_file(
            args.file_id,
            destination_folder_id=args.destination_folder_id,
        )
```

- [ ] **Step 4: Run tests to verify parser/dispatch pass**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_commands.py -q
```

Expected: parser/dispatch tests for the new verbs PASS; client-level tests may still fail later because methods do not yet exist.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/drive/commands.py tests/connectors/drive/test_commands.py
git commit -m "feat(drive): add file management cli verbs"
```

---

### Task 2: Implement `rename_file`

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py`
- Test: `tests/connectors/drive/test_client.py`

- [ ] **Step 1: Write the failing `rename_file` tests**

Add these tests to `tests/connectors/drive/test_client.py`:

```python
def test_rename_file_updates_name_and_returns_metadata(client_obj):
    files = client_obj.service.files.return_value
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "renamed.txt",
        "mimeType": "text/plain",
        "webViewLink": "https://drive/file1",
        "modifiedTime": "2026-05-25T18:00:00Z",
    }

    result = client_obj.rename_file("file1", "renamed.txt")

    assert result["file_id"] == "file1"
    assert result["name"] == "renamed.txt"
    assert files.update.call_args.kwargs["fileId"] == "file1"
    assert files.update.call_args.kwargs["body"] == {"name": "renamed.txt"}
    assert files.update.call_args.kwargs["supportsAllDrives"] is True


def test_rename_file_requires_non_empty_name(client_obj):
    with pytest.raises(UsageError):
        client_obj.rename_file("file1", "   ")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: FAIL with `AttributeError: 'DriveClient' object has no attribute 'rename_file'`.

- [ ] **Step 3: Write minimal implementation**

Add this method to `h2t_ops/connectors/drive/client.py` near `create_folder(...)`:

```python
    def rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
        if not new_name or not new_name.strip():
            raise UsageError("drive rename: new name is required")
        try:
            res = self.service.files().update(
                fileId=file_id,
                body={"name": new_name.strip()},
                fields="id, name, mimeType, webViewLink, modifiedTime",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", file_id),
                "name": res.get("name", new_name.strip()),
                "mimeType": res.get("mimeType", ""),
                "web_view_link": res.get("webViewLink", ""),
                "modifiedTime": res.get("modifiedTime", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"rename file {file_id}") from e
```

- [ ] **Step 4: Run tests to verify `rename_file` passes**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: new rename tests PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/drive/client.py tests/connectors/drive/test_client.py
git commit -m "feat(drive): add rename file operation"
```

---

### Task 3: Implement `copy_file`

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py`
- Test: `tests/connectors/drive/test_client.py`

- [ ] **Step 1: Write the failing `copy_file` tests**

Add these tests to `tests/connectors/drive/test_client.py`:

```python
def test_copy_file_without_folder_copies_in_place(client_obj):
    files = client_obj.service.files.return_value
    files.copy.return_value.execute.return_value = {
        "id": "copy1",
        "name": "Copy of report.txt",
        "mimeType": "text/plain",
        "parents": ["parent1"],
        "webViewLink": "https://drive/copy1",
    }

    result = client_obj.copy_file("file1")

    assert result["file_id"] == "copy1"
    assert result["source_file_id"] == "file1"
    assert files.copy.call_args.kwargs["fileId"] == "file1"
    assert files.copy.call_args.kwargs["supportsAllDrives"] is True


def test_copy_file_with_name_and_folder_sets_body(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder1", "Target", False))
    files.copy.return_value.execute.return_value = {
        "id": "copy1",
        "name": "copy.txt",
        "mimeType": "text/plain",
        "parents": ["folder1"],
        "webViewLink": "https://drive/copy1",
    }

    result = client_obj.copy_file("file1", new_name="copy.txt", folder="Target")

    assert result["parents"] == ["folder1"]
    assert files.copy.call_args.kwargs["body"] == {
        "name": "copy.txt",
        "parents": ["folder1"],
    }


def test_copy_file_to_root_sets_explicit_root_parent(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: (None, "root", False))
    files.copy.return_value.execute.return_value = {
        "id": "copy-root",
        "name": "copy.txt",
        "mimeType": "text/plain",
        "parents": [],
        "webViewLink": "https://drive/copy-root",
    }

    client_obj.copy_file("file1", new_name="copy.txt", folder="root")

    assert files.copy.call_args.kwargs["body"] == {
        "name": "copy.txt",
        "parents": ["root"],
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: FAIL with missing `copy_file`.

- [ ] **Step 3: Write minimal implementation**

Add this method to `h2t_ops/connectors/drive/client.py` after `rename_file(...)`:

```python
    def copy_file(
        self,
        file_id: str,
        *,
        new_name: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            body: Dict[str, Any] = {}
            if new_name and new_name.strip():
                body["name"] = new_name.strip()
            if folder:
                folder_id, _, _ = self._resolve_folder_id(folder)
                body["parents"] = ["root"] if not folder_id else [folder_id]
            res = self.service.files().copy(
                fileId=file_id,
                body=body,
                fields="id, name, mimeType, parents, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", ""),
                "source_file_id": file_id,
                "name": res.get("name", ""),
                "mimeType": res.get("mimeType", ""),
                "parents": res.get("parents", []),
                "web_view_link": res.get("webViewLink", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"copy file {file_id}") from e
```

- [ ] **Step 4: Run tests to verify `copy_file` passes**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: new copy tests PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/drive/client.py tests/connectors/drive/test_client.py
git commit -m "feat(drive): add copy file operation"
```

---

### Task 4: Implement `move_file`

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py`
- Test: `tests/connectors/drive/test_client.py`

- [ ] **Step 1: Write the failing `move_file` tests**

Add these tests to `tests/connectors/drive/test_client.py`:

```python
def test_move_file_replaces_existing_parents(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder2", "Archive", False))
    files.get.return_value.execute.side_effect = [
        {
            "id": "folder2",
            "name": "Archive",
            "mimeType": "application/vnd.google-apps.folder",
        },
        {
            "id": "file1",
            "name": "report.txt",
            "mimeType": "text/plain",
            "parents": ["parent1", "parentA"],
        },
    ]
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": ["folder2"],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id="Archive")

    assert result["parents"] == ["folder2"]
    assert files.update.call_args.kwargs["addParents"] == "folder2"
    assert files.update.call_args.kwargs["removeParents"] == "parent1,parentA"
    assert files.update.call_args.kwargs["supportsAllDrives"] is True


def test_move_file_requires_destination_to_be_folder(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("file-as-dest", "Bad", False))
    files.get.return_value.execute.return_value = {
        "id": "file-as-dest",
        "name": "Bad",
        "mimeType": "text/plain",
    }

    with pytest.raises(UsageError):
        client_obj.move_file("file1", destination_folder_id="Bad")


def test_move_file_to_root_skips_folder_validation_fetch(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: (None, "root", False))
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": ["parent1"],
    }
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": [],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id="root")

    assert result["parents"] == []
    assert files.update.call_args.kwargs["addParents"] == "root"
    assert files.update.call_args.kwargs["removeParents"] == "parent1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: FAIL with missing `move_file`.

- [ ] **Step 3: Write minimal implementation**

Add this method to `h2t_ops/connectors/drive/client.py` after `copy_file(...)`:

```python
    def move_file(self, file_id: str, *, destination_folder_id: str) -> Dict[str, Any]:
        try:
            folder_id, _, _ = self._resolve_folder_id(destination_folder_id)
            add_parents = "root" if not folder_id else folder_id
            if folder_id:
                folder_meta = self.service.files().get(
                    fileId=folder_id,
                    fields="id, name, mimeType",
                    supportsAllDrives=True,
                ).execute()
                if folder_meta.get("mimeType") != FOLDER_MIME:
                    raise UsageError(
                        f"destination {folder_meta.get('name', folder_id)!r} is not a Drive folder"
                    )

            file_meta = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, parents",
                supportsAllDrives=True,
            ).execute()
            parents = file_meta.get("parents", []) or []
            remove_parents = ",".join(parents)

            res = self.service.files().update(
                fileId=file_id,
                addParents=add_parents,
                removeParents=remove_parents,
                fields="id, name, mimeType, parents, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", file_id),
                "name": res.get("name", file_meta.get("name", "")),
                "mimeType": res.get("mimeType", file_meta.get("mimeType", "")),
                "parents": res.get("parents", []),
                "web_view_link": res.get("webViewLink", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"move file {file_id}") from e
```

- [ ] **Step 4: Run tests to verify `move_file` passes**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py -q
```

Expected: move tests PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/drive/client.py tests/connectors/drive/test_client.py
git commit -m "feat(drive): add move file operation"
```

---

### Task 5: Tighten help coverage and run targeted suite

**Files:**
- Modify: `tests/connectors/drive/test_commands.py`
- Test: `tests/connectors/drive/test_commands.py`
- Test: `tests/connectors/drive/test_client.py`

- [ ] **Step 1: Expand help coverage**

Update `tests/connectors/drive/test_commands.py` so the command lists include:

```python
    cases = [
        ("rename", ["file1", "renamed.txt"]),
        ("copy", ["file1"]),
        ("move", ["file1", "--to", "folder1"]),
    ]
```

And inside `test_help_exits_zero()` add:

```python
            elif cmd == "rename":
                argv = ["drive", cmd, "file1", "renamed.txt", "--help"]
            elif cmd == "copy":
                argv = ["drive", cmd, "file1", "--help"]
            elif cmd == "move":
                argv = ["drive", cmd, "file1", "--to", "folder1", "--help"]
```

- [ ] **Step 2: Run the targeted Drive suite**

Run:

```bash
uv.exe run pytest tests/connectors/drive/test_client.py tests/connectors/drive/test_commands.py -q
```

Expected: PASS.

- [ ] **Step 3: Run CLI help checks**

Run:

```bash
uv.exe run h2t-ops drive rename --help
uv.exe run h2t-ops drive copy --help
uv.exe run h2t-ops drive move --help
```

Expected: each command prints usage with the new arguments and exits 0.

- [ ] **Step 4: Commit**

```bash
git add tests/connectors/drive/test_commands.py
git commit -m "test(drive): cover file management help surface"
```

---

### Task 6: Safe live smoke and issue closure gate

**Files:**
- No code changes required unless smoke exposes a bug
- Reference: `docs/reports/2026-05-25-h2t-ops-recent-closure-validation-checklist.md`

- [ ] **Step 1: Create safe test folders**

Run:

```bash
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-a" --json
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-b" --json
```

Expected: two fresh folder IDs for smoke-only artifacts.

- [ ] **Step 2: Pick one harmless source file**

Run:

```bash
uv.exe run h2t-ops drive list --json
```

Expected: do **not** reuse a live working document. Either choose an obviously disposable file or create a tiny test file first and use only that artifact for rename/copy/move.

- [ ] **Step 3: Validate rename**

Run:

```bash
uv.exe run h2t-ops drive rename <file-id> "h2t-ops-smoke-renamed.txt" --json
```

Expected: `ok: true` and updated `name`.

- [ ] **Step 3a: Restore the original filename if the source artifact is not disposable**

Run:

```bash
uv.exe run h2t-ops drive rename <file-id> "<original-name>" --json
```

Expected: original name restored. Skip this step only if the smoke source file was created specifically for the test.

- [ ] **Step 4: Validate copy into smoke folder**

Run:

```bash
uv.exe run h2t-ops drive copy <file-id> --name "h2t-ops-copy.txt" --folder <folder-a-id> --json
```

Expected: `ok: true`, new `file_id`, and `parents` include `<folder-a-id>`.

- [ ] **Step 5: Validate move of the copied file**

Run:

```bash
uv.exe run h2t-ops drive move <copied-file-id> --to <folder-b-id> --json
```

Expected: `ok: true`, and `parents` now contain only `<folder-b-id>`.

- [ ] **Step 6: Record evidence and close only if all three operations passed**

Required evidence:
- targeted tests PASS
- help surface PASS
- live rename PASS
- live copy PASS
- live move PASS

If any live step fails:
- do **not** close `#179`
- patch the bug
- rerun smoke

- [ ] **Step 7: Commit any final fixes or evidence docs**

```bash
git add docs/reports/<evidence-file>.md
git commit -m "docs(drive): record move copy rename smoke evidence"
```

---

## Self-Review

- Spec coverage:
  - `rename` covered in Task 2
  - `copy` covered in Task 3
  - `move` covered in Task 4
  - CLI/help/JSON surface covered in Tasks 1 and 5
  - live acceptance covered in Task 6
- Placeholder scan:
  - no `TODO`, `TBD`, or implicit “write tests”
  - each code step includes concrete method signatures or command snippets
- Type consistency:
  - CLI names: `rename`, `copy`, `move`
  - client methods: `rename_file`, `copy_file`, `move_file`
  - move dispatch arg: `destination_folder_id`
