#!/usr/bin/env bash
# Update h2t plugin in Claude Code cache from the dev repo.
# Usage: bash plugins/h2t/scripts/update-plugin.sh [--push]
#   --push: also git push to origin before updating cache
#
# Returns JSON to stdout for chat integration.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$PLUGIN_DIR/../.." && pwd)"

PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
CACHE_BASE="$HOME/.claude/plugins/cache/lichtpfad/h2t"
MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/lichtpfad"

# Resolve Python (venv > system)
PY=""
[ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && PY="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$PY" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && PY="$HOME/.h2t/venv/bin/python"
[ -z "$PY" ] && PY=$(command -v python 2>/dev/null || command -v python3 2>/dev/null || echo "")
if [ -z "$PY" ]; then
  echo '{"status": "error", "error": "Python not found"}'
  exit 1
fi

# Convert Git Bash paths to Windows paths for Python
_winpath() {
  if [[ "$1" == /c/* ]]; then
    echo "C:${1:2}"
  else
    echo "$1"
  fi
}

PLUGIN_JSON_W=$(_winpath "$PLUGIN_JSON")
INSTALLED_JSON_W=$(_winpath "$INSTALLED_JSON")

# Read version from plugin.json
VERSION=$("$PY" -c "import json; print(json.load(open(r'$PLUGIN_JSON_W'))['version'])" 2>/dev/null || echo "")
if [ -z "$VERSION" ]; then
  echo '{"status": "error", "error": "Cannot read version from plugin.json"}'
  exit 1
fi

SHA=$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
PUSH=false

for arg in "$@"; do
  case "$arg" in
    --push) PUSH=true ;;
  esac
done

# Step 1: Push if requested
if [ "$PUSH" = true ]; then
  git -C "$REPO_DIR" push origin main 2>/dev/null
fi

# Step 2: Pull marketplace (reset local changes first)
if [ -d "$MARKETPLACE_DIR/.git" ]; then
  git -C "$MARKETPLACE_DIR" checkout -- . 2>/dev/null || true
  git -C "$MARKETPLACE_DIR" clean -fd 2>/dev/null || true
  git -C "$MARKETPLACE_DIR" pull origin main --ff-only 2>/dev/null || true
fi

# Step 3: Copy plugin to cache
CACHE_DIR="$CACHE_BASE/$VERSION"
mkdir -p "$CACHE_DIR"

# Remove old contents, copy fresh
rm -rf "$CACHE_DIR"/*
cp -r "$PLUGIN_DIR"/* "$CACHE_DIR"/

# Ensure .claude-plugin exists in cache
if [ ! -d "$CACHE_DIR/.claude-plugin" ]; then
  cp -r "$PLUGIN_DIR/.claude-plugin" "$CACHE_DIR/.claude-plugin"
fi

# Step 4: Update installed_plugins.json
NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
CACHE_DIR_WIN=$(echo "$CACHE_DIR" | sed 's|/c/|C:\\|; s|/|\\|g')

# Use Python for reliable JSON editing
"$PY" -c "
import json, sys

path = r'$INSTALLED_JSON_W'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

key = 'h2t@lichtpfad'
if key in data:
    for entry in data[key]:
        entry['installPath'] = r'$CACHE_DIR_WIN'
        entry['version'] = '$VERSION'
        entry['lastUpdated'] = '$NOW'
        entry['gitCommitSha'] = '$SHA'
else:
    data[key] = [{
        'scope': 'user',
        'installPath': r'$CACHE_DIR_WIN',
        'version': '$VERSION',
        'installedAt': '$NOW',
        'lastUpdated': '$NOW',
        'gitCommitSha': '$SHA'
    }]

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null

if [ $? -ne 0 ]; then
  echo "{\"status\": \"error\", \"error\": \"Failed to update installed_plugins.json\"}"
  exit 1
fi

# Step 5: Verify
INSTALLED_VERSION=$("$PY" -c "
import json
data = json.load(open(r'$INSTALLED_JSON_W'))
print(data.get('h2t@lichtpfad', [{}])[0].get('version', 'unknown'))
" 2>/dev/null)

SKILLS_COUNT=$(ls -d "$CACHE_DIR"/skills/*/ 2>/dev/null | wc -l)
HAS_HOOK=$([ -f "$CACHE_DIR/hooks-handlers/gather-on-skill" ] && echo "true" || echo "false")

echo "{\"status\": \"ok\", \"version\": \"$VERSION\", \"sha\": \"${SHA:0:7}\", \"cache\": \"$CACHE_DIR\", \"skills\": $SKILLS_COUNT, \"hook\": $HAS_HOOK, \"installed_version\": \"$INSTALLED_VERSION\", \"note\": \"Restart Claude Code session to apply\"}"
