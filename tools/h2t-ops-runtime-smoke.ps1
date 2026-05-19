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

$Uv      = Resolve-Uv
$Ops     = Join-Path $HOME '.local\bin\h2t-ops.exe'
$Fixture = '10adbc1e61d04d13aa6f17210b77e0d3'   # Notion "Art - Projects", read-only
$results = [ordered]@{}

function Smoke([string]$name, [scriptblock]$cmd, [bool]$json) {
    try {
        $out = & $cmd 2>&1
        $code = $LASTEXITCODE
    } catch { $out = "$_"; $code = 999 }
    $ok = ($code -eq 0)
    if ($ok -and $json) {
        try { $null = ($out | Out-String | ConvertFrom-Json); $ok = $true }
        catch { $ok = $false }
    }
    $leak = ($out | Out-String) -match 'secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}'
    if ($leak) { $ok = $false }
    $results[$name] = [pscustomobject]@{ exit=$code; ok=$ok; jsonChecked=$json; tokenLeak=[bool]$leak }
    Write-Host ("[{0}] {1} exit={2} ok={3}{4}" -f $(if($ok){'PASS'}else{'FAIL'}),$name,$code,$ok,$(if($leak){' TOKEN-LEAK!'}else{''}))
}

# --- G0 Runtime ---
Smoke 'uv --version'        { & $Uv --version }                              $false
Smoke 'h2t-ops --version'   { & $Ops --version }                             $false
Smoke 'h2t-ops doctor'      { & $Ops doctor }                                $false
# --- G3 Notion live read-only ---
Smoke 'notion get'    { & $Ops notion get $Fixture --json }                  $true
Smoke 'notion blocks' { & $Ops notion blocks $Fixture --limit 3 --json }     $true
# --- G4 Gmail live read-only (HARD GATE — must pass; bootstrap mandatory, see Task 4) ---
Smoke 'gmail list'    { & $Ops gmail list --max 3 --json }                   $true

# Gmail is a HARD gate (standing decision: must test BOTH Notion and Gmail).
$hardGate = @('uv --version','h2t-ops --version','h2t-ops doctor',
              'notion get','notion blocks','gmail list')
$gatePass = ($hardGate | ForEach-Object { $results[$_].ok }) -notcontains $false
"`n=== EVIDENCE ==="
"Date: $(Get-Date -Format o)"
"Machine: $env:COMPUTERNAME"
"uv: $Uv"
"h2t-ops: $Ops"
$results.GetEnumerator() | ForEach-Object { "{0}: exit={1} ok={2}" -f $_.Key,$_.Value.exit,$_.Value.ok }
"NOTE: 'gmail list' is a hard-gate command. exit 3 (§4.1 OAuth not bootstrapped) is a"
"      FAIL for #139, not informational — run the Task-4 bootstrap, then re-run."
"HARD GATE (#139, incl. Gmail): " + $(if($gatePass){'PASS'}else{'FAIL'})
exit $(if($gatePass){0}else{1})
