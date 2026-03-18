---
name: setup
description: "Install h2t Python dependencies into ~/.h2t/venv. Cross-platform: Mac, Linux, Windows. Run once after plugin install or update. Triggers: 'h2t setup', 'install h2t', 'setup plugin', 'h2t install', 'h2t:setup'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# h2t Setup

Install Python dependencies for h2t integration skills (gmail, calendar, notion, telegram, drive, etc.).

## Procedure

### Step 1: Detect environment

```bash
python3 -c "import sys, os; print(sys.platform); print(os.path.expanduser('~'))"
```

Determine:
- `VENV_DIR`: `~/.h2t/venv` (Mac/Linux) or `%USERPROFILE%\.h2t\venv` (Windows)
- `PIP`: `$VENV_DIR/bin/pip` (Mac/Linux) or `$VENV_DIR\Scripts\pip` (Windows)
- `PYTHON`: `python3` (Mac/Linux) or `python` (Windows)

### Step 2: Locate requirements.txt

Requirements are bundled with the plugin. Find the installed plugin path:

```bash
# The requirements.txt is next to this SKILL.md, two levels up:
# ~/.claude/plugins/cache/lichtpfad/h2t/{version}/requirements.txt
ls ~/.claude/plugins/cache/lichtpfad/h2t/*/requirements.txt 2>/dev/null || \
ls "$APPDATA/../Local/.claude/plugins/cache/lichtpfad/h2t/"*/requirements.txt 2>/dev/null
```

### Step 3: Create venv (if not exists)

**Mac/Linux:**
```bash
python3 -m venv ~/.h2t/venv
```

**Windows (PowerShell):**
```powershell
python -m venv "$env:USERPROFILE\.h2t\venv"
```

### Step 4: Install dependencies

**Mac/Linux:**
```bash
~/.h2t/venv/bin/pip install --upgrade pip
~/.h2t/venv/bin/pip install -r {requirements_path}
```

**Windows (PowerShell):**
```powershell
& "$env:USERPROFILE\.h2t\venv\Scripts\pip" install --upgrade pip
& "$env:USERPROFILE\.h2t\venv\Scripts\pip" install -r {requirements_path}
```

### Step 5: Set DOR_MACHINE_NAME (if not set)

Check if `DOR_MACHINE_NAME` is set:
```bash
echo "${DOR_MACHINE_NAME:-NOT SET}"
```

If not set, ask user: "Как назвать эту машину? (например: mac, automata, work)"
Then show how to add it:

**Mac/Linux** (add to `~/.zshrc` or `~/.bashrc`):
```bash
echo 'export DOR_MACHINE_NAME="{name}"' >> ~/.zshrc
```

**Windows** (add to PowerShell profile):
```powershell
Add-Content $PROFILE "`n`$env:DOR_MACHINE_NAME = '{name}'"
```

### Step 6: Verify

```bash
# Mac/Linux
~/.h2t/venv/bin/python -c "import google.generativeai, notion_client, telethon, docx; print('OK')"

# Windows
& "$env:USERPROFILE\.h2t\venv\Scripts\python" -c "import google.generativeai, notion_client, telethon, docx; print('OK')"
```

Show summary: which packages installed, venv path, DOR_MACHINE_NAME status.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using system python instead of venv | Always activate venv or use full path to venv python |
| Running on wrong Python version | Check `python --version` >= 3.10 |
| Windows path with spaces | Use `$env:USERPROFILE` not `~` in Windows commands |
