#!/usr/bin/env bash
# Creates ~/.h2t/venv with all h2t skill dependencies
set -e
VENV_DIR="${H2T_VENV:-$HOME/.h2t/venv}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating h2t venv at $VENV_DIR..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "h2t venv ready at $VENV_DIR"
echo ""
echo "Add to PATH:  export PATH=\"$VENV_DIR/bin:\$PATH\""
echo "Or set venv:  export H2T_VENV=\"$VENV_DIR\""
