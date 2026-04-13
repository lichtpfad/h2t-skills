#!/usr/bin/env bash
# Update h2t-dev plugin in Claude Code cache.
# Usage: bash plugins/h2t-dev/scripts/update-plugin.sh [--push]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$PLUGIN_DIR/../.." && pwd)"

PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
CACHE_BASE="$HOME/.claude/plugins/cache/lichtpfad/h2t-dev"

# Detect Python
PY=""
[ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && PY="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$PY" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && PY="$HOME/.h2t/venv/bin/python"
[ -z "$PY" ] && PY=$(command -v python 2>/dev/null || command -v python3 2>/dev/null || echo "")
[ -z "$PY" ] && { echo '{"status":"error","error":"Python not found"}'; exit 1; }

_winpath() { [[ "$1" == /c/* ]] && echo "C:${1:2}" || echo "$1"; }
PLUGIN_JSON_W=$(_winpath "$PLUGIN_JSON")
INSTALLED_JSON_W=$(_winpath "$INSTALLED_JSON")

VERSION=$("$PY" -c "import json; print(json.load(open(r'$PLUGIN_JSON_W'))['version'])" 2>/dev/null || echo "")
[ -z "$VERSION" ] && { echo '{"status":"error","error":"Cannot read version"}'; exit 1; }

SHA=$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")

for arg in "$@"; do [[ "$arg" == "--push" ]] && git -C "$REPO_DIR" push origin main 2>/dev/null; done

CACHE_DIR="$CACHE_BASE/$VERSION"
mkdir -p "$CACHE_DIR"
rm -rf "$CACHE_DIR"/*
rm -f "$CACHE_DIR/.orphaned_at"

# Copy plugin content
cp -r "$PLUGIN_DIR/." "$CACHE_DIR/"

# Update installed_plugins.json if it exists
if [ -f "$INSTALLED_JSON" ]; then
  NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
  CACHE_DIR_WIN=$(echo "$CACHE_DIR" | sed 's|/c/|C:\\|; s|/|\\|g')
  "$PY" -c "
import json
path = r'$INSTALLED_JSON_W'
with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
key = 'h2t-dev@lichtpfad'
entry = {'scope': 'user', 'installPath': r'$CACHE_DIR_WIN', 'version': '$VERSION',
         'installedAt': '$NOW', 'lastUpdated': '$NOW', 'gitCommitSha': '$SHA'}
data.setdefault('plugins', {})[key] = [entry]
with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
" 2>/dev/null || true
fi

SKILLS_COUNT=$(find "$CACHE_DIR/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)

echo "{\"status\":\"ok\",\"version\":\"$VERSION\",\"sha\":\"${SHA:0:7}\",\"cache\":\"$CACHE_DIR\",\"skills\":$SKILLS_COUNT}"
