$t = Get-Content (Join-Path $PSScriptRoot '..\plugins\h2t-core\skills\setup\SKILL.md') -Raw
$need = @('uv tool install','--reinstall','h2t-ops','.local\bin','NEVER touch','h2t-ai')
$miss = $need | Where-Object { $t -notmatch [regex]::Escape($_) }
if ($miss) { Write-Error ("setup SKILL.md missing: " + ($miss -join ', ')); exit 1 }
"setup SKILL.md covers h2t-ops install/repair + h2t-ai boundary"; exit 0
