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
    # A module that cannot exist, not `import lib.cli.main`. PATH keeps /usr/bin:/bin
    # because the fakes need a shell, so whatever real interpreter the host puts there
    # stays reachable — and `lib.cli.main` is importable from the repository root, which
    # is where the suite runs. On ubuntu `python` is one of those, so the probe this case
    # calls unsatisfiable was satisfied and the resolver correctly returned zero (#471).
    if resolve_h2t_python "import h2t_probe_that_cannot_exist_471"; then
      echo "FAIL: custom probe with no satisfying python should return non-zero"
      exit 1
    fi
  )
}

# uv is the last resort: it can supply an interpreter AND the packages a probe needs,
# but it is slow and may download, and these hooks run on every prompt.
test_uv_used_only_when_nothing_local_satisfies_the_probe() {
  local home_dir="$TMPDIR_TEST/home6"
  local bin_dir="$TMPDIR_TEST/bin6"

  make_fake_python "$bin_dir/python3" \
    '[[ "${1:-}" == "-c" && "${2:-}" == "import sys" ]] && exit 0; exit 1'
  make_fake_python "$bin_dir/uv" 'exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    resolve_h2t_python "import yaml" pyyaml
    assert_eq "${H2T_PYTHON_CMD[*]}" \
      "uv run --no-project --python 3.11 --with pyyaml python" \
      "uv should resolve when no local python has the package"
  )
}

test_uv_is_not_reached_when_a_local_python_satisfies() {
  local home_dir="$TMPDIR_TEST/home7"
  local bin_dir="$TMPDIR_TEST/bin7"

  make_fake_python "$bin_dir/python3" '[[ "${1:-}" == "-c" ]] && exit 0; exit 0'
  make_fake_python "$bin_dir/uv" 'exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    resolve_h2t_python "import yaml" pyyaml
    assert_eq "${H2T_PYTHON_CMD[*]}" "python3" \
      "a working local python must win; uv costs hook latency on every prompt"
  )
}

test_every_requirement_reaches_uv() {
  local home_dir="$TMPDIR_TEST/home8"
  local bin_dir="$TMPDIR_TEST/bin8"

  # Shadow the host's python3 with one that satisfies nothing, so the chain has to walk
  # past it. Without this the test passes or fails on whether /usr/bin/python3 happens
  # to have the package — a property of the machine, not of the resolver.
  make_fake_python "$bin_dir/python3" 'exit 1'
  make_fake_python "$bin_dir/python" 'exit 1'
  make_fake_python "$bin_dir/uv" 'exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    resolve_h2t_python "import yaml, requests" pyyaml requests
    assert_eq "${H2T_PYTHON_CMD[*]}" \
      "uv run --no-project --python 3.11 --with pyyaml --with requests python" \
      "each requirement should become its own --with"
  )
}

test_no_requirements_is_not_a_dangling_with() {
  local home_dir="$TMPDIR_TEST/home9"
  local bin_dir="$TMPDIR_TEST/bin9"

  # Shadow the host's python3 with one that satisfies nothing, so the chain has to walk
  # past it. Without this the test passes or fails on whether /usr/bin/python3 happens
  # to have the package — a property of the machine, not of the resolver.
  make_fake_python "$bin_dir/python3" 'exit 1'
  make_fake_python "$bin_dir/python" 'exit 1'
  make_fake_python "$bin_dir/uv" 'exit 0'

  (
    export HOME="$home_dir"
    export PATH="$bin_dir:/usr/bin:/bin"
    unset H2T_PYTHON

    source "$RESOLVER"
    resolve_h2t_python
    assert_eq "${H2T_PYTHON_CMD[*]}" "uv run --no-project --python 3.11 python" \
      "a probe with no packages must not produce a dangling --with"
  )
}


test_broken_venv_falls_back_to_python3
test_broken_env_var_falls_back_to_python3
test_good_env_var_wins
test_custom_probe_rejects_package_less_python
test_custom_probe_all_fail_returns_nonzero
test_uv_used_only_when_nothing_local_satisfies_the_probe
test_uv_is_not_reached_when_a_local_python_satisfies
test_every_requirement_reaches_uv
test_no_requirements_is_not_a_dangling_with

echo "OK: resolve-h2t-python"
