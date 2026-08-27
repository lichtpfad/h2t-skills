# 2026-05-25 Drive File Management Smoke

## Scope

Validation for `#179` (`drive rename`, `drive copy`, `drive move`) on real Google
Drive state after targeted test coverage landed.

Branch during validation: `codex-drive-file-management-ops`

## Preconditions

- Targeted suite already green:
  - `uv.exe run pytest tests/connectors/drive/test_client.py tests/connectors/drive/test_commands.py -q`
  - result: `73 passed`
- CLI help surface already green:
  - `uv.exe run h2t-ops drive rename --help`
  - `uv.exe run h2t-ops drive copy --help`
  - `uv.exe run h2t-ops drive move --help`

## Disposable Smoke Artifacts

- local source file:
  - `C:\dev\h2t-skills\.codex-smoke\drive-smoke-20260525-213408.txt`
- destination folders:
  - `DRIVE_FILE_ID_1` — `h2t-ops-move-smoke-a-20260525-213408`
  - `DRIVE_FILE_ID_2` — `h2t-ops-move-smoke-b-20260525-213408`

## Commands and Results

### 1. Create smoke folder A

Command:

```bash
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-a-20260525-213408" --json
```

Result: PASS

- `file_id`: `DRIVE_FILE_ID_1`

### 2. Create smoke folder B

Command:

```bash
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-b-20260525-213408" --json
```

Result: PASS

- `file_id`: `DRIVE_FILE_ID_2`

### 3. Upload disposable source file

Command:

```bash
uv.exe run h2t-ops drive upload C:\dev\h2t-skills\.codex-smoke\drive-smoke-20260525-213408.txt --folder DRIVE_FILE_ID_1 --json
```

Result: PASS

- uploaded file id:
  - `DRIVE_FILE_ID_3`

### 4. Rename

Command:

```bash
uv.exe run h2t-ops drive rename DRIVE_FILE_ID_3 h2t-ops-smoke-renamed-20260525-213408 --json
```

Result: PASS

- `file_id`: `DRIVE_FILE_ID_3`
- `name`: `h2t-ops-smoke-renamed-20260525-213408`

### 5. Copy into folder B

Command:

```bash
uv.exe run h2t-ops drive copy DRIVE_FILE_ID_3 --name h2t-ops-copy-20260525-213408 --folder DRIVE_FILE_ID_2 --json
```

Result: PASS

- copied file id:
  - `DRIVE_FILE_ID_4`
- `parents`:
  - `["DRIVE_FILE_ID_2"]`

### 6. Move original into folder B

Command:

```bash
uv.exe run h2t-ops drive move DRIVE_FILE_ID_3 --to DRIVE_FILE_ID_2 --json
```

Result: PASS

- moved file id:
  - `DRIVE_FILE_ID_3`
- final `parents`:
  - `["DRIVE_FILE_ID_2"]`

## Conclusion

`#179` validation gate is satisfied.

- targeted tests: PASS
- CLI help surface: PASS
- live `rename`: PASS
- live `copy`: PASS
- live `move`: PASS

No rollback was required because the smoke used a disposable uploaded file and
dedicated smoke folders.
