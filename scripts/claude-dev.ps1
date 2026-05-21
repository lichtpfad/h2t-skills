# Dev launcher for h2t-skills plugin development.
# Uses --plugin-dir so local sources override installed cache versions (no duplicates).
# Usage: pwsh scripts/claude-dev.ps1 [extra claude args]

$repo = Split-Path -Parent $PSScriptRoot

$pluginDirs = @(
    "h2t-core",
    "h2t-ops",
    "h2t-arch",
    "h2t-creative",
    "h2t-dev",
    "h2t-edu"
) | ForEach-Object { "--plugin-dir"; "$repo/plugins/$_" }

claude @pluginDirs @args
