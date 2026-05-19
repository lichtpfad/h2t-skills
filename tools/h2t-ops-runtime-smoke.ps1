#requires -Version 7
param([switch]$ResolveUvOnly)   # MUST be the first statement after #requires

<#
## PATH strategy — h2t-ops smoke harness is always PATH-independent
#
# The harness resolves uv and all tool binaries by absolute path, so it passes
# even when the user PATH is broken.  If you want uv on PATH permanently:
#
# Option A — Durable (recommended, one-time, manual, survives new shells):
#   Note: run where $PSScriptRoot is set, or substitute the script's full path.
#   [Environment]::SetEnvironmentVariable(
#       'PATH',
#       [Environment]::GetEnvironmentVariable('PATH','User') + ';' +
#       (Split-Path (& "$PSScriptRoot\h2t-ops-runtime-smoke.ps1" -ResolveUvOnly)) + ';' +
#       (Join-Path $HOME '.local\bin'),
#       'User'
#   )
#
# Option B — In-script fallback (this script, every command invoked by absolute path):
#   Every binary is obtained via Resolve-Uv / absolute candidate list so no PATH needed.
#>

$ErrorActionPreference = 'Stop'

function Resolve-Uv {
    # Prefer the stable WinGet Links shim; fall back to the version-stamped package path.
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\uv.exe'),
        'C:\Users\stani\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe'  # machine-specific fallback; Links shim above covers other installs
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "uv not found in WinGet Links, package path, or PATH"
}

# Resolver-only mode: emit ONLY the uv path and exit BEFORE any harness body.
# Other scripts get uv via:  $uv = pwsh -NoProfile -File <this> -ResolveUvOnly
if ($ResolveUvOnly) { Resolve-Uv; return }

# Task-1 self-test tail (Task 2 REPLACES everything from here down with the
# harness body — but KEEPS the #requires + param + Resolve-Uv + the
# `if ($ResolveUvOnly)` early-return above, unchanged):
$uv = Resolve-Uv
& $uv --version
if ($LASTEXITCODE -ne 0) { throw "uv --version exited $LASTEXITCODE" }
Write-Host "RESOLVED-UV: $uv"
