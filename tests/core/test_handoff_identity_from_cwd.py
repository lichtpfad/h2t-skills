"""The writer derives session identity from the working directory, not from its caller.

`--project` was required, so the identity reaching disk was whatever string the model
passed — documented to fall back to "the current repo name" when session-start had not
run. That fallback is visible on this machine as three directories for one project
(`agent-skills/`, `h2t-skills/`) plus an `unknown/` for a repo that resolved to nothing.

The reader already resolves scope from cwd (`identify_project` -> repo-mapping.yaml).
The writer must go through the same function, so both halves answer "which project is
this?" the same way.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "plugins" / "h2t-core" / "skills" / "handoff" / "scripts" / "writer.py"


def _config_root(tmp_path, mapping_yaml):
    config = tmp_path / "config"
    config.mkdir()
    (config / "repo-mapping.yaml").write_text(mapping_yaml, encoding="utf-8")
    (config / "domains.yaml").write_text("domains: {}\n", encoding="utf-8")
    return config


def _write(cwd, sessions_root, config_root, *extra):
    env = dict(os.environ)
    env["H2T_SESSION_ROOT"] = str(sessions_root)
    env["H2T_MACHINE_NAME"] = "test-machine"
    env["H2T_EVALS_MODE"] = "off"
    env["H2T_CONFIG_ROOT"] = str(config_root)
    result = subprocess.run(
        [sys.executable, str(WRITER), "write",
         "--session-id", "some-session-2026-08-23",
         "--what-done", "did the thing",
         "--what-remains", "- [ ] the next thing", *extra],
        capture_output=True, text=True, env=env, cwd=str(cwd), check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_project_comes_from_the_working_directory(tmp_path):
    work = tmp_path / "some-checkout"
    work.mkdir()
    config = _config_root(tmp_path, (
        "mappings: {}\n"
        f"cwd_patterns:\n  {Path(work).resolve()}: personal-os/derived-id\n"
        "default: dev/unknown\n"
    ))
    out = _write(work, tmp_path / "sessions", config)
    assert Path(out["markdown"]).parent.name == "derived-id", out["markdown"]
    assert "**Domain:** personal-os" in Path(out["markdown"]).read_text(encoding="utf-8")


def test_unresolved_project_keeps_the_directory_name(tmp_path):
    """`unknown/` is a directory no reader looks in; the checkout name at least is a key."""
    work = tmp_path / "unmapped-checkout"
    work.mkdir()
    config = _config_root(tmp_path, "mappings: {}\ncwd_patterns: {}\ndefault: dev/unknown\n")
    out = _write(work, tmp_path / "sessions", config)
    assert Path(out["markdown"]).parent.name == "unmapped-checkout", out["markdown"]


def test_explicit_project_still_wins(tmp_path):
    work = tmp_path / "some-checkout"
    work.mkdir()
    config = _config_root(tmp_path, (
        "mappings: {}\n"
        f"cwd_patterns:\n  {Path(work).resolve()}: personal-os/derived-id\n"
        "default: dev/unknown\n"
    ))
    out = _write(work, tmp_path / "sessions", config,
                 "--project", "explicit-id", "--domain", "personal-os")
    assert Path(out["markdown"]).parent.name == "explicit-id", out["markdown"]
