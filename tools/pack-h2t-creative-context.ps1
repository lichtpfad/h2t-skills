param(
    [string]$Root = "C:\dev\h2t-skills",
    [string]$Pilot = "C:\dev\h2t-skills-119-editorial-pilot",
    [string]$Output = "C:\tmp\h2t-creative-context.xml",
    [string]$StageRoot = "C:\tmp\h2t-creative-context-repomix-staging",
    [switch]$UseNpx
)

$ErrorActionPreference = "Stop"

if ($UseNpx) {
    throw "-UseNpx is disabled for security. Install a reviewed repomix binary on PATH and run without -UseNpx."
}

$files = @(
    "$Root\docs\superpowers\specs\2026-04-26-h2t-creative-v2-design.md",
    "$Root\docs\superpowers\specs\2026-04-28-h2t-creative-profiles-design.md",
    "$Root\docs\superpowers\specs\2026-04-28-h2t-creative-v3-roadmap.md",
    "$Root\docs\superpowers\specs\2026-05-04-h2t-creative-recovery-audit.md",
    "$Root\docs\superpowers\specs\2026-05-04-h2t-creative-recovery-spec.md",

    "$Root\docs\superpowers\plans\2026-04-26-h2t-creative-v2.md",
    "$Root\docs\superpowers\plans\2026-04-28-h2t-creative-profiles.md",
    "$Root\docs\superpowers\plans\2026-05-03-h2t-creative-phase2a.md",
    "$Root\docs\superpowers\plans\2026-05-03-h2t-creative-phase2b.md",
    "$Root\docs\superpowers\plans\2026-05-04-h2t-creative-r1-legacy-fidelity.md",
    "$Root\docs\superpowers\plans\2026-05-05-r2a-h2t-terminal-deck-modularization.md",
    "$Root\docs\superpowers\plans\2026-05-07-r2b-h2t-editorial-modularization.md",

    "$Root\docs\visual-regression\2026-05-04-r1\h2t-graphs-design-system.md",
    "$Root\docs\visual-regression\2026-05-04-r1\h2t-mono-design-system.md",
    "$Root\docs\visual-regression\2026-05-05-r2\h2t-terminal-deck-design-system.md",
    "$Root\docs\visual-regression\2026-05-05-r2\h2t-terminal-deck-modular\parity-notes.md",
    "$Root\docs\visual-regression\2026-05-07-r2b\h2t-editorial-deck-system-b-modular\parity-notes.md",

    "$Root\plugins\h2t-creative\profiles\h2t-editorial\DESIGN.md",
    "$Root\plugins\h2t-creative\profiles\h2t-graphs\DESIGN.md",
    "$Root\plugins\h2t-creative\profiles\h2t-mono\DESIGN.md",
    "$Root\plugins\h2t-creative\profiles\h2t-terminal\DESIGN.md",
    "$Root\plugins\h2t-creative\skills\legacy-fidelity\SKILL.md",
    "$Root\plugins\h2t-creative\skills\legacy-fidelity\references\pressure-scenarios.md",

    "$Pilot\docs\superpowers\specs\2026-05-08-h2t-creative-semantic-rendering-architecture.md",
    "$Pilot\docs\superpowers\plans\2026-05-08-h2t-creative-semantic-renderer-v0.md",
    "$Pilot\docs\superpowers\references\h2t-creative-semantic-rendering-prior-art.md",
    "$Pilot\docs\superpowers\specs\2026-05-07-r2b-landing-source-arbitration.md",
    "$Pilot\docs\visual-regression\2026-05-07-r2b\h2t-editorial-landing-design-system.md",
    "$Pilot\docs\visual-regression\2026-05-07-r2b\h2t-editorial-landing-composition-spec.md",
    "$Pilot\docs\visual-regression\2026-05-07-r2b\h2t-editorial-landing-rhythm-spec.md",
    "$Pilot\docs\visual-regression\2026-05-08-semantic-v0\h2t-editorial-landing-v0\parity-notes.md"
)

$existing = @()
$missing = @()

foreach ($file in $files) {
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        $existing += (Resolve-Path -LiteralPath $file).Path
    } else {
        $missing += $file
    }
}

if ($existing.Count -eq 0) {
    throw "No input files found. Check -Root and -Pilot paths."
}

$outputDir = Split-Path -Parent $Output
if ($outputDir -and -not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if ($missing.Count -gt 0) {
    Write-Warning "Missing $($missing.Count) files; packing $($existing.Count) existing files."
    $missing | ForEach-Object { Write-Warning "Missing: $_" }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stage = Join-Path $StageRoot $stamp
New-Item -ItemType Directory -Path $stage -Force | Out-Null

foreach ($file in $existing) {
    if ((Test-Path -LiteralPath $Pilot) -and $file.StartsWith((Resolve-Path -LiteralPath $Pilot).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $file.Substring((Resolve-Path -LiteralPath $Pilot).Path.Length).TrimStart("\", "/")
        $target = Join-Path $stage (Join-Path "pilot" $relative)
    } elseif ($file.StartsWith((Resolve-Path -LiteralPath $Root).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $file.Substring((Resolve-Path -LiteralPath $Root).Path.Length).TrimStart("\", "/")
        $target = Join-Path $stage (Join-Path "root" $relative)
    } else {
        $safeName = ($file -replace "[:\\\/]", "_")
        $target = Join-Path $stage (Join-Path "external" $safeName)
    }

    $targetDir = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $file -Destination $target -Force
}

$repomix = Get-Command repomix -ErrorAction SilentlyContinue
if (-not $repomix) {
    throw "repomix not found on PATH. Install a reviewed local version first; this script will not run an unpinned npx package."
}

Push-Location $stage
try {
    repomix --style xml --parsable-style -o $Output
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $Output -PathType Leaf)) {
    throw "Repomix finished but output file was not created: $Output"
}

$size = (Get-Item -LiteralPath $Output).Length
Write-Host "Packed $($existing.Count) files into $Output ($size bytes)"
Write-Host "Staging copy: $stage"
