# H2T Ops External Install + Debug Log

Use this checklist when installing `h2t-core` / `h2t-ops` for another user.

## Access

The repository is private. The installer requires read access to:

```text
https://github.com/lichtpfad/h2t-skills
```

Ask the user for their GitHub username and add them with read access before
installing.

## Install

In Claude Code:

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

Then run:

```text
/h2t-core:setup doctor
/h2t-core:setup install-h2t-ops
/h2t-core:setup connectors-check
```

CLI smoke:

```bash
h2t-ops --version
h2t-ops connectors
h2t-ops drive --help
```

## Debug Log To Send Back

Ask the user to run the commands below and send the resulting `h2t-debug-log.txt`.

### macOS / Linux

```bash
{
  echo "## date"
  date -u
  echo
  echo "## system"
  uname -a
  echo
  echo "## tools"
  command -v claude || true
  command -v uv || true
  command -v h2t-ops || true
  claude --version || true
  uv --version || true
  h2t-ops --version || true
  echo
  echo "## plugins"
  ls -la ~/.claude/plugins 2>/dev/null || true
  cat ~/.claude/plugins/installed_plugins.json 2>/dev/null || true
  echo
  echo "## h2t setup"
  python3 ~/.claude/plugins/cache/lichtpfad/h2t-core/latest/skills/setup/scripts/setup_h2t.py doctor --json 2>&1 || true
  python3 ~/.claude/plugins/cache/lichtpfad/h2t-core/latest/skills/setup/scripts/setup_h2t.py connectors-check --json 2>&1 || true
  echo
  echo "## h2t-ops"
  h2t-ops connectors 2>&1 || true
  h2t-ops drive --help 2>&1 || true
} > h2t-debug-log.txt
```

### Windows PowerShell

```powershell
$out = "h2t-debug-log.txt"
Remove-Item $out -ErrorAction SilentlyContinue

function Add-Section($name, $script) {
  Add-Content $out "`n## $name"
  try {
    & $script 2>&1 | Out-String | Add-Content $out
  } catch {
    Add-Content $out $_.Exception.Message
  }
}

Add-Section "date" { Get-Date -AsUTC }
Add-Section "system" { Get-ComputerInfo | Select-Object OsName, OsVersion, CsSystemType }
Add-Section "tools" {
  Get-Command claude, uv, h2t-ops -ErrorAction SilentlyContinue
  claude --version
  uv --version
  h2t-ops --version
}
Add-Section "plugins" {
  Get-ChildItem "$env:USERPROFILE\.claude\plugins" -Force -ErrorAction SilentlyContinue
  Get-Content "$env:USERPROFILE\.claude\plugins\installed_plugins.json" -ErrorAction SilentlyContinue
}
Add-Section "h2t setup" {
  py -3 "$env:USERPROFILE\.claude\plugins\cache\lichtpfad\h2t-core\latest\skills\setup\scripts\setup_h2t.py" doctor --json
  py -3 "$env:USERPROFILE\.claude\plugins\cache\lichtpfad\h2t-core\latest\skills\setup\scripts\setup_h2t.py" connectors-check --json
}
Add-Section "h2t-ops" {
  h2t-ops connectors
  h2t-ops drive --help
}
```

## Privacy

Before sending the log, remove:

- OAuth tokens;
- API keys;
- Telegram phone numbers and codes;
- email bodies;
- private file names if sensitive.

The setup doctor and connector checks are designed to report presence/status,
not secret values. Still review the log manually before sharing.

