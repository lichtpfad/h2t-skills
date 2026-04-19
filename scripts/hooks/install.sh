#!/usr/bin/env sh
# One-shot installer: symlink scripts/hooks/pre-commit into .git/hooks/.
# Run from repo root: sh scripts/hooks/install.sh

set -e

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

src="scripts/hooks/pre-commit"
dst=".git/hooks/pre-commit"

if [ -e "$dst" ] && [ ! -L "$dst" ]; then
  echo "error: $dst already exists and is not a symlink." >&2
  echo "       Back it up or remove it, then rerun." >&2
  exit 1
fi

# Symlink if supported; fallback to copy on Windows native Git without symlinks.
if ln -sf "../../$src" "$dst" 2>/dev/null; then
  chmod +x "$src"
  echo "✓ installed symlink: $dst → $src"
else
  cp "$src" "$dst"
  chmod +x "$dst"
  echo "✓ installed copy: $dst (symlink not supported; update manually after edits)"
fi

echo
echo "Test it:"
echo "  python scripts/check_marketplace_sync.py"
