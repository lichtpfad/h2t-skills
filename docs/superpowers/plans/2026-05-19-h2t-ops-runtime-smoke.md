# h2t-ops Local Runtime Smoke (#139) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Execution must happen in an isolated worktree branched off `main`** (created via superpowers:using-git-worktrees) — NOT in the `feat+131-gmail-connector` worktree (this is runtime/infra scope, independent of PR #140's connector code; mixing them re-pollutes #140).

**Goal:** Prove `h2t-ops` runs as an *installed local CLI* on this machine and passes live read-only Notion **and Gmail** smoke (both are hard gates per standing decision), closing blocker #139 so PR #140 acceptance is unblocked.

**Architecture:** Three concerns are kept strictly separate and never conflated: **(1)** h2t-ai's `h2t` is out of scope — its stale `~/.local/bin/h2t.exe` (`uv trampoline failed to canonicalize script path`) is h2t-ai's own breakage; we never touch, shadow, repair, or reinstall it. **(2)** `uv` is installed but absent from the interactive PATH — pinned via a canonical absolute path / one-time user-PATH fix. **(3)** `h2t-ops` is installed with `uv tool install --reinstall` from the **PR #140 worktree** (the only ref containing the `h2t_ops` package + `uv.lock` until #140 merges), producing `~/.local/bin/h2t-ops.exe`; a committed, repeatable smoke harness then asserts the hard DoD. `/h2t-core:setup` is updated to perform/repair this install (spec §7), but #139 **closes on the manual repair + harness evidence (Tasks 1–4, 6)**; setup automation (Task 5) is sequenced so it does NOT block #139.

> **Sequencing (verbatim, normative):**
> - **Temporary source for #139:** PR #140 worktree (`C:/dev/h2t-skills/.claude/worktrees/feat+131-gmail-connector`).
> - **Canonical future source:** released/merged `h2t-ops` package from `main` or a git ref (after #140 merges).
> - **Do not use root `h2t` for this smoke.** h2t-ai's broken `h2t` is a separate problem; do not fix it here.
> - **#139 is a blocker for *acceptance*, not for *coding*.** Gmail code (#131/PR #140) is already done; PR #140 stays **draft** until #139 passes through the installed CLI.

**Tech Stack:** `uv` (WinGet install), `uv tool install --reinstall`, PowerShell 7+ (primary — this machine) with POSIX parity for CI/Mac, the existing `h2t-ops doctor`, live Notion REST *through the installed `h2t-ops notion` CLI* (never direct REST — proving the CLI path is the entire point).

**Hard DoD (the gate — must all hold via the installed binary, absolute path, no PATH assumptions):**
```
~/.local/bin/h2t-ops.exe --version
~/.local/bin/h2t-ops.exe doctor
~/.local/bin/h2t-ops.exe notion get 10adbc1e61d04d13aa6f17210b77e0d3 --json
~/.local/bin/h2t-ops.exe notion blocks 10adbc1e61d04d13aa6f17210b77e0d3 --limit 3 --json
~/.local/bin/h2t-ops.exe gmail list --max 3 --json     # HARD gate — Task 4: bootstrap mandatory if not authed
```
(Notion fixture `10adbc1e61d04d13aa6f17210b77e0d3` = "Art - Projects", confirmed read-only & live. All five lines are hard-gate; `gmail` exit 3 = #139 FAIL, not informational.)

---

## Known machine state (verified 2026-05-19 — do not re-discover, but DO re-verify in Task steps)

| Fact | Value |
|---|---|
| `uv` installed at | `C:/Users/stani/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uv.exe` (v0.10.10) |
| `uv` on interactive PATH? | **No** ("uv not found" in user shell) |
| WinGet stable shim dir (prefer if present) | `C:/Users/stani/AppData/Local/Microsoft/WinGet/Links/` |
| uv tool bin dir (where `h2t-ops.exe` lands) | `C:/Users/stani/.local/bin` |
| `~/.local/bin` current contents | `graphify.exe`, `h2t.exe` (h2t-ai — **stale/broken, OUT OF SCOPE**); **no `h2t-ops.exe`** |
| `uv tool list` | `graphify`, `h2t-ai → h2t` — **`h2t-ops` is NOT installed** (root cause of "doesn't run") |
| `h2t_ops` package + `[project.scripts] h2t-ops = "h2t_ops.cli:main"` + `uv.lock` | only on branch `worktree-feat+131-gmail-connector` (PR #140, draft) — **NOT on `main`** |
| `/h2t-core:setup` skill | exists at `plugins/h2t-core/skills/setup/SKILL.md`; does **NOT** currently `uv tool install` h2t-ops (spec §7 gap; legacy `secrets-readme-template.md` still points at `~/.h2t/venv/...python.exe`) |
| Notion token | live; read-only workspace search confirmed (Art-Projects et al.) |

## File Structure

| File | Responsibility |
|---|---|
| `tools/h2t-ops-runtime-smoke.ps1` (create) | Single repeatable PowerShell harness encoding the hard DoD: resolves uv, runs each command via the **absolute** `~/.local/bin/h2t-ops.exe`, asserts exit 0 + JSON parses + non-empty + no token leak, emits an Evidence block. One responsibility: prove-and-report. |
| `tools/h2t-ops-runtime-smoke.sh` (create) | POSIX parity of the same harness (CI/Mac); identical assertions, no PowerShell idioms. |
| `plugins/h2t-core/skills/setup/SKILL.md` (modify) | Add an "h2t-ops runtime (install / repair)" section: canonical uv resolution, `uv tool install --reinstall <source>`, `~/.local/bin` PATH guidance, the verbatim Sequencing block, and the explicit "never touch h2t-ai's `h2t`" boundary. |
| `docs/superpowers/plans/2026-05-19-h2t-ops-runtime-smoke.md` | This plan. |
| Evidence | Posted into issue **#139** and as a **PR #140** comment using the Evidence Format from `docs/h2t-ops-testing-plan.md` — not a repo file. |

---

### Task 1: Pin the canonical `uv` invocation

**Files:**
- Create: `tools/h2t-ops-runtime-smoke.ps1` (the `Resolve-Uv` function only — rest added in Task 2)

- [ ] **Step 1: Write the failing check**

Create `tools/h2t-ops-runtime-smoke.ps1` with ONLY this resolver + a self-test tail:

```powershell
#requires -Version 7
param([switch]$ResolveUvOnly)   # MUST be the first statement after #requires
$ErrorActionPreference = 'Stop'

function Resolve-Uv {
    # Prefer the stable WinGet Links shim; fall back to the version-stamped package path.
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\uv.exe'),
        'C:\Users\stani\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe'
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
```

- [ ] **Step 2: Run to verify the resolver works (this step's "test")**

Run: `pwsh -File tools/h2t-ops-runtime-smoke.ps1`
Expected: prints `uv 0.10.x` then `RESOLVED-UV: <path>`, exit 0. If it throws "uv not found" the candidate list is wrong — fix the paths against the Known-machine-state table, do not proceed.

- [ ] **Step 3: Decide & document the PATH strategy (no code beyond Step 1)**

Two supported options — document BOTH in a `## PATH` comment block at the top of the script; the harness itself always uses absolute paths so it is PATH-independent:
- **Durable (recommended, one-time, manual):** append uv's dir AND `~/.local/bin` to the user PATH:
  ```powershell
  [Environment]::SetEnvironmentVariable('PATH',
    [Environment]::GetEnvironmentVariable('PATH','User') + ';' +
    (Split-Path (Resolve-Uv)) + ';' + (Join-Path $HOME '.local\bin'), 'User')
  ```
  (User runs this once in a normal shell; new shells then have `uv` and `h2t-ops`.)
- **Fallback (in-script):** every command in the harness is invoked by absolute path (`& $uv ...`, `& "$HOME\.local\bin\h2t-ops.exe" ...`) so the smoke passes even with a broken PATH.

- [ ] **Step 4: Commit**

```bash
git add tools/h2t-ops-runtime-smoke.ps1
git commit -m "feat(runtime): uv resolver + PATH strategy for h2t-ops smoke (#139)"
```

---

### Task 2: Smoke harness — write it so it FAILS on the current broken state

**Files:**
- Modify: `tools/h2t-ops-runtime-smoke.ps1`

- [ ] **Step 1: Write the failing test (the harness body)**

KEEP the Task-1 header unchanged (`#requires`, `param([switch]$ResolveUvOnly)`, `$ErrorActionPreference`, `function Resolve-Uv`, and the `if ($ResolveUvOnly) { Resolve-Uv; return }` early-return). REPLACE only the Task-1 self-test tail (everything from `$uv = Resolve-Uv` down) with this harness body:

```powershell
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
# --- G4 Gmail live read-only (HARD GATE — must pass; bootstrap is mandatory, see Task 4) ---
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
```

- [ ] **Step 2: Run to verify it FAILS for the right reason**

Run: `pwsh -File tools/h2t-ops-runtime-smoke.ps1`
Expected: `[PASS] uv --version`, then `[FAIL] h2t-ops --version exit=999` (binary absent — `~/.local/bin/h2t-ops.exe` does not exist yet), `HARD GATE (#139): FAIL`, exit 1. This proves the harness detects the real broken state.

- [ ] **Step 3: POSIX parity**

Create `tools/h2t-ops-runtime-smoke.sh` — same SIX hard-gate commands (incl. `gmail list`), `set -e` off (collect all), `jq -e . >/dev/null` for JSON checks, grep for token leak, `$HOME/.local/bin/h2t-ops` (no `.exe`), exit non-zero unless ALL six hard-gate pass (gmail included — no informational carve-out). (No PowerShell idioms; identical assertions.)

- [ ] **Step 4: Run the bash harness to confirm it also FAILs cleanly**

Run: `bash tools/h2t-ops-runtime-smoke.sh`
Expected: `h2t-ops --version` FAIL (absent), hard gate FAIL, non-zero exit — no crash, clean report.

- [ ] **Step 5: Commit**

```bash
git add tools/h2t-ops-runtime-smoke.ps1 tools/h2t-ops-runtime-smoke.sh
git commit -m "feat(runtime): h2t-ops smoke harness — fails on uninstalled state (#139)"
```

> **Defect note (Task 2 code-quality review — harness gates the Task-4 live acceptance):**
> the `$out = & $cmd 2>&1` / `out=$("$@" 2>&1)` single-stream capture merges stderr
> into the JSON parse → any stderr line before JSON (future eager import / SDK
> deprecation) silently flips a live PASS to a **false FAIL** in Task 4. Fixed by
> **two-stream capture for json-mode** (parse stdout only; scan stdout+stderr for
> leaks). Also: add EVIDENCE `NOTE:` lines explaining `exit=999` (PS throw sentinel)
> vs `exit=127` (bash not-found); add `ya29\.[A-Za-z0-9._\-]{20,}` (Google OAuth)
> to the token-leak regex before the live gmail run; one-line comments on the
> `$LASTEXITCODE`-external-only assumption and the untested python JSON fallback.

---

### Task 3: Install `h2t-ops` from the PR #140 worktree (the G0 implement step)

**Files:** none (machine state; nothing committed — the install is environment, not source)

- [ ] **Step 1: Record h2t-ai baseline (prove we never touch it)**

```powershell
# Do NOT dot-source the harness (it runs the body + exits). Use resolver-only mode:
$uv = (pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly).Trim()
& $uv tool list
Get-FileHash "$HOME\.local\bin\h2t.exe" -Algorithm SHA256   # h2t-ai's binary — baseline
```
Record the `h2t.exe` hash and the `uv tool list` output. **Constraint:** h2t-ai's `h2t` MUST be byte-identical before/after this task. We never run `uv tool install ... h2t`, never `--reinstall h2t`, never edit `~/.local/bin/h2t.exe`.

- [ ] **Step 2: Install h2t-ops from the temporary source (PR #140 worktree)**

```powershell
& $uv tool install --reinstall "C:/dev/h2t-skills/.claude/worktrees/feat+131-gmail-connector"
```
Expected: uv resolves project `h2t-ops` (name from its `pyproject.toml`), installs deps from its `uv.lock`, writes `C:/Users/stani/.local/bin/h2t-ops.exe`. `--reinstall` makes it idempotent/repairable.

- [ ] **Step 3: Verify install + h2t-ai untouched (this task's "test")**

```powershell
Test-Path "$HOME\.local\bin\h2t-ops.exe"                       # must be True
& "$HOME\.local\bin\h2t-ops.exe" --version                     # must exit 0, print h2t-ops 0.2.0
(Get-FileHash "$HOME\.local\bin\h2t.exe" -Algorithm SHA256).Hash  # must equal Step-1 baseline
& $uv tool list                                                # h2t-ops now listed; h2t-ai entry unchanged
```
Expected: `h2t-ops.exe` exists, `--version` → `h2t-ops 0.2.0` exit 0, **h2t.exe hash unchanged**, `uv tool list` now shows `h2t-ops` alongside the untouched `h2t-ai`. If the hash changed → STOP, you violated the scope boundary; revert and investigate.

- [ ] **Step 4: Re-run the harness G0 section**

Run: `pwsh -File tools/h2t-ops-runtime-smoke.ps1`
Expected: `[PASS] uv --version`, `[PASS] h2t-ops --version`, `[PASS] h2t-ops doctor` (doctor prints version, executable path, connectors incl. `notion`+`gmail`, secrets presence — no network). Notion/gmail lines may still FAIL (next task). No commit (machine state).

---

### Task 4: Live read-only Notion + Gmail E2E through the installed CLI

**Files:** none (the assertions live in the already-committed harness; this task runs it against live providers)

- [ ] **Step 1: Run the full harness against live Notion + Gmail**

Precondition: Notion token resolvable (`NOTION_API_TOKEN` in `~/.dor/secrets.env` or `~/.config/notion/token`).
Run: `pwsh -File tools/h2t-ops-runtime-smoke.ps1`

- [ ] **Step 2: Assert the hard Notion gate (this is #139's core "test")**

Expected, all via `~/.local/bin/h2t-ops.exe`:
- `[PASS] notion get` — exit 0, JSON parses, non-empty, no token in output.
- `[PASS] notion blocks` — exit 0, JSON parses, ≤3 blocks, non-empty, no token.
- `HARD GATE (#139): PASS`, harness exit 0.

If `notion get` exits 3 → config (token not resolvable by the *installed* tool's secrets loader — a real adoption finding: fix secrets path, do NOT fall back to direct REST). If exit 4 → auth (token invalid). Either is a genuine #139 failure to resolve here, not to paper over.

- [ ] **Step 3: Gmail HARD gate — bootstrap is mandatory, not optional**

Standing decision: BOTH Notion and Gmail must be tested live. `gmail list --max 3 --json` (gmail uses `--max`, NOT `--limit`) is in `$hardGate`. There is **no informational carve-out** and #139 does **not** pass with gmail failing.

- **If Google OAuth already bootstrapped** (`~/.config/gmail/token.json` or `~/.config/google-calendar-mcp/tokens.json` valid): expect `[PASS] gmail list` — exit 0, JSON parses, plausible non-empty result.
- **If not bootstrapped** (`gmail list` exits 3, §4.1 — connector raises ConfigError, no browser): this is a **#139 FAIL**. You MUST run the one-time bootstrap, then re-run the harness until `gmail list` is `[PASS]`:
  ```bash
  python C:/dev/h2t-skills/.claude/worktrees/feat+131-gmail-connector/plugins/h2t/skills/gmail/scripts/gmail_cli.py labels
  ```
  (performs browser OAuth, writes the token to `~/.config/gmail/token.json` or the shared `tokens.json`), then `~/.local/bin/h2t-ops.exe gmail list --max 3 --json` → must exit 0, JSON, non-empty.
- If the bootstrap itself cannot be completed in this environment (no browser/display available to the operator), #139 stays **open/blocked** with that exact reason recorded — it is NOT closed as pass. (Alternative split, only if explicitly approved later: #139a = installed CLI + Notion; #139b = Gmail live gate for #131/#140. Default per current agreement: single hard gate, Gmail included.)

- [ ] **Step 4: Capture evidence (no commit — evidence goes to GitHub in Task 6)**

Save the harness `=== EVIDENCE ===` block verbatim for Task 6. Redact nothing except: never paste message bodies / page content / tokens — only command, exit, ok, result-shape.

---

### Task 5: Update `/h2t-core:setup` to perform/repair the h2t-ops install (spec §7) — NON-blocking for #139

**Files:**
- Modify: `plugins/h2t-core/skills/setup/SKILL.md`

> Per the Sequencing rule: #139 closes on Tasks 1–4 + 6 (manual repair + harness evidence). This task hardens the repair into the canonical entrypoint so the next person/agent doesn't repeat the manual steps; it is explicitly **not** a #139 blocker.

- [ ] **Step 1: Write the failing check**

Add a test asserting the setup skill documents the h2t-ops install. Create `tools/check-setup-skill.ps1`:
```powershell
$t = Get-Content plugins/h2t-core/skills/setup/SKILL.md -Raw
$need = @('uv tool install','--reinstall','h2t-ops','.local\bin','do not','h2t-ai')
$miss = $need | Where-Object { $t -notmatch [regex]::Escape($_) }
if ($miss) { Write-Error ("setup SKILL.md missing: " + ($miss -join ', ')); exit 1 }
"setup SKILL.md covers h2t-ops install/repair + h2t-ai boundary"; exit 0
```

- [ ] **Step 2: Run to verify it FAILS**

Run: `pwsh -File tools/check-setup-skill.ps1`
Expected: FAIL — current `setup/SKILL.md` has none of these tokens (verified: it does not `uv tool install` h2t-ops).

- [ ] **Step 3: Implement — add the section to `plugins/h2t-core/skills/setup/SKILL.md`**

Add a section "## h2t-ops runtime (install / repair)" containing: the `Resolve-Uv` strategy (canonical WinGet path / Links shim / one-time user-PATH fix); the idempotent repair command `& <uv> tool install --reinstall <source>`; the **verbatim Sequencing block** from this plan's header (Temporary source = PR #140 worktree; canonical future = merged main/git ref; do not use root `h2t`); `~/.local/bin` PATH guidance; and an explicit boundary callout: *"NEVER touch, reinstall, shadow, or repair h2t-ai's `h2t` (`~/.local/bin/h2t.exe`) — its `uv trampoline failed to canonicalize` is h2t-ai's own breakage, a separate problem."* Point the smoke at `tools/h2t-ops-runtime-smoke.ps1`.

- [ ] **Step 4: Run to verify it PASSES**

Run: `pwsh -File tools/check-setup-skill.ps1`
Expected: exit 0, "setup SKILL.md covers h2t-ops install/repair + h2t-ai boundary".

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/setup/SKILL.md tools/check-setup-skill.ps1
git commit -m "feat(setup): h2t-core:setup performs/repairs h2t-ops uv tool install (spec §7, #139)"
```

---

### Task 6: Record evidence + wire the #139 / PR #140 gate

**Files:** none (GitHub issue/PR comments; `gh`)

- [ ] **Step 1: Re-run the committed harness for the final evidence**

Run: `pwsh -File tools/h2t-ops-runtime-smoke.ps1` → capture the `=== EVIDENCE ===` block (hard gate must be PASS).

- [ ] **Step 2: Post evidence to issue #139** using the Evidence Format from `docs/h2t-ops-testing-plan.md` (Runtime / Notion / Gmail / Notes — redactions, skipped, follow-ups). Include: harness commit SHA, `uv tool install` source = the PR #140 worktree (temporary), h2t-ai `h2t.exe` hash unchanged (scope-boundary proof).

```bash
gh issue comment 139 -R lichtpfad/h2t-skills --body-file <evidence.md>
```

- [ ] **Step 3: Post the same evidence as a PR #140 comment** and state explicitly: hard gate (#139) PASS via installed `~/.local/bin/h2t-ops.exe`; gmail G4 status (full / auth-bootstrap-pending). **Do NOT flip #140 out of draft automatically** — that is the operator's/user's call (acceptance decision). The comment records that the code+runtime are proven; the merge action stays manual.

```bash
gh pr comment 140 -R lichtpfad/h2t-skills --body-file <evidence.md>
```

- [ ] **Step 4: Close #139** ONLY if the FULL hard gate is green — all six commands incl. `gmail list` — AND evidence is posted. **Gmail-pending is NOT a closeable state**: if `gmail list` is not `[PASS]` (e.g. OAuth not bootstrapped and bootstrap not completed), #139 stays **open/blocked** with the exact blocker recorded; it is not closed with a "follow-up". (Only deviate if the #139a/#139b split was explicitly approved — then #139a may close on CLI+Notion while #139b/#131-gate tracks Gmail. Absent that approval: one gate, all six green or #139 stays open.)

---

## Self-Review

**1. Spec coverage (against the user's directive + `docs/h2t-ops-testing-plan.md` G0/G3/G4/G6 + spec §7):**
- "Prove installed local CLI works" → Tasks 2–4 (harness via absolute `~/.local/bin/h2t-ops.exe`).
- Hard DoD (5 commands, Gmail included as a HARD gate) → Task 2 `$hardGate` (six entries) + Task 4 (executed, Gmail bootstrap mandatory); no informational carve-out anywhere.
- "Do not touch h2t / h2t-ai" → Task 3 Steps 1&3 (hash baseline + post-check), Task 5 boundary callout, Architecture.
- "Canonical uv path" → Task 1 (`Resolve-Uv` + PATH strategy).
- "Install from PR #140 worktree; canonical future = main/git ref; not root h2t" → verbatim Sequencing block in header + Task 3 Step 2 + Task 5.
- "#139 blocker for acceptance not coding; #140 stays draft" → header Sequencing + Task 6 Step 3.
- "/h2t-core:setup update if exists, else manual now + automation follow-up" → it exists ⇒ Task 5 updates it, sequenced as non-blocking; #139 closes on manual repair (Tasks 1–4,6). G6 evidence → Task 6.

**2. Placeholder scan:** No TBD/"handle errors"/"similar to". Every command is concrete with real absolute paths, the real Notion fixture id, the real uv path candidates, the real worktree source. Gmail is a hard gate (not a soft conditional): if OAuth is unbootstrapped the plan gives the exact mandatory bootstrap command and #139 stays open until `gmail list` passes — an explicit decision rule, not a placeholder.

**3. Type/identifier consistency:** `Resolve-Uv`, `$Uv`/`$Ops`/`$Fixture`, `Smoke`, `$hardGate`/`$gatePass`, `tools/h2t-ops-runtime-smoke.ps1`/`.sh`, `tools/check-setup-skill.ps1`, `plugins/h2t-core/skills/setup/SKILL.md`, fixture `10adbc1e61d04d13aa6f17210b77e0d3` — used identically across Tasks 1–6. Hard-gate set is the same five commands in the DoD, Task 2 `$hardGate`, and Task 6.

**Known intentional non-TDD shape:** this is a runtime/adoption plan — the "tests" are the smoke commands themselves; "fail" = the real broken machine state (Task 2 Step 2 / Task 3), "pass" = post-repair. Code-with-unit-tests TDD does not apply to "install a tool on a machine"; the harness IS the executable, committed, repeatable proof. The only committed artifacts are the harness + setup-skill change + this plan; the install is environment state by design.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-h2t-ops-runtime-smoke.md`. Execute in a worktree **off `main`** (not the gmail worktree). Two options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review (spec + code-quality) between tasks, defects mirrored back to this plan (same discipline as #131). Note Tasks 3 & 4 are machine/secret-bound (live install + live Notion token) — those run in the controller/operator context, not a sandboxed subagent.

**2. Inline Execution** — execute here with checkpoints (executing-plans).

Which approach?
