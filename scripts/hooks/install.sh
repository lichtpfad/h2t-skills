#!/usr/bin/env sh
# Point git at the versioned hook directory. Run from anywhere in the repo:
#   sh scripts/hooks/install.sh
#
# This sets core.hooksPath rather than symlinking into .git/hooks, so an edit to
# a hook takes effect immediately and there is nothing to re-install after one.
#
# core.hooksPath is per-clone and cannot be committed, so this step still has to
# happen once per checkout. What makes it noticeable when it has not: `h2t-gather`
# reports a versioned hook git is not running as a session-start hint.

set -e

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

chmod +x scripts/hooks/pre-commit 2>/dev/null || true
git config core.hooksPath scripts/hooks

echo "✓ core.hooksPath = $(git config --get core.hooksPath)"
echo
echo "Test it:"
echo "  python3 scripts/check_marketplace_sync.py"
