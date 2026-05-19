#!/usr/bin/env bash
# h2t-ops runtime smoke harness — POSIX parity for h2t-ops-runtime-smoke.ps1
# Six hard-gate commands, no set -e (collect all, don't abort on first fail).
# Exits non-zero unless ALL six hard-gate commands pass.

UV=""
OPS="$HOME/.local/bin/h2t-ops"
FIXTURE="10adbc1e61d04d13aa6f17210b77e0d3"   # Notion "Art - Projects", read-only

# Resolve uv path (mirrors PowerShell Resolve-Uv logic)
WINGET_LINKS="$LOCALAPPDATA/Microsoft/WinGet/Links/uv"
WINGET_PKG="$LOCALAPPDATA/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uv"
if [ -x "$WINGET_LINKS" ]; then
    UV="$WINGET_LINKS"
elif [ -x "$WINGET_PKG" ]; then
    UV="$WINGET_PKG"
else
    UV="$(command -v uv 2>/dev/null)"
fi
[ -z "$UV" ] && UV="uv"   # fallback: let shell resolve (will fail loud if absent)

# --- result tracking ---
declare -A RESULTS_EXIT
declare -A RESULTS_OK
HARD_GATE=("uv --version" "h2t-ops --version" "h2t-ops doctor" "notion get" "notion blocks" "gmail list")

smoke() {
    local name="$1"
    shift
    local json_check="$1"
    shift
    local out out_json code ok leak

    if [ "$json_check" = "json" ]; then
        # json-mode: stdout-only capture for JSON validation (IMP-1),
        # separate merged capture for leak-scan + display.
        out_json=$("$@" 2>/dev/null)
        code=$?
        out=$("$@" 2>&1)
    else
        out=$("$@" 2>&1)
        code=$?
    fi
    ok=1
    [ $code -ne 0 ] && ok=0

    # JSON check (validate STDOUT only)
    if [ $ok -eq 1 ] && [ "$json_check" = "json" ]; then
        if command -v jq >/dev/null 2>&1; then
            echo "$out_json" | jq -e . >/dev/null 2>&1 || ok=0
        else
            # python fallback is code-correct but untested vs live h2t-ops JSON; jq preferred
            echo "$out_json" | python -c 'import json,sys;json.load(sys.stdin)' >/dev/null 2>&1 || ok=0
        fi
    fi

    # Token leak check (scan merged stdout+stderr)
    leak=0
    if echo "$out" | grep -Eq 'secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9._\-]{20,}'; then
        leak=1
        ok=0
    fi

    RESULTS_EXIT["$name"]=$code
    RESULTS_OK["$name"]=$ok

    local status_label
    [ $ok -eq 1 ] && status_label="PASS" || status_label="FAIL"
    local leak_label=""
    [ $leak -eq 1 ] && leak_label=" TOKEN-LEAK!"
    echo "[$status_label] $name exit=$code ok=$ok$leak_label"
}

# --- G0 Runtime ---
smoke "uv --version"        no  "$UV" --version
smoke "h2t-ops --version"   no  "$OPS" --version
smoke "h2t-ops doctor"      no  "$OPS" doctor
# --- G3 Notion live read-only ---
smoke "notion get"          json  "$OPS" notion get "$FIXTURE" --json
smoke "notion blocks"       json  "$OPS" notion blocks "$FIXTURE" --limit 3 --json
# --- G4 Gmail live read-only (HARD GATE — must pass; bootstrap mandatory, see Task 4) ---
smoke "gmail list"          json  "$OPS" gmail list --max 3 --json

echo ""
echo "=== EVIDENCE ==="
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Machine: $(hostname)"
echo "uv: $UV"
echo "h2t-ops: $OPS"
for key in "uv --version" "h2t-ops --version" "h2t-ops doctor" "notion get" "notion blocks" "gmail list"; do
    echo "$key: exit=${RESULTS_EXIT[$key]} ok=${RESULTS_OK[$key]}"
done
echo "NOTE: 'gmail list' is a hard-gate command. exit 3 (§4.1 OAuth not bootstrapped) is a"
echo "      FAIL for #139, not informational — run the Task-4 bootstrap, then re-run."
echo "NOTE: exit=127 = binary not found (bash command-not-found, POSIX)"

# Hard gate check (all six must pass)
gate_pass=1
for key in "${HARD_GATE[@]}"; do
    if [ "${RESULTS_OK[$key]}" != "1" ]; then
        gate_pass=0
        break
    fi
done

echo "HARD GATE (#139, incl. Gmail): $([ $gate_pass -eq 1 ] && echo PASS || echo FAIL)"
[ $gate_pass -eq 1 ] && exit 0 || exit 1
