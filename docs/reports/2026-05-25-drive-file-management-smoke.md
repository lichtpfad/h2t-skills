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
  - `1KN1j9H232w7quz1YL5Z-5KMOdp5M1ETA` — `h2t-ops-move-smoke-a-20260525-213408`
  - `1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p` — `h2t-ops-move-smoke-b-20260525-213408`

## Commands and Results

### 1. Create smoke folder A

Command:

```bash
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-a-20260525-213408" --json
```

Result: PASS

- `file_id`: `1KN1j9H232w7quz1YL5Z-5KMOdp5M1ETA`

### 2. Create smoke folder B

Command:

```bash
uv.exe run h2t-ops drive create-folder "h2t-ops-move-smoke-b-20260525-213408" --json
```

Result: PASS

- `file_id`: `1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p`

### 3. Upload disposable source file

Command:

```bash
uv.exe run h2t-ops drive upload C:\dev\h2t-skills\.codex-smoke\drive-smoke-20260525-213408.txt --folder 1KN1j9H232w7quz1YL5Z-5KMOdp5M1ETA --json
```

Result: PASS

- uploaded file id:
  - `1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM`

### 4. Rename

Command:

```bash
uv.exe run h2t-ops drive rename 1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM h2t-ops-smoke-renamed-20260525-213408 --json
```

Result: PASS

- `file_id`: `1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM`
- `name`: `h2t-ops-smoke-renamed-20260525-213408`

### 5. Copy into folder B

Command:

```bash
uv.exe run h2t-ops drive copy 1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM --name h2t-ops-copy-20260525-213408 --folder 1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p --json
```

Result: PASS

- copied file id:
  - `1bfQWLihNvuPgKdYCY6BdlKgoM3181QEk6SDSKN4ZuMs`
- `parents`:
  - `["1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p"]`

### 6. Move original into folder B

Command:

```bash
uv.exe run h2t-ops drive move 1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM --to 1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p --json
```

Result: PASS

- moved file id:
  - `1ymuOuWxptJ8sDTaNBYobyfnJq2AauVze0et-lxB4QgM`
- final `parents`:
  - `["1ROy-2fF4OpBjdYdYAhJYukL40L8BIb5p"]`

## Conclusion

`#179` validation gate is satisfied.

- targeted tests: PASS
- CLI help surface: PASS
- live `rename`: PASS
- live `copy`: PASS
- live `move`: PASS

No rollback was required because the smoke used a disposable uploaded file and
dedicated smoke folders.
