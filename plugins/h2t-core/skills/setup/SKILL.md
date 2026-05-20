---
name: h2t-core:setup
description: "Install h2t Python dependencies into ~/.h2t/venv. Cross-platform: Mac, Linux, Windows. Run once after plugin install or update. Triggers: 'h2t setup', 'install h2t', 'setup plugin', 'h2t install', 'h2t:setup'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.2.0
---

# h2t Setup

Install Python dependencies for h2t integration skills (gmail, calendar, notion, telegram, drive, etc.).

## Procedure

### Step 1: Detect platform and set variables

```bash
# Detect OS
UNAME=$(uname -s 2>/dev/null || echo "Windows")
echo "Platform: $UNAME"

# Set platform-specific paths
if [[ "$UNAME" == *"MINGW"* ]] || [[ "$UNAME" == *"MSYS"* ]] || [[ "$UNAME" == *"Windows"* ]] || [[ "$UNAME" == *"CYGWIN"* ]]; then
  PLATFORM="windows"
  VENV_DIR="$HOME/.h2t/venv"
  VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
  VENV_PIP="$VENV_DIR/Scripts/pip.exe"
  SYS_PYTHON="python"
else
  PLATFORM="unix"
  VENV_DIR="$HOME/.h2t/venv"
  VENV_PYTHON="$VENV_DIR/bin/python"
  VENV_PIP="$VENV_DIR/bin/pip"
  SYS_PYTHON="python3"
fi

echo "Platform: $PLATFORM"
echo "Venv dir: $VENV_DIR"
```

### Step 2: Locate requirements.txt

```bash
# Requirements are bundled with the plugin
REQ=$(ls ~/.claude/plugins/cache/lichtpfad/h2t/*/requirements.txt 2>/dev/null | sort -V | tail -1)
[ -z "$REQ" ] && REQ=$(ls "$LOCALAPPDATA/.claude/plugins/cache/lichtpfad/h2t/"*/requirements.txt 2>/dev/null | sort -V | tail -1)
[ -z "$REQ" ] && echo "ERROR: requirements.txt not found. Is h2t plugin installed?" && exit 1
echo "Requirements: $REQ"
```

### Step 3: Create venv (if not exists)

```bash
if [ ! -f "$VENV_PYTHON" ]; then
  echo "Creating venv at $VENV_DIR..."
  mkdir -p "$(dirname "$VENV_DIR")"
  $SYS_PYTHON -m venv "$VENV_DIR"
else
  echo "Venv already exists at $VENV_DIR"
fi
```

### Step 4: Install dependencies

```bash
"$VENV_PIP" install --upgrade pip uv
"$VENV_PIP" install -r "$REQ"
```

### Step 4b: Install h2t CLI (enables `h2t gather` command)

Find the plugin cache root and install in editable mode:

```bash
# Find latest h2t-core cache
H2T_CACHE=$(ls -d "$HOME/.claude/plugins/cache/lichtpfad/h2t-core"/*/  2>/dev/null | sort -V | tail -1)
[ -z "$H2T_CACHE" ] && H2T_CACHE=$(ls -d "$LOCALAPPDATA/.claude/plugins/cache/lichtpfad/h2t-core"/*/ 2>/dev/null | sort -V | tail -1)

if [ -n "$H2T_CACHE" ] && [ -f "${H2T_CACHE}pyproject.toml" ]; then
  "$VENV_DIR/bin/uv" pip install -e "${H2T_CACHE}" --quiet 2>/dev/null \
    || "$VENV_PIP" install -e "${H2T_CACHE}" --quiet
  echo "h2t CLI installed from $H2T_CACHE"
else
  echo "WARN: pyproject.toml not found in cache — skipping h2t CLI install"
fi
```

After install, verify:
```bash
"$VENV_PYTHON" -m lib.cli.main gather --help 2>/dev/null && echo "h2t gather OK" || echo "h2t gather NOT available"
```

### Step 5: Set DOR_MACHINE_NAME (if not set)

Check if `DOR_MACHINE_NAME` is set:
```bash
echo "DOR_MACHINE_NAME=${DOR_MACHINE_NAME:-NOT SET}"
```

If not set, ask user: "Как назвать эту машину? (например: mac, automata, work)"

Then add to Claude Code env in `~/.claude/settings.json`:
```json
{
  "env": {
    "DOR_MACHINE_NAME": "{name}"
  }
}
```

Or set in shell profile:

**Mac/Linux** (`~/.zshrc` or `~/.bashrc`):
```bash
echo 'export DOR_MACHINE_NAME="{name}"' >> ~/.zshrc
```

**Windows** (PowerShell profile):
```powershell
Add-Content $PROFILE "`n`$env:DOR_MACHINE_NAME = '{name}'"
```

### Step 6: Verify

```bash
"$VENV_PYTHON" -c "
import google.generativeai
import notion_client
import telethon
import docx
import youtube_transcript_api
import dotenv
import yaml
print('All h2t dependencies OK')
"
```

### Step 7: Show summary

Print:
- Platform detected
- Venv path and Python version (`"$VENV_PYTHON" --version`)
- Installed packages count (`"$VENV_PIP" list | wc -l`)
- DOR_MACHINE_NAME status
- Next steps: "Run any h2t skill, e.g. /h2t:gmail or /h2t:calendar" (these are in the h2t plugin, not h2t-core)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using system python instead of venv | All h2t skills auto-detect `~/.h2t/venv` — no manual activation needed |
| Running on wrong Python version | Check `python --version` >= 3.10 |
| Windows: `python3` not found | On Windows use `python` not `python3`. Git Bash may alias it. |
| Plugin not found | Run `claude plugins add lichtpfad/claude-agent-skills` first |

## h2t-ops runtime (install / repair)

`h2t-ops` is a separate `uv`-managed CLI tool (distinct from the legacy `~/.h2t/venv` model above). Install/repair it via the steps below. The existing venv-based setup is not superseded for other h2t skills; this section covers h2t-ops specifically.

### Resolve `uv`

`uv` is installed on this machine but is often absent from the interactive PATH. Resolution order (prefer the first that exists):

1. **WinGet Links shim (stable, preferred):** `%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe`
2. **Version-stamped package path:** `C:\Users\stani\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`
3. `Get-Command uv` / `which uv` (PATH fallback)
4. Or let the smoke harness resolve it: `pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly`

**Durable one-time PATH fix (run once in a normal shell — new shells then have `uv` and `h2t-ops`):**

```powershell
[Environment]::SetEnvironmentVariable('PATH',
  [Environment]::GetEnvironmentVariable('PATH','User') + ';' +
  (Split-Path "$env:LOCALAPPDATA\Microsoft\WinGet\Links\uv.exe") + ';' +
  (Join-Path $HOME '.local\bin'), 'User')
```

### Install / repair h2t-ops (idempotent)

```powershell
# Self-healing uv resolution (always runnable verbatim — see "Resolve uv" prose
# above for the Links shim → package path → PATH order it applies internally):
$uv = pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly

# Example for #139 (temporary source = PR #140 worktree):
& $uv tool install --reinstall "C:/dev/h2t-skills/.claude/worktrees/feat+131-gmail-connector"
```

`--reinstall` makes the command safe to re-run at any time (idempotent repair). Substitute the source per the Sequencing rule below.

**Sequencing (verbatim, normative):**

> - **Temporary source for #139:** PR #140 worktree (`C:/dev/h2t-skills/.claude/worktrees/feat+131-gmail-connector`).
> - **Canonical future source:** released/merged `h2t-ops` package from `main` or a git ref (after #140 merges).
> - **Do not use root `h2t` for this smoke.** h2t-ai's broken `h2t` is a separate problem; do not fix it here.
> - **#139 is a blocker for *acceptance*, not for *coding*.** Gmail code (#131/PR #140) is already done; PR #140 stays **draft** until #139 passes through the installed CLI.

### `~/.local/bin` PATH guidance

`uv tool install` writes the `h2t-ops.exe` binary to `~/.local/bin` (`C:\Users\<you>\.local\bin`). After install, `h2t-ops` commands are invokable via the absolute path `~/.local/bin/h2t-ops.exe` (no PATH assumption needed in scripts) or via the shell once the durable PATH fix above is applied.

### Boundary — NEVER touch h2t-ai's `h2t`

**NEVER touch, reinstall, shadow, or repair h2t-ai's `h2t` (`~/.local/bin/h2t.exe`) — its `uv trampoline failed to canonicalize` is h2t-ai's own breakage, a separate problem.** Do not run `uv tool install` targeting the root `h2t` package, `--reinstall h2t`, or anything that modifies `~/.local/bin/h2t.exe`. That binary is out of scope for h2t-ops work.

### Verify

Run the committed smoke harness to confirm all gates pass (G0 runtime + Notion + Gmail):

```powershell
pwsh -File tools/h2t-ops-runtime-smoke.ps1
```

For a quick self-report of version, connectors, and secrets resolution:

```powershell
& "$HOME\.local\bin\h2t-ops.exe" doctor
```
