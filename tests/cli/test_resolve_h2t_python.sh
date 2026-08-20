#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESOLVER="$REPO_ROOT/plugins/h2t-core/scripts/resolve-h2t-python.sh"

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

make_fake_python() {
  local target="$1"
  local body="$2"
  mkdir -p "$(dirname "$target")"
  cat >"$target" <<EOF
#!/usr/bin/env bash
$body
EOF
  chmod +x "$target"
}

assert_eq() {
  local got="$1"
  local want="$2"
  local label="$3"
  if [[ "$got" != "$want" ]]; then
    echo "FAIL: $label"
    echo "  got:  $got"
    echo "  want: $want"
    exit 1
  fi
}

test_broken_venv_falls_back_to_python3() {
  local home_dir="$TMPDIR_TEST/home1"
  local bin_dir="$TMPDIR_TEST/bin1"

  make_fake_python "$home_dir/.h2t/venv/Scripts/python.exe" 'exit 1'
  make_fake_python "$bin_dir/python3" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    resolve_h2t_python
    assert_eq "${H2T_PYTHON_CMD[*]}" "python3" "broken venv should fall back to python3"
  )
}

test_broken_env_var_falls_back_to_python3() {
  local home_dir="$TMPDIR_TEST/home2"
  local bin_dir="$TMPDIR_TEST/bin2"

  make_fake_python "$bin_dir/bad-python" 'exit 1'
  make_fake_python "$bin_dir/python3" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    export H2T_PYTHON="$bin_dir/bad-python"

    source "$RESOLVER"
    resolve_h2t_python
    assert_eq "${H2T_PYTHON_CMD[*]}" "python3" "broken H2T_PYTHON should fall back to python3"
  )
}

test_good_env_var_wins() {
  local home_dir="$TMPDIR_TEST/home3"
  local bin_dir="$TMPDIR_TEST/bin3"

  make_fake_python "$bin_dir/good-python" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'
  make_fake_python "$bin_dir/python3" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    export H2T_PYTHON="$bin_dir/good-python"

    source "$RESOLVER"
    resolve_h2t_python
    assert_eq "${H2T_PYTHON_CMD[*]}" "$bin_dir/good-python" "working H2T_PYTHON should win"
  )
}

test_custom_probe_rejects_package_less_python() {
  local home_dir="$TMPDIR_TEST/home4"
  local bin_dir="$TMPDIR_TEST/bin4"

  # venv python satisfies "import sys" but NOT the custom probe
  make_fake_python "$home_dir/.h2t/venv/Scripts/python.exe" \
    '[[ "${1:-}" == "-c" && "${2:-}" == "import sys" ]] && exit 0; exit 1'
  # python3 satisfies any probe
  make_fake_python "$bin_dir/python3" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    # default probe: venv passes and wins
    resolve_h2t_python
    assert_eq "${H2T_PYTHON_CMD[*]}" "$home_dir/.h2t/venv/Scripts/python.exe" \
      "default probe should accept package-less venv"
    # custom probe: venv rejected, falls back to python3
    resolve_h2t_python "import lib.cli.main"
    assert_eq "${H2T_PYTHON_CMD[*]}" "python3" \
      "custom probe should reject package-less venv and fall back"
  )
}

test_custom_probe_all_fail_returns_nonzero() {
  local home_dir="$TMPDIR_TEST/home5"
  local bin_dir="$TMPDIR_TEST/bin5"

  # every candidate satisfies "import sys" only
  make_fake_python "$bin_dir/python3" \
    '[[ "${1:-}" == "-c" && "${2:-}" == "import sys" ]] && exit 0; exit 1'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    if resolve_h2t_python "import lib.cli.main"; then
      echo "FAIL: custom probe with no satisfying python should return non-zero"
      exit 1
    fi
  )
}

test_broken_venv_falls_back_to_python3
test_broken_env_var_falls_back_to_python3
test_good_env_var_wins
test_custom_probe_rejects_package_less_python
test_custom_probe_all_fail_returns_nonzero

echo "OK: resolve-h2t-python"
