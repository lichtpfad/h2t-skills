#!/usr/bin/env bash
# shellcheck shell=bash
set -euo pipefail

H2T_PYTHON_CMD=()

# Probe module used to validate a candidate interpreter. Default is the trivial
# "import sys" (any Python passes). Callers that need a specific package present
# (e.g. the gather hook, which runs `-m lib.cli.main`) pass a stricter probe as
# the first argument to resolve_h2t_python so a package-less interpreter is
# rejected and resolution fails loudly instead of a downstream silent crash.
_H2T_PYTHON_PROBE="import sys"

_h2t_try_python() {
  "$@" -c "$_H2T_PYTHON_PROBE" >/dev/null 2>&1 || return 1
  H2T_PYTHON_CMD=("$@")
  return 0
}

resolve_h2t_python() {
  local _H2T_PYTHON_PROBE="${1:-import sys}"
  H2T_PYTHON_CMD=()

  if [ -n "${H2T_PYTHON:-}" ]; then
    _h2t_try_python "$H2T_PYTHON" && return 0
  fi

  local candidate
  for candidate in "$HOME/.h2t/venv/Scripts/python.exe" "$HOME/.h2t/venv/bin/python"; do
    [ -f "$candidate" ] || continue
    _h2t_try_python "$candidate" && return 0
  done

  if command -v py >/dev/null 2>&1; then
    _h2t_try_python py -3.11 && return 0
    _h2t_try_python py -3 && return 0
  fi

  for candidate in python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    _h2t_try_python "$candidate" && return 0
  done

  return 1
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  if resolve_h2t_python; then
    printf '%q ' "${H2T_PYTHON_CMD[@]}"
    printf '\n'
    exit 0
  fi
  exit 1
fi
